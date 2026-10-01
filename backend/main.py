"""
main.py — thin FastAPI layer.

This file does auth + HTTP plumbing only. It never runs the model itself —
every /customers* read comes straight out of customer_predictions, which
pipeline.py keeps fresh on a schedule. If you're looking for the scoring
logic, it's in pipeline.py; if you're looking for the fake activity feed,
it's in realtime.py.
"""
import os
import io
import json
import asyncio
import smtplib
import logging
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta, timezone, date
from typing import Optional
import secrets

import bcrypt
import jwt
import joblib
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

try:
    import shap
except ImportError:
    shap = None

import cache
import pipeline
from features import FEATURE_COLS, ticket_urgency_score
from database import (
    engine, get_db, init_all_tables, User, MLCustomer, CustomerNote, CustomerOwner,
    CustomerPrediction, LoginEvent, UsageEvent, SupportTicket, PaymentEvent, EmailDraft, Report, AppSetting,
    Plan, Subscription, seed_default_plans,
)

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RetainAI")

raw_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
allowed_origins_list = [o.strip() for o in raw_allowed_origins.split(",") if o.strip()]

# Allows localhost (any port) + any Vercel production or preview domain (*.vercel.app)
CORS_ORIGIN_REGEX = r"^(http://(localhost|127\.0\.0\.1):\d+|https://.*\.vercel\.app)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ── Config ────────────────────────────────────────────────────────────────
ENV = os.environ.get("ENV", "production").lower()
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALGORITHM = "HS256"
DEFAULT_HIGH_RISK_THRESHOLD = 0.7  # used until an admin overrides it via /settings/app
SCORING_INTERVAL_SECONDS = int(os.environ.get("SCORING_INTERVAL_SECONDS", "15"))
# Emails in this list get "admin" role automatically on signup. Comma-separated.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
}

if ENV == "production":
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        raise RuntimeError("FATAL: set a strong SECRET_KEY (>=32 chars) before running in production.")
elif not SECRET_KEY:
    SECRET_KEY = "dev_only_fallback_do_not_use_in_production"
    print("[WARNING] SECRET_KEY not set — using a dev-only fallback.")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
_MODEL_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "model.pkl"),
    os.path.join(os.path.dirname(__file__), "..", "model.pkl"),
    os.path.join(os.path.dirname(__file__), "saas_churn_model.pkl"),
    os.path.join(os.path.dirname(__file__), "..", "saas_churn_model.pkl"),
]
MODEL_PATH = next((p for p in _MODEL_CANDIDATES if os.path.exists(p)), _MODEL_CANDIDATES[0])

_META_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "model_metadata.json"),
    os.path.join(os.path.dirname(__file__), "..", "model_metadata.json"),
]
META_PATH = next((p for p in _META_CANDIDATES if os.path.exists(p)), _META_CANDIDATES[0])

model = None
explainer = None
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY") or "sk-not-configured")


# ── Auth helpers ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    if len(password.encode()) > 72:
        raise HTTPException(400, "Password must be 72 bytes or fewer")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(email: str) -> str:
    payload = {"sub": email, "exp": datetime.utcnow() + timedelta(days=1)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
        return email
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


def db_session() -> Session:
    return next(get_db())


def get_current_admin(current_user: str = Depends(get_current_user)) -> str:
    """Same as get_current_user, but 403s unless that user's role is 'admin'."""
    db = db_session()
    try:
        user = db.query(User).filter(User.email == current_user).first()
        if not user or user.role != "admin":
            raise HTTPException(403, "Admin access required")
        return current_user
    finally:
        db.close()


def get_high_risk_threshold() -> float:
    """Reads the org-wide high-risk threshold from app_settings, falling back
    to DEFAULT_HIGH_RISK_THRESHOLD if an admin has never set one."""
    db = db_session()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "high_risk_threshold").first()
        if row is None:
            return DEFAULT_HIGH_RISK_THRESHOLD
        try:
            return float(row.value)
        except (TypeError, ValueError):
            return DEFAULT_HIGH_RISK_THRESHOLD
    finally:
        db.close()


# ── Startup ───────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    global model, explainer
    init_all_tables()
    seed_default_plans()

    model_version = "unknown"
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        if shap is not None:
            explainer = shap.TreeExplainer(model)
        if os.path.exists(META_PATH):
            with open(META_PATH) as f:
                model_version = json.load(f).get("model_version", "unknown")
        print(f"[startup] model loaded ({model_version})")
    else:
        print(f"[startup] WARNING: no model at {MODEL_PATH} — run train_model.py")

    pipeline.configure(model=model, explainer=explainer, model_version=model_version)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        pipeline.run_scoring_pass, trigger="interval",
        seconds=SCORING_INTERVAL_SECONDS, id="scoring_pass",
        max_instances=1, replace_existing=True,
    )
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(pipeline.run_scoring_pass))
    print(f"[startup] scoring pipeline scheduled every {SCORING_INTERVAL_SECONDS}s")


@app.get("/")
@app.head("/")
def root():
    return {"message": "RetainAI backend is running", "docs": "/docs"}


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


# ── Email & SMTP Utilities ───────────────────────────────────────────────
def _send_smtp_email(to_addr: str, subject: str, body: str, html_body: str = None) -> tuple[bool, str]:
    host, user = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM", user)  # Use verified sender if set
    port = int(os.environ.get("SMTP_PORT", "587"))
    if not all([host, user, password, to_addr]):
        return False, "SMTP is not configured (set SMTP_HOST / SMTP_USER / SMTP_PASSWORD)"
    from email.mime.multipart import MIMEMultipart
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
    else:
        msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True, "sent"
    except Exception as e:
        err_msg = str(e)
        if "550" in err_msg and "testing emails" in err_msg:
            err_msg = "Resend Sandbox restriction: free tier only delivers emails to sandeepkumar9837146@gmail.com until a custom domain is verified at resend.com/domains"
        logging.warning(f"SMTP send failed: {err_msg}")
        return False, f"send failed: {err_msg}"


def _generate_verification_code() -> str:
    """Generate a 6-digit numeric verification code."""
    return f"{secrets.randbelow(900000) + 100000}"


def _send_verification_email(email: str, code: str) -> tuple[bool, str]:
    import urllib.parse
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    verify_url = f"{frontend_url}/verify?email={urllib.parse.quote(email)}&code={code}"

    subject = f"Verify your RetainAI account — Code: {code}"
    plain_body = f"""Welcome to RetainAI!

Your 6-digit verification code is: {code}

You can verify automatically by opening this link:
{verify_url}

Or enter your 6-digit code on the verification screen:
{code}

This verification code is valid for 15 minutes.

If you did not request this verification email, please safely disregard it.

— RetainAI Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify your RetainAI Account</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #e2e8f0; margin: 0; padding: 30px 15px;">
  <div style="max-width: 520px; margin: 0 auto; background-color: #0f172a; border: 1px solid #334155; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);">
    <div style="background: linear-gradient(135deg, #0e7490 0%, #0369a1 100%); padding: 28px 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 26px; color: #ffffff; font-weight: 800; letter-spacing: -0.5px;">RetainAI</h1>
      <p style="margin: 6px 0 0 0; color: #a5f3fc; font-size: 13px;">Customer Retention &amp; Churn Intelligence</p>
    </div>
    <div style="padding: 32px 28px;">
      <div style="font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 12px;">Confirm your email address</div>
      <p style="font-size: 14px; line-height: 1.6; color: #94a3b8; margin-bottom: 24px;">
        Welcome to RetainAI. Use the 6-digit verification code below, or click the button to verify your email automatically:
      </p>
      <div style="background: #020617; border: 2px dashed #06b6d4; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #38bdf8; font-weight: 600; margin-bottom: 8px;">Verification Code</div>
        <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #22d3ee; margin: 0;">{code}</div>
      </div>
      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{verify_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #06b6d4 0%, #0284c7 100%); color: #ffffff; text-decoration: none; font-weight: 700; font-size: 15px; padding: 13px 30px; border-radius: 8px; box-shadow: 0 4px 14px rgba(6, 182, 212, 0.35);">
          Verify &amp; Activate Account &rarr;
        </a>
      </div>
      <p style="font-size: 12px; text-align: center; color: #64748b; margin-top: 10px; word-break: break-all;">
        Direct link: <a href="{verify_url}" style="color: #38bdf8; text-decoration: underline;">{verify_url}</a>
      </p>
      <p style="font-size: 13px; text-align: center; margin-top: 16px; color: #94a3b8;">
        ⏳ This code will expire in <strong style="color: #f1f5f9;">15 minutes</strong>.
      </p>
      <div style="font-size: 12px; color: #64748b; line-height: 1.5; margin-top: 24px; padding-top: 16px; border-top: 1px solid #1e293b;">
        If you didn't create an account with RetainAI, you can safely ignore this email. Someone may have typed your email address by mistake.
      </div>
    </div>
    <div style="background-color: #090d16; padding: 18px 24px; text-align: center; font-size: 11px; color: #475569; border-top: 1px solid #1e293b;">
      &copy; {datetime.now(timezone.utc).year} RetainAI Platform. All rights reserved.
    </div>
  </div>
</body>
</html>
"""
    ok, detail = _send_smtp_email(email, subject, plain_body, html_body)
    if not ok:
        logging.warning(f"[AUTH] Could not send verification email to {email}: {detail}")
    else:
        logging.info(f"[AUTH] Verification email sent to {email} successfully via SMTP.")
    return ok, detail


# ── Auth endpoints ───────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class EmailVerificationRequest(BaseModel):
    email: EmailStr
    code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ProfileUpdate(BaseModel):
    name: str
    job_title: str
    company_name: str
    avatar_url: str
    preferences: dict = {}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@app.post("/signup")
def signup(user: UserCreate):
    if len(user.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db = db_session()
    try:
        user_email = user.email.strip().lower()
        existing = db.query(User).filter(User.email == user_email).first()
        is_test_env = os.environ.get("ENV") == "test"

        if existing:
            if getattr(existing, "is_verified", True):
                raise HTTPException(400, "Email already registered")

            code = _generate_verification_code()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            existing.hashed_password = hash_password(user.password)
            existing.verification_code = code
            existing.verification_code_expires_at = expires_at
            db.commit()

            email_sent, detail = _send_verification_email(user_email, code)
            resp = {
                "message": f"Verification code sent to {user_email}. Please check your inbox.",
                "email": user_email,
                "role": existing.role,
                "requires_verification": True,
            }
            if not email_sent:
                resp["debug_code"] = code
                resp["notice"] = f"SMTP note: {detail}. (Code: {code})"
            return resp

        sub = db.query(Subscription).first()
        if sub:
            plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
            seat_count = db.query(User).count()
            if plan and seat_count >= plan.max_seats:
                raise HTTPException(
                    402,
                    f"Your {plan.name} plan is at its {plan.max_seats}-seat limit. "
                    "An admin needs to upgrade the plan before adding more people.",
                )

        role = "admin" if user_email in ADMIN_EMAILS else "member"
        code = _generate_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # In automated test suite, default to pre-verified so existing tests pass
        auto_verify = is_test_env

        new_user = User(
            email=user_email,
            hashed_password=hash_password(user.password),
            role=role,
            is_verified=auto_verify,
            verification_code=None if auto_verify else code,
            verification_code_expires_at=None if auto_verify else expires_at,
        )
        db.add(new_user)
        db.commit()

        if not auto_verify:
            email_sent, detail = _send_verification_email(user_email, code)
        else:
            email_sent, detail = True, "test auto-verified"

        resp = {
            "message": "User created successfully. A verification code has been sent to your email.",
            "email": user_email,
            "role": role,
            "requires_verification": not auto_verify,
        }
        if not auto_verify and not email_sent:
            resp["debug_code"] = code
            resp["notice"] = f"SMTP note: {detail}. (Verification code: {code})"

        return resp
    finally:
        db.close()


def _process_verification(db, email: str, code: str) -> dict:
    user_email = email.strip().lower()
    code_input = code.strip()
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(404, "No account found with this email.")

    if getattr(user, "is_verified", False):
        return {
            "message": "Account already verified. Welcome back!",
            "access_token": create_access_token(user.email),
            "token_type": "bearer",
            "role": user.role,
            "is_verified": True,
        }

    if not user.verification_code:
        raise HTTPException(400, "No pending verification code found. Please request a new code.")

    now = datetime.now(timezone.utc)
    expires_at = user.verification_code_expires_at
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            raise HTTPException(400, "Verification code has expired. Please click 'Resend code' to get a new one.")

    if user.verification_code != code_input:
        raise HTTPException(400, "Invalid verification code. Please check your email and try again.")

    # Mark user as verified in DB
    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None
    db.commit()

    return {
        "message": "Account verified successfully! Welcome to RetainAI.",
        "access_token": create_access_token(user.email),
        "token_type": "bearer",
        "role": user.role,
        "is_verified": True,
    }


@app.post("/verify-email")
@app.post("/verify")
def verify_email(req: EmailVerificationRequest):
    db = db_session()
    try:
        return _process_verification(db, req.email, req.code)
    finally:
        db.close()


@app.get("/verify-email")
@app.get("/verify")
def verify_email_get(email: str, code: str):
    db = db_session()
    try:
        res = _process_verification(db, email, code)
        token = res.get("access_token", "")
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        from starlette.responses import RedirectResponse
        return RedirectResponse(f"{frontend_url}/?token={token}&verified=true", status_code=303)
    finally:
        db.close()


@app.post("/resend-verification")
def resend_verification(req: ResendVerificationRequest):
    db = db_session()
    try:
        user_email = req.email.strip().lower()
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(404, "No account found with this email.")

        if getattr(user, "is_verified", False):
            raise HTTPException(400, "Account is already verified. You can sign in directly.")

        code = _generate_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        user.verification_code = code
        user.verification_code_expires_at = expires_at
        db.commit()

        email_sent, detail = _send_verification_email(user_email, code)
        resp = {
            "message": f"A new verification code has been sent to {user_email}.",
            "email": user_email,
        }
        if not email_sent:
            resp["debug_code"] = code
            resp["notice"] = f"SMTP note: {detail}. (Verification code: {code})"
        return resp
    finally:
        db.close()


@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    db = db_session()
    try:
        user = db.query(User).filter(User.email == form.username.strip().lower()).first()
        if not user or not verify_password(form.password, user.hashed_password):
            raise HTTPException(401, "Incorrect email or password")

        if not getattr(user, "is_verified", True):
            raise HTTPException(
                403,
                detail="Your account is not verified yet. Please check your inbox for the verification code.",
            )

        return {"access_token": create_access_token(user.email), "token_type": "bearer", "role": user.role}
    finally:
        db.close()


@app.get("/me")
def get_me(current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        user = db.query(User).filter(User.email == current_user).first()
        if not user:
            raise HTTPException(404, "User not found")
        try:
            prefs = json.loads(user.preferences or "{}")
        except Exception:
            prefs = {}
        return {
            "email": user.email, "name": user.name or "", "job_title": user.job_title or "",
            "company_name": user.company_name or "", "avatar_url": user.avatar_url or "",
            "preferences": prefs, "role": user.role,
        }
    finally:
        db.close()


@app.put("/me")
def update_me(profile: ProfileUpdate, current_user: str = Depends(get_current_user)):
    if not profile.name.strip() or not profile.job_title.strip():
        raise HTTPException(400, "Name and Job Title cannot be empty")
    db = db_session()
    try:
        user = db.query(User).filter(User.email == current_user).first()
        user.name = profile.name
        user.job_title = profile.job_title
        user.company_name = profile.company_name
        user.avatar_url = profile.avatar_url
        user.preferences = json.dumps(profile.preferences)
        db.commit()
        return {"message": "Profile updated successfully"}
    finally:
        db.close()


@app.post("/me/change_password")
def change_password(payload: PasswordChange, current_user: str = Depends(get_current_user)):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    db = db_session()
    try:
        user = db.query(User).filter(User.email == current_user).first()
        if not user or not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(400, "Incorrect current password")
        user.hashed_password = hash_password(payload.new_password)
        db.commit()
        return {"message": "Password changed successfully"}
    finally:
        db.close()


class RoleUpdate(BaseModel):
    role: str  # "admin" | "member"


@app.get("/admin/users")
def list_users(current_user: str = Depends(get_current_admin)):
    db = db_session()
    try:
        users = db.query(User).order_by(User.email).all()
        return {
            "users": [
                {"email": u.email, "name": u.name or "", "role": u.role}
                for u in users
            ]
        }
    finally:
        db.close()


@app.put("/admin/users/{email}/role")
def update_user_role(email: str, payload: RoleUpdate, current_user: str = Depends(get_current_admin)):
    if payload.role not in ("admin", "member"):
        raise HTTPException(400, "role must be 'admin' or 'member'")
    if email.lower() == current_user.lower() and payload.role != "admin":
        raise HTTPException(400, "You can't demote yourself")
    db = db_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(404, "User not found")
        user.role = payload.role
        db.commit()
        return {"email": user.email, "role": user.role}
    finally:
        db.close()


@app.get("/integrations/status")
def integrations_status(current_user: str = Depends(get_current_user)):
    return {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "slack": bool(os.environ.get("SLACK_WEBHOOK_URL")),
        "smtp": bool(os.environ.get("SMTP_HOST")),
    }


# ── Customers (all reads come from customer_predictions) ──────────────────
def _scored_customers_df() -> pd.DataFrame:
    cached = cache.get_cached("customers:scored")
    if cached is not None:
        return pd.DataFrame(cached)

    query = """
        SELECT c.customer_id, c.name, c.email, c.signup_date,
               p.churn_probability AS churn_risk_score, p.top_driver, p.shap_values, p.scored_at
        FROM ml_customers c
        JOIN customer_predictions p ON c.customer_id = p.customer_id
    """
    df = pd.read_sql(text(query), engine)
    if df.empty:
        return df

    df["high_risk"] = df["churn_risk_score"] > get_high_risk_threshold()
    df["shap_explanations"] = df["shap_values"].apply(lambda x: json.loads(x) if x else {})
    df = df.drop(columns=["shap_values"]).sort_values("churn_risk_score", ascending=False).reset_index(drop=True)

    cache.set_cached("customers:scored", df.to_dict(orient="records"), ttl_seconds=10)
    return df


def _owners_map(db: Session) -> dict:
    return {o.customer_id: o.owner_email for o in db.query(CustomerOwner).all()}


@app.get("/customers")
def list_customers(high_risk_only: bool = False, current_user: str = Depends(get_current_user)):
    df = _scored_customers_df()
    if df.empty:
        return {"count": 0, "customers": []}
    if high_risk_only:
        df = df[df["high_risk"]]
    db = db_session()
    try:
        owners = _owners_map(db)
    finally:
        db.close()
    records = df.to_dict(orient="records")
    for r in records:
        r["owner_email"] = owners.get(r["customer_id"])
    return {"count": len(records), "customers": records}


@app.get("/customers/summary")
def customers_summary(current_user: str = Depends(get_current_user)):
    df = _scored_customers_df()
    # Bucket boundaries derive from the SAME configurable threshold that decides
    # high_risk_count below (and that risk.js mirrors on the frontend) — previously
    # this used a hardcoded 0.33/0.66 split while high_risk_count used a different,
    # admin-editable number, so the KPI card and this chart could silently disagree.
    high_cut = get_high_risk_threshold()
    mid_cut = high_cut / 2
    buckets = {
        f"low (0-{round(mid_cut*100)}%)": 0,
        f"medium ({round(mid_cut*100)}-{round(high_cut*100)}%)": 0,
        f"high ({round(high_cut*100)}-100%)": 0,
    }
    bucket_keys = list(buckets.keys())
    if not df.empty:
        for score in df["churn_risk_score"]:
            key = bucket_keys[0] if score < mid_cut else bucket_keys[1] if score < high_cut else bucket_keys[2]
            buckets[key] += 1
    driver_counts = df["top_driver"].value_counts().to_dict() if not df.empty else {}
    return {
        "total_customers": len(df),
        "high_risk_count": int(df["high_risk"].sum()) if not df.empty else 0,
        "avg_risk_score": float(df["churn_risk_score"].mean()) if not df.empty else 0.0,
        "risk_distribution": buckets,
        "high_risk_threshold": high_cut,
        "top_driver_breakdown": driver_counts,
    }


@app.get("/customers/export")
def export_customers_csv(high_risk_only: bool = False, current_user: str = Depends(get_current_user)):
    df = _scored_customers_df()
    if high_risk_only:
        df = df[df["high_risk"]]
    db = db_session()
    try:
        owners = _owners_map(db)
    finally:
        db.close()
    export_df = df.copy()
    export_df["owner_email"] = export_df["customer_id"].map(owners).fillna("")
    export_df["churn_risk_score"] = export_df["churn_risk_score"].round(4)

    buf = io.StringIO()
    export_df.to_csv(buf, index=False)
    buf.seek(0)
    filename = "high_risk_customers.csv" if high_risk_only else "all_customers.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/customers/{customer_id}")
def get_customer_detail(customer_id: str, current_user: str = Depends(get_current_user)):
    cached = cache.get_cached(f"customer_detail:{customer_id}")
    if cached:
        return cached

    query = """
        SELECT c.customer_id, c.name, c.email, c.signup_date,
               p.churn_probability, p.shap_values
        FROM ml_customers c
        LEFT JOIN customer_predictions p ON c.customer_id = p.customer_id
        WHERE c.customer_id = :cid
    """
    with engine.connect() as conn:
        row = pd.read_sql(text(query), conn, params={"cid": customer_id})
    if row.empty:
        raise HTTPException(404, "Customer not found")

    record = row.iloc[0].to_dict()
    account_age_days = max(1, (datetime.utcnow().date() - record["signup_date"]).days)
    try:
        shap_explanations = json.loads(record.get("shap_values") or "{}")
    except Exception:
        shap_explanations = {}

    db = db_session()
    try:
        owner = db.query(CustomerOwner).filter(CustomerOwner.customer_id == customer_id).first()

        # Compute live activity fields for the KPI tiles
        from features import LOGIN_WINDOW_DAYS, USAGE_WINDOW_DAYS
        now = datetime.utcnow()

        login_count = db.query(LoginEvent).filter(
            LoginEvent.customer_id == customer_id,
            LoginEvent.login_at > now - timedelta(days=LOGIN_WINDOW_DAYS)
        ).count()

        usage_events = db.query(UsageEvent).filter(
            UsageEvent.customer_id == customer_id,
            UsageEvent.occurred_at > now - timedelta(days=USAGE_WINDOW_DAYS)
        ).all()
        avg_usage_mins = round(sum(u.duration_secs for u in usage_events) / 60 / max(1, len(usage_events)), 1) if usage_events else 0.0

        last_ticket = db.query(SupportTicket).filter(
            SupportTicket.customer_id == customer_id
        ).order_by(SupportTicket.created_at.desc()).first()
    finally:
        db.close()

    result = {
        "customer_id": record["customer_id"],
        "name": record["name"],
        "email": record["email"],
        "account_age_days": account_age_days,
        "churn_risk_score": float(record["churn_probability"]) if pd.notnull(record["churn_probability"]) else 0.0,
        "shap_explanations": shap_explanations,
        "owner_email": owner.owner_email if owner else None,
        # Activity KPI fields
        "login_frequency_raw": login_count,
        "daily_usage_mins": avg_usage_mins,
        "last_support_ticket_raw": last_ticket.subject if last_ticket else None,
    }
    cache.set_cached(f"customer_detail:{customer_id}", result, ttl_seconds=15)
    return result


@app.get("/customers/{customer_id}/risk_trend")
def customer_risk_trend(customer_id: str, days: int = 14, current_user: str = Depends(get_current_user)):
    cache_key = f"risk_trend:{customer_id}:{days}"
    cached = cache.get_cached(cache_key)
    if cached:
        return cached

    db = db_session()
    source = "reconstructed"
    points = None
    try:
        from models import RiskScoreSnapshot
        from datetime import date
        cutoff = date.today() - timedelta(days=days)
        recorded = (
            db.query(RiskScoreSnapshot)
            .filter(RiskScoreSnapshot.customer_id == customer_id, RiskScoreSnapshot.snapshot_date >= cutoff)
            .order_by(RiskScoreSnapshot.snapshot_date.asc())
            .all()
        )
        if len(recorded) >= 3:
            source = "recorded"
            points = [{"date": r.snapshot_date.isoformat(), "churn_risk_score": r.churn_risk_score} for r in recorded]
    finally:
        db.close()

    if points is None:
        points = pipeline.get_customer_trend(customer_id, days)
    if points is None:
        raise HTTPException(404, "Customer not found")

    result = {"customer_id": customer_id, "trend": points, "source": source}
    cache.set_cached(cache_key, result, ttl_seconds=300)
    return result


@app.get("/customer_history/{customer_id}")
def customer_history(customer_id: str, current_user: str = Depends(get_current_user)):
    cache_key = f"history:{customer_id}"
    cached = cache.get_cached(cache_key)
    if cached:
        return cached

    db = db_session()
    try:
        logins = db.query(LoginEvent).filter(LoginEvent.customer_id == customer_id) \
            .order_by(LoginEvent.login_at.desc()).limit(50).all()
        usage = db.query(UsageEvent).filter(UsageEvent.customer_id == customer_id) \
            .order_by(UsageEvent.occurred_at.desc()).limit(50).all()
        tickets = db.query(SupportTicket).filter(SupportTicket.customer_id == customer_id) \
            .order_by(SupportTicket.created_at.desc()).limit(50).all()
        payments = db.query(PaymentEvent).filter(PaymentEvent.customer_id == customer_id) \
            .order_by(PaymentEvent.occurred_at.desc()).limit(50).all()
    finally:
        db.close()

    result = {
        "logins": [{"login_timestamp": str(l.login_at)} for l in logins],
        "usage": [{"event_timestamp": str(u.occurred_at), "duration_secs": round(u.duration_secs, 1)} for u in usage],
        "support": [{"ticket_timestamp": str(t.created_at), "subject": t.subject} for t in tickets],
        "payments": [{"payment_timestamp": str(p.occurred_at), "amount_usd": p.amount, "status": p.status} for p in payments],
    }
    cache.set_cached(cache_key, result, ttl_seconds=60)
    return result


@app.get("/recent_events")
def recent_events(limit: int = 30, current_user: str = Depends(get_current_user)):
    """A merged, most-recent-first feed of raw activity realtime.py has written —
    what's actually happening, not a synthetic replay."""
    db = db_session()
    try:
        logins = db.query(LoginEvent).order_by(LoginEvent.login_at.desc()).limit(limit).all()
        usage = db.query(UsageEvent).order_by(UsageEvent.occurred_at.desc()).limit(limit).all()
        tickets = db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(limit).all()
        events = (
            [{"type": "login", "customer_id": l.customer_id, "timestamp": l.login_at.isoformat()} for l in logins]
            + [{"type": "usage", "customer_id": u.customer_id, "timestamp": u.occurred_at.isoformat()} for u in usage]
            + [{"type": "ticket", "customer_id": t.customer_id, "timestamp": t.created_at.isoformat(), "subject": t.subject} for t in tickets]
        )
    finally:
        db.close()
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return {"events": events[:limit]}


# ── Notes & owner assignment ────────────────────────────────────────────
class NoteCreate(BaseModel):
    text: str


@app.get("/customers/{customer_id}/notes")
def list_notes(customer_id: str, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        notes = db.query(CustomerNote).filter(CustomerNote.customer_id == customer_id) \
            .order_by(CustomerNote.created_at.desc()).all()
        return {"notes": [{"id": n.id, "author": n.author, "text": n.text, "created_at": str(n.created_at)} for n in notes]}
    finally:
        db.close()


@app.post("/customers/{customer_id}/notes")
def add_note(customer_id: str, note: NoteCreate, current_user: str = Depends(get_current_user)):
    if not note.text.strip():
        raise HTTPException(400, "Note text can't be empty")
    db = db_session()
    try:
        n = CustomerNote(customer_id=customer_id, author=current_user, text=note.text.strip())
        db.add(n)
        db.commit()
        db.refresh(n)
        return {"id": n.id, "author": n.author, "text": n.text, "created_at": str(n.created_at)}
    finally:
        db.close()


class OwnerAssign(BaseModel):
    owner_email: EmailStr


@app.put("/customers/{customer_id}/owner")
def assign_owner(customer_id: str, payload: OwnerAssign, current_user: str = Depends(get_current_admin)):
    db = db_session()
    try:
        existing = db.query(CustomerOwner).filter(CustomerOwner.customer_id == customer_id).first()
        if existing:
            existing.owner_email = payload.owner_email
        else:
            db.add(CustomerOwner(customer_id=customer_id, owner_email=payload.owner_email))
        db.commit()
        return {"customer_id": customer_id, "owner_email": payload.owner_email}
    finally:
        db.close()


# ── What-if prediction (ad hoc, not tied to a stored customer) ───────────
class PredictionRequest(BaseModel):
    customer_id: Optional[str] = None
    account_age_days: float
    login_frequency: int
    daily_usage_mins: float
    last_support_ticket: str  # raw ticket text OR a 0-10 score


@app.post("/predict")
def predict_churn(req: PredictionRequest, current_user: str = Depends(get_current_user)):
    if model is None:
        raise HTTPException(503, "Model not loaded")
    X = pd.DataFrame([{
        "Account_Age_Days": req.account_age_days,
        "Login_Frequency": req.login_frequency,
        "Daily_Usage_Mins": req.daily_usage_mins,
        "Last_Support_Ticket": ticket_urgency_score(req.last_support_ticket),
    }])
    probability = float(model.predict_proba(X)[0][1])
    shap_explanations = {}
    if explainer is not None:
        raw_shap = explainer.shap_values(X)
        row = raw_shap[1][0] if isinstance(raw_shap, list) else (
            raw_shap[0][:, 1] if raw_shap.ndim == 3 else raw_shap[0]
        )
        shap_explanations = dict(zip(FEATURE_COLS, [float(v) for v in row]))
    top_driver = max(shap_explanations, key=lambda k: abs(shap_explanations[k])) if shap_explanations else None
    return {
        "customer_id": req.customer_id,
        "churn_risk_score": probability,
        "high_risk": probability > get_high_risk_threshold(),
        "shap_explanations": shap_explanations,
        "top_driver": top_driver,
    }


# ── AI-drafted retention email ────────────────────────────────────────────
TONE_GUIDANCE = {
    "professional": "professional and courteous, matter-of-fact",
    "friendly": "warm, casual, and conversational, like a helpful teammate",
    "empathetic": "empathetic and understanding, acknowledging any friction they've hit",
    "urgent": "polite but conveys real urgency and a clear time-bound offer",
}
LENGTH_GUIDANCE = {
    "short": "under 60 words",
    "medium": "80-120 words",
    "long": "150-200 words",
}


def _generate_email_draft(customer_data: dict, shap_explanations: dict, tone: str = "professional",
                           length: str = "medium") -> dict:
    tone = tone if tone in TONE_GUIDANCE else "professional"
    length = length if length in LENGTH_GUIDANCE else "medium"
    prompt = (
        "You are an expert SaaS Customer Success Agent. A customer is at risk of churning.\n"
        f"Profile data: {json.dumps(customer_data)}\n"
        f"Risk Drivers (SHAP values): {json.dumps(shap_explanations)}\n\n"
        f"Draft a personalized retention email offering a relevant solution based strictly on "
        f"their risk drivers. Tone should be {TONE_GUIDANCE[tone]}. Length should be {LENGTH_GUIDANCE[length]}. "
        "Sign off as 'RetainAI Automated Success Team'. Do not use placeholders like [Name]. "
        "Output plain text only. Do not use HTML tags, markdown, or rich text formatting. "
        "Respond with two lines: 'SUBJECT: ...' followed by the email body."
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=400,
        )
        text_out = response.choices[0].message.content.strip()
        source = "openai"
    except Exception as e:
        logging.warning(f"OpenAI call failed, using fallback template: {e}")
        name = customer_data.get("name", "there")
        text_out = (
            "SUBJECT: Checking in\n"
            f"Hi {name},\n\nWe noticed your usage has dropped recently. We'd love to help you "
            "get more value from RetainAI — let us know if a quick check-in call would help.\n\n"
            "Best,\nRetainAI Automated Success Team"
        )
        source = "fallback_template"

    subject, body = "Checking in", text_out
    if text_out.upper().startswith("SUBJECT:"):
        first_line, _, rest = text_out.partition("\n")
        subject = first_line.split(":", 1)[1].strip()
        body = rest.strip()
    return {"subject": subject, "body": body, "source": source, "tone": tone, "length": length}


# ── Billing: plan limits + AI-email quota enforcement ──────────────────────
def _consume_ai_email_quota(n: int = 1):
    """Rolls the billing period over if it's elapsed, then checks and consumes
    n units of this period's AI-email quota. Raises 402 if it would exceed
    the plan's limit — called before any OpenAI call, so we never bill an
    email generation that wasn't actually allowed."""
    db = db_session()
    try:
        sub = db.query(Subscription).first()
        if not sub:
            return  # no subscription row (shouldn't happen once seeded) — fail open rather than block everyone
        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        if not plan:
            return

        if sub.current_period_end and datetime.now(timezone.utc).replace(tzinfo=None) > sub.current_period_end:
            sub.current_period_start = datetime.utcnow()
            sub.current_period_end = datetime.utcnow() + timedelta(days=30)
            sub.ai_emails_used_this_period = 0

        if sub.ai_emails_used_this_period + n > plan.ai_email_quota_monthly:
            db.commit()  # persist any rollover that just happened even though this request is being rejected
            raise HTTPException(
                402,
                f"This would exceed your {plan.name} plan's AI email quota "
                f"({sub.ai_emails_used_this_period}/{plan.ai_email_quota_monthly} used this period). "
                "An admin can upgrade the plan in Settings → Billing.",
            )
        sub.ai_emails_used_this_period += n
        db.commit()
    finally:
        db.close()


class AgentRequest(BaseModel):
    customer_data: dict
    shap_explanations: dict


@app.post("/execute_agent")
def execute_agent(req: AgentRequest, current_user: str = Depends(get_current_user)):
    _consume_ai_email_quota()
    result = _generate_email_draft(req.customer_data, req.shap_explanations)
    return {"status": "success", "source": result["source"], "email_draft": f"{result['subject']}\n\n{result['body']}"}


# ── Email drafts (compose / save / send) ──────────────────────────────────
def _customer_context(customer_id: str) -> tuple[dict, dict]:
    """Returns (customer_data, shap_explanations) for a customer, or 404s."""
    df = _scored_customers_df()
    row = df[df["customer_id"] == customer_id] if not df.empty else df
    if row.empty:
        raise HTTPException(404, "Customer not found or not yet scored")
    record = row.iloc[0].to_dict()
    return (
        {"name": record["name"], "email": record["email"], "churn_risk_score": record["churn_risk_score"]},
        record.get("shap_explanations") or {},
    )


class EmailGenerateRequest(BaseModel):
    customer_id: str
    tone: str = "professional"
    length: str = "medium"


@app.post("/emails/generate")
def generate_email(req: EmailGenerateRequest, current_user: str = Depends(get_current_user)):
    customer_data, shap_explanations = _customer_context(req.customer_id)
    _consume_ai_email_quota()
    return _generate_email_draft(customer_data, shap_explanations, req.tone, req.length)


class EmailBatchGenerateRequest(BaseModel):
    min_risk: float
    max_risk: float
    tone: str = "professional"
    length: str = "medium"
    max_customers: int = 7  # a deliberately small default — see rationale in the endpoint docstring


@app.post("/emails/generate_batch")
def generate_email_batch(req: EmailBatchGenerateRequest, current_user: str = Depends(get_current_user)):
    """Generates (and saves as drafts, NOT sent) one email per customer in a
    risk-score range, capped at max_customers. Deliberately small batches —
    this exists so a human can review a coherent, same-strategy group before
    anything goes out, not to auto-blast an entire risk tier unreviewed.
    Skips customers who already have an unsent draft, so re-running this
    doesn't create duplicates."""
    if not 0 <= req.min_risk < req.max_risk <= 1:
        raise HTTPException(400, "min_risk must be less than max_risk, both between 0 and 1")
    if req.max_customers > 7:
        raise HTTPException(400, "Batches are capped at 7 customers — generate another batch for the rest, "
                                  "so each group stays small enough to actually review before sending.")

    df = _scored_customers_df()
    in_range = df[(df["churn_risk_score"] >= req.min_risk) & (df["churn_risk_score"] <= req.max_risk)] if not df.empty else df
    if in_range.empty:
        return {"generated": 0, "skipped": 0, "drafts": [], "message": "No customers in that risk range."}

    db = db_session()
    try:
        already_drafted = {
            row.customer_id for row in
            db.query(EmailDraft.customer_id).filter(
                EmailDraft.customer_id.in_(in_range["customer_id"].tolist()),
                EmailDraft.status == "draft",
            ).all()
        }
        candidates = in_range[~in_range["customer_id"].isin(already_drafted)].head(req.max_customers)
        skipped = len(in_range) - len(candidates)
        if candidates.empty:
            return {"generated": 0, "skipped": skipped, "drafts": [],
                     "message": "Everyone in that range already has an unsent draft. Nothing new to generate."}

        _consume_ai_email_quota(len(candidates))  # check the WHOLE batch fits before generating any of it

        results = []
        for record in candidates.to_dict(orient="records"):
            customer_data = {"name": record["name"], "email": record["email"], "churn_risk_score": record["churn_risk_score"]}
            shap = record.get("shap_explanations") or {}
            gen = _generate_email_draft(customer_data, shap, req.tone, req.length)
            draft = EmailDraft(
                customer_id=record["customer_id"], subject=gen["subject"], body=gen["body"],
                tone=req.tone, length=req.length, created_by=current_user,
            )
            db.add(draft)
            db.flush()
            results.append(_draft_to_dict(draft))
        db.commit()
        return {"generated": len(results), "skipped": skipped, "drafts": results}
    finally:
        db.close()


class EmailDraftCreate(BaseModel):
    customer_id: str
    subject: str
    body: str
    tone: str = "professional"
    length: str = "medium"


class EmailDraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    tone: Optional[str] = None
    length: Optional[str] = None


def _draft_to_dict(d: EmailDraft) -> dict:
    return {
        "id": d.id, "customer_id": d.customer_id, "subject": d.subject, "body": d.body,
        "tone": d.tone, "length": d.length, "status": d.status, "created_by": d.created_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "sent_at": d.sent_at.isoformat() if d.sent_at else None,
    }


@app.post("/emails/drafts")
def create_draft(payload: EmailDraftCreate, current_user: str = Depends(get_current_user)):
    _customer_context(payload.customer_id)  # 404s if the customer doesn't exist / isn't scored
    db = db_session()
    try:
        draft = EmailDraft(
            customer_id=payload.customer_id, subject=payload.subject, body=payload.body,
            tone=payload.tone, length=payload.length, created_by=current_user,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return _draft_to_dict(draft)
    finally:
        db.close()


@app.get("/emails/drafts")
def list_drafts(customer_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        q = db.query(EmailDraft)
        if customer_id:
            q = q.filter(EmailDraft.customer_id == customer_id)
        drafts = q.order_by(EmailDraft.updated_at.desc()).all()
        return {"count": len(drafts), "drafts": [_draft_to_dict(d) for d in drafts]}
    finally:
        db.close()


def _get_draft_or_404(db: Session, draft_id: str) -> EmailDraft:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


@app.get("/emails/drafts/{draft_id}")
def get_draft(draft_id: str, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        return _draft_to_dict(_get_draft_or_404(db, draft_id))
    finally:
        db.close()


@app.put("/emails/drafts/{draft_id}")
def update_draft(draft_id: str, payload: EmailDraftUpdate, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        draft = _get_draft_or_404(db, draft_id)
        if draft.status == "sent":
            raise HTTPException(400, "Can't edit a draft that's already been sent")
        for field in ("subject", "body", "tone", "length"):
            value = getattr(payload, field)
            if value is not None:
                setattr(draft, field, value)
        db.commit()
        db.refresh(draft)
        return _draft_to_dict(draft)
    finally:
        db.close()


@app.delete("/emails/drafts/{draft_id}")
def delete_draft(draft_id: str, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        draft = _get_draft_or_404(db, draft_id)
        db.delete(draft)
        db.commit()
        return {"deleted": True, "id": draft_id}
    finally:
        db.close()


@app.post("/emails/drafts/{draft_id}/send_test")
def send_test_draft(draft_id: str, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        draft = _get_draft_or_404(db, draft_id)
        ok, detail = _send_smtp_email(current_user, f"[TEST] {draft.subject}", draft.body)
        if not ok:
            raise HTTPException(502, detail)
        return {"sent": True, "to": current_user, "detail": detail}
    finally:
        db.close()


@app.post("/emails/drafts/{draft_id}/send")
def send_draft(draft_id: str, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        draft = _get_draft_or_404(db, draft_id)
        if draft.status == "sent":
            raise HTTPException(400, "This draft has already been sent")
        customer_data, _ = _customer_context(draft.customer_id)
        ok, detail = _send_smtp_email(customer_data["email"], draft.subject, draft.body)
        if not ok:
            raise HTTPException(502, detail)
        draft.status = "sent"
        draft.sent_at = datetime.now(timezone.utc)
        db.commit()
        return {"sent": True, "to": customer_data["email"], "detail": detail}
    finally:
        db.close()


# ── Alerts ────────────────────────────────────────────────────────────────
def _send_slack_alert(webhook_url: str, high_risk_df: pd.DataFrame) -> bool:
    lines = [f"*RetainAI high-risk alert* — {len(high_risk_df)} customers above threshold:"]
    for _, r in high_risk_df.head(10).iterrows():
        lines.append(f"- {r['name']} ({r['email']}) — {round(r['churn_risk_score']*100)}% risk")
    try:
        resp = requests.post(webhook_url, json={"text": "\n".join(lines)}, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _send_email_alert(high_risk_df: pd.DataFrame) -> tuple[bool, str]:
    to_addr = os.environ.get("ALERT_EMAIL_TO")
    if not to_addr:
        return False, "not configured (set ALERT_EMAIL_TO)"

    count = len(high_risk_df)
    subject = f"RetainAI Alert: {count} customers at high churn risk"
    plain_body = f"RetainAI High-Risk Alert\n\n{count} customers are currently above the high-risk threshold:\n\n"
    plain_body += "\n".join(
        f"• {r.get('name', 'Customer')} ({r.get('email', 'N/A')}) — {round(float(r.get('churn_risk_score', 0)) * 100)}% risk"
        for _, r in high_risk_df.head(20).iterrows()
    )
    if count > 20:
        plain_body += f"\n\n... and {count - 20} more customers. View all in RetainAI Dashboard."

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155;">
    <h2 style="color: #f43f5e; margin-top: 0;">⚠️ RetainAI High-Risk Churn Alert</h2>
    <p style="color: #94a3b8; font-size: 14px;"><strong>{count}</strong> customers are currently flagged as high churn risk.</p>
    <table style="width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px;">
      <thead>
        <tr style="border-bottom: 1px solid #475569; text-align: left; color: #94a3b8;">
          <th style="padding: 8px;">Customer</th>
          <th style="padding: 8px;">Email</th>
          <th style="padding: 8px; text-align: right;">Risk Score</th>
        </tr>
      </thead>
      <tbody>
"""
    for _, r in high_risk_df.head(15).iterrows():
        score_pct = round(float(r.get('churn_risk_score', 0)) * 100)
        html_body += f"""
        <tr style="border-bottom: 1px solid #334155;">
          <td style="padding: 8px; color: #f1f5f9;">{r.get('name', 'N/A')}</td>
          <td style="padding: 8px; color: #94a3b8;">{r.get('email', 'N/A')}</td>
          <td style="padding: 8px; text-align: right; color: #f43f5e; font-weight: bold;">{score_pct}%</td>
        </tr>"""
    html_body += """
      </tbody>
    </table>
    <p style="margin-top: 20px; font-size: 12px; color: #64748b;">
      Generated automatically by RetainAI Intelligent Churn Prevention System.
    </p>
  </div>
</body>
</html>"""

    return _send_smtp_email(to_addr, subject, plain_body, html_body)


@app.post("/alerts/high_risk/run")
def run_high_risk_alert(threshold: Optional[float] = None, current_user: str = Depends(get_current_admin)):
    threshold = threshold if threshold is not None else get_high_risk_threshold()
    df = _scored_customers_df()
    high_risk_df = df[df["churn_risk_score"] > threshold] if not df.empty else df
    if high_risk_df.empty:
        return {"sent": False, "reason": "No customers above threshold", "count": 0}

    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    slack_sent = _send_slack_alert(slack_webhook, high_risk_df) if slack_webhook else None
    email_ok, email_detail = _send_email_alert(high_risk_df)
    return {
        "count": len(high_risk_df),
        "slack": "sent" if slack_sent else ("failed" if slack_sent is False else "not configured (set SLACK_WEBHOOK_URL)"),
        "email": "sent" if email_ok else email_detail,
    }


REPORT_TYPES = {
    "churn_overview": "Churn Overview",
    "customer_risk": "Customer Risk Report",
    "revenue_at_risk": "Revenue at Risk",
    "model_performance": "ML Model Performance",
    "retention_campaign": "Retention Campaign Report",
}


def _risk_tier(score: float) -> str:
    return "low" if score < 0.33 else "medium" if score < 0.66 else "high"


def _customer_mrr_estimates(db: Session) -> dict:
    """Approximates each customer's MRR from their recent successful payments,
    since there's no stored subscription-price field. Documented assumption:
    average of 'succeeded' payment_events amounts in the last 90 days."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    rows = (
        db.query(PaymentEvent.customer_id, PaymentEvent.amount)
        .filter(PaymentEvent.status == "succeeded", PaymentEvent.occurred_at >= cutoff)
        .all()
    )
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=["customer_id", "amount"])
    return df.groupby("customer_id")["amount"].mean().round(2).to_dict()


def _generate_report_data(report_type: str, start: Optional[date], end: Optional[date], db: Session) -> dict:
    if report_type == "churn_overview":
        df = _scored_customers_df()
        if start or end:
            roster = pd.read_sql(text("SELECT customer_id, signup_date FROM ml_customers"), engine)
            if start:
                roster = roster[roster["signup_date"] >= start]
            if end:
                roster = roster[roster["signup_date"] <= end]
            df = df[df["customer_id"].isin(roster["customer_id"])]
        if df.empty:
            return {"total_customers": 0, "avg_churn_score": 0.0, "high_risk_count": 0, "risk_distribution": {}, "top_driver_breakdown": {}}
        buckets = {"low": 0, "medium": 0, "high": 0}
        for score in df["churn_risk_score"]:
            buckets[_risk_tier(score)] += 1
        return {
            "total_customers": len(df),
            "avg_churn_score": round(float(df["churn_risk_score"].mean()), 4),
            "high_risk_count": int((df["churn_risk_score"] >= 0.66).sum()),
            "risk_distribution": buckets,
            "top_driver_breakdown": df["top_driver"].value_counts().to_dict(),
        }

    if report_type == "customer_risk":
        df = _scored_customers_df()
        if start or end:
            roster = pd.read_sql(text("SELECT customer_id, signup_date FROM ml_customers"), engine)
            if start:
                roster = roster[roster["signup_date"] >= start]
            if end:
                roster = roster[roster["signup_date"] <= end]
            df = df[df["customer_id"].isin(roster["customer_id"])]
        owners = _owners_map(db)
        rows = []
        for r in df.to_dict(orient="records"):
            rows.append({
                "customer_id": r["customer_id"], "name": r["name"], "email": r["email"],
                "churn_risk_score": round(r["churn_risk_score"], 4), "risk_tier": _risk_tier(r["churn_risk_score"]),
                "top_driver": r.get("top_driver"), "owner_email": owners.get(r["customer_id"]),
            })
        return {"count": len(rows), "customers": rows}

    if report_type == "revenue_at_risk":
        df = _scored_customers_df()
        mrr = _customer_mrr_estimates(db)
        rows, total_mrr, at_risk_mrr = [], 0.0, 0.0
        for r in df.to_dict(orient="records"):
            estimate = mrr.get(r["customer_id"], 0.0)
            total_mrr += estimate
            if r["churn_risk_score"] >= 0.66:
                at_risk_mrr += estimate
            rows.append({
                "customer_id": r["customer_id"], "name": r["name"],
                "churn_risk_score": round(r["churn_risk_score"], 4),
                "estimated_mrr": round(estimate, 2),
            })
        return {
            "assumption": "estimated_mrr = avg of successful payments in the last 90 days per customer; "
                           "customers with no successful payment in that window show $0.",
            "total_estimated_mrr": round(total_mrr, 2),
            "estimated_mrr_at_risk": round(at_risk_mrr, 2),
            "customers": sorted(rows, key=lambda r: r["churn_risk_score"], reverse=True),
        }

    if report_type == "model_performance":
        if not os.path.exists(META_PATH):
            return {"available": False, "reason": "No model_metadata.json found — train a model first."}
        with open(META_PATH) as f:
            meta = json.load(f)
        return {
            "available": True,
            "model_version": meta.get("model_version"),
            "trained_at": meta.get("trained_at"),
            "training_row_count": meta.get("row_count"),
            "roc_auc": meta.get("auc"),
            "precision": meta.get("precision"),
            "recall": meta.get("recall"),
            "note": "Accuracy/F1 aren't recorded by the current training script — only what train_model.py wrote is shown here.",
        }

    if report_type == "retention_campaign":
        q = db.query(EmailDraft)
        if start:
            q = q.filter(EmailDraft.created_at >= datetime.combine(start, datetime.min.time()))
        if end:
            q = q.filter(EmailDraft.created_at <= datetime.combine(end, datetime.max.time()))
        drafts = q.all()
        tone_counts: dict = {}
        for d in drafts:
            tone_counts[d.tone] = tone_counts.get(d.tone, 0) + 1
        sent = [d for d in drafts if d.status == "sent"]
        # For sent drafts, show the customer's CURRENT score as a (rough, not causal) follow-up signal.
        current_scores = _scored_customers_df().set_index("customer_id")["churn_risk_score"].to_dict() if not _scored_customers_df().empty else {}
        return {
            "total_drafts": len(drafts),
            "sent_count": len(sent),
            "tone_breakdown": tone_counts,
            "sent_emails": [
                {
                    "customer_id": d.customer_id, "subject": d.subject, "tone": d.tone,
                    "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                    "current_churn_risk_score": current_scores.get(d.customer_id),
                }
                for d in sent
            ],
        }

    raise HTTPException(400, f"Unknown report_type '{report_type}'. Valid types: {list(REPORT_TYPES)}")


class ReportGenerateRequest(BaseModel):
    report_type: str
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None


def _report_to_dict(r: Report, include_result: bool = True) -> dict:
    out = {
        "id": r.id, "report_type": r.report_type, "name": r.name, "status": r.status,
        "created_by": r.created_by, "created_at": r.created_at.isoformat() if r.created_at else None,
        "date_range_start": r.date_range_start.isoformat() if r.date_range_start else None,
        "date_range_end": r.date_range_end.isoformat() if r.date_range_end else None,
    }
    if include_result:
        out["result"] = json.loads(r.result_json)
    return out


@app.post("/reports/generate")
def generate_report(payload: ReportGenerateRequest, current_user: str = Depends(get_current_user)):
    if payload.report_type not in REPORT_TYPES:
        raise HTTPException(400, f"Unknown report_type. Valid types: {list(REPORT_TYPES)}")
    db = db_session()
    try:
        try:
            result = _generate_report_data(payload.report_type, payload.date_range_start, payload.date_range_end, db)
            status = "completed"
        except HTTPException:
            raise
        except Exception as e:
            logging.exception("Report generation failed")
            result, status = {"error": str(e)}, "failed"

        report = Report(
            report_type=payload.report_type, name=REPORT_TYPES[payload.report_type],
            date_range_start=payload.date_range_start, date_range_end=payload.date_range_end,
            status=status, created_by=current_user, result_json=json.dumps(result),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        if status == "failed":
            raise HTTPException(502, "Report generation failed — see report history for details.")
        return _report_to_dict(report)
    finally:
        db.close()


@app.get("/reports")
def list_reports(current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        reports = db.query(Report).order_by(Report.created_at.desc()).all()
        return {"count": len(reports), "reports": [_report_to_dict(r, include_result=False) for r in reports]}
    finally:
        db.close()


def _get_report_or_404(db: Session, report_id: int) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    return report


@app.get("/reports/{report_id}")
def get_report(report_id: int, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        return _report_to_dict(_get_report_or_404(db, report_id))
    finally:
        db.close()


@app.delete("/reports/{report_id}")
def delete_report(report_id: int, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        report = _get_report_or_404(db, report_id)
        db.delete(report)
        db.commit()
        return {"deleted": True, "id": report_id}
    finally:
        db.close()


@app.get("/reports/{report_id}/export")
def export_report_csv(report_id: int, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        report = _get_report_or_404(db, report_id)
        result = json.loads(report.result_json)
    finally:
        db.close()

    # Pick the tabular part of each report type; everything else becomes summary rows.
    table_key = {"customer_risk": "customers", "revenue_at_risk": "customers", "retention_campaign": "sent_emails"}.get(report.report_type)
    if table_key and result.get(table_key):
        export_df = pd.DataFrame(result[table_key])
    else:
        metric_rows = []
        for k, v in result.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    metric_rows.append({"metric": f"{k}.{sub_k}", "value": sub_v})
            elif not isinstance(v, list):
                metric_rows.append({"metric": k, "value": v})
        export_df = pd.DataFrame(metric_rows)

    buf = io.StringIO()
    export_df.to_csv(buf, index=False)
    buf.seek(0)
    filename = f"{report.report_type}_{report.id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _build_excel_attachment(report_name: str, result: dict) -> bytes:
    """Build a styled Excel workbook from report result and return as bytes."""
    wb = openpyxl.Workbook()

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="0E7490")
    subheader_fill = PatternFill("solid", fgColor="1E293B")
    subheader_font = Font(bold=True, color="94A3B8", size=10)
    title_font = Font(bold=True, color="06B6D4", size=14)
    center = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        bottom=Side(style="thin", color="334155"),
        right=Side(style="thin", color="334155"),
    )

    # Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.column_dimensions["A"].width = 32
    ws_summary.column_dimensions["B"].width = 24

    ws_summary["A1"] = f"RetainAI — {report_name}"
    ws_summary["A1"].font = title_font
    ws_summary["A2"] = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    ws_summary["A2"].font = Font(color="64748B", size=10)
    ws_summary.row_dimensions[1].height = 28

    ws_summary["A4"] = "Metric"
    ws_summary["B4"] = "Value"
    for cell in [ws_summary["A4"], ws_summary["B4"]]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    row = 5
    for k, v in result.items():
        if isinstance(v, (int, float, str, bool)) and not isinstance(v, dict):
            ws_summary.cell(row=row, column=1, value=k.replace("_", " ").title()).border = thin_border
            ws_summary.cell(row=row, column=2, value=v).border = thin_border
            row += 1
        elif isinstance(v, list):
            ws_summary.cell(row=row, column=1, value=k.replace("_", " ").title()).border = thin_border
            ws_summary.cell(row=row, column=2, value=f"{len(v)} records").border = thin_border
            row += 1

    # Data sheets — one per list key in result
    for key, records in result.items():
        if not isinstance(records, list) or not records:
            continue
        sheet_name = key.replace("_", " ").title()[:31]
        ws = wb.create_sheet(title=sheet_name)
        if not records:
            continue
        cols = list(records[0].keys()) if isinstance(records[0], dict) else ["value"]
        for ci, col in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(ci)].width = max(16, len(str(col)) + 4)
            cell = ws.cell(row=1, column=ci, value=col.replace("_", " ").title())
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border
        for ri, record in enumerate(records, 2):
            if isinstance(record, dict):
                for ci, col in enumerate(cols, 1):
                    c = ws.cell(row=ri, column=ci, value=record.get(col, ""))
                    c.border = thin_border
                    if ri % 2 == 0:
                        c.fill = PatternFill("solid", fgColor="0F172A")
            else:
                ws.cell(row=ri, column=1, value=record).border = thin_border

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _send_smtp_email_with_attachment(
    to_addr: str, subject: str, plain_body: str, html_body: str,
    attachment_bytes: bytes, attachment_filename: str
) -> tuple[bool, str]:
    host, user = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM", user)
    port = int(os.environ.get("SMTP_PORT", "587"))
    if not all([host, user, password, to_addr]):
        return False, "SMTP not configured"

    from email.mime.multipart import MIMEMultipart

    outer = MIMEMultipart("mixed")
    outer["Subject"] = subject
    outer["From"] = from_addr
    outer["To"] = to_addr

    # Attach text + html as alternatives
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    outer.attach(alt)

    # Attach Excel file
    part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    part.set_payload(attachment_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
    outer.attach(part)

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], outer.as_string())
        return True, "sent"
    except Exception as e:
        logging.warning(f"SMTP send failed: {e}")
        return False, f"send failed: {e}"


class EmailReportRequest(BaseModel):
    to_email: str


@app.post("/reports/{report_id}/email")
def email_report(report_id: int, req: EmailReportRequest, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        report = _get_report_or_404(db, report_id)
        result = json.loads(report.result_json) if report.result_json else {}

        generated_at = report.created_at.strftime("%B %d, %Y at %H:%M UTC") if report.created_at else "N/A"
        generated_at_short = report.created_at.strftime("%Y-%m-%d %H:%M UTC") if report.created_at else "N/A"

        # ── Plain text body ──────────────────────────────────────────────────
        summary_lines = []
        for k, v in result.items():
            if isinstance(v, (int, float, str, bool)) and not isinstance(v, dict):
                summary_lines.append(f"  • {k.replace('_', ' ').title()}: {v}")
            elif isinstance(v, list):
                summary_lines.append(f"  • {k.replace('_', ' ').title()}: {len(v)} records")

        summary_text = "\n".join(summary_lines) or "  (Full details in the attached Excel file)"
        plain_body = (
            f"Hello,\n\n"
            f"Your RetainAI report \"{report.name}\" is ready.\n\n"
            f"Report Summary:\n{summary_text}\n\n"
            f"Generated: {generated_at_short}\n"
            f"Status: {report.status.upper()}\n\n"
            f"The full data is attached as an Excel (.xlsx) file.\n\n"
            f"— RetainAI Automated System"
        )

        # ── HTML body (fully responsive, email-client-safe) ──────────────────
        metric_rows_html = ""
        for k, v in result.items():
            if isinstance(v, dict):
                continue
            display_val = f"{len(v)} records" if isinstance(v, list) else str(v)
            label = k.replace("_", " ").title()
            metric_rows_html += f"""
            <tr>
              <td style="padding:10px 16px;color:#94a3b8;font-size:13px;border-bottom:1px solid #1e293b;white-space:nowrap">{label}</td>
              <td style="padding:10px 16px;color:#f1f5f9;font-size:13px;font-weight:600;border-bottom:1px solid #1e293b">{display_val}</td>
            </tr>"""

        if not metric_rows_html:
            metric_rows_html = '<tr><td colspan="2" style="padding:16px;color:#64748b;text-align:center;font-size:13px">See attached Excel file for full data.</td></tr>'

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta http-equiv="X-UA-Compatible" content="IE=edge"/>
  <title>RetainAI Report</title>
  <!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0f172a">
    <tr>
      <td align="center" style="padding:32px 16px">
        <!--[if mso]><table role="presentation" border="0" cellspacing="0" cellpadding="0" width="600"><tr><td><![endif]-->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background-color:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #334155">

          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,#0e7490 0%,#065f46 100%);padding:36px 32px;text-align:center">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="text-align:center;padding-bottom:8px">
                    <span style="font-size:32px">&#128202;</span>
                  </td>
                </tr>
                <tr>
                  <td style="text-align:center">
                    <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;letter-spacing:-0.5px;line-height:1.3">RetainAI Report Ready</h1>
                    <p style="margin:8px 0 0;color:#a5f3fc;font-size:14px;line-height:1.4">{report.name}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- META INFO -->
          <tr>
            <td style="padding:24px 32px 8px">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0f172a;border-radius:10px;border:1px solid #334155">
                <tr>
                  <td style="padding:12px 16px;border-bottom:1px solid #1e293b">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="color:#64748b;font-size:12px;width:130px;white-space:nowrap">&#128100; Generated by</td>
                        <td style="color:#e2e8f0;font-size:13px;font-weight:600">{current_user}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:12px 16px;border-bottom:1px solid #1e293b">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="color:#64748b;font-size:12px;width:130px;white-space:nowrap">&#128197; Generated on</td>
                        <td style="color:#e2e8f0;font-size:13px;font-weight:600">{generated_at}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:12px 16px">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="color:#64748b;font-size:12px;width:130px;white-space:nowrap">&#9989; Status</td>
                        <td style="color:#10b981;font-size:13px;font-weight:700">{report.status.upper()}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- SUMMARY TABLE -->
          <tr>
            <td style="padding:16px 32px 8px">
              <p style="margin:0 0 12px;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Report Summary</p>
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0f172a;border-radius:10px;overflow:hidden;border:1px solid #334155">
                <tr style="background-color:#1e293b">
                  <th style="padding:10px 16px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Metric</th>
                  <th style="padding:10px 16px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Value</th>
                </tr>
                {metric_rows_html}
              </table>
            </td>
          </tr>

          <!-- ATTACHMENT NOTICE -->
          <tr>
            <td style="padding:16px 32px 8px">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0c2a1a;border:1px solid #065f46;border-radius:10px">
                <tr>
                  <td style="padding:14px 18px">
                    <p style="margin:0;color:#6ee7b7;font-size:13px">
                      &#128190;&nbsp;<strong>Excel file attached</strong> — Open the <em>.xlsx</em> attachment for the full dataset with multiple sheets.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- CTA BUTTON -->
          <tr>
            <td style="padding:24px 32px;text-align:center">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin:0 auto">
                <tr>
                  <td style="background-color:#0e7490;border-radius:10px;text-align:center">
                    <a href="http://localhost:5173" style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:14px;font-weight:700;text-decoration:none;border-radius:10px;line-height:1">
                      View Full Report &#8594;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="padding:20px 32px;border-top:1px solid #334155;text-align:center;background-color:#0f172a">
              <p style="margin:0;color:#475569;font-size:11px;line-height:1.6">
                RetainAI &bull; Automated Customer Retention Intelligence<br/>
                You&rsquo;re receiving this because a report was generated on your account.
              </p>
            </td>
          </tr>

        </table>
        <!--[if mso]></td></tr></table><![endif]-->
      </td>
    </tr>
  </table>
</body>
</html>"""

        # Build Excel attachment
        xlsx_bytes = _build_excel_attachment(report.name, result)
        safe_name = report.report_type.replace(" ", "_")
        ts = datetime.utcnow().strftime("%Y%m%d")
        attachment_filename = f"RetainAI_{safe_name}_{ts}.xlsx"

        ok, detail = _send_smtp_email_with_attachment(
            req.to_email, f"📊 RetainAI Report: {report.name}",
            plain_body, html_body, xlsx_bytes, attachment_filename
        )
        if not ok:
            raise HTTPException(500, f"Failed to send email: {detail}")
        return {"sent": ok, "detail": detail, "report_name": report.name, "attachment": attachment_filename}
    finally:
        db.close()


class ScheduledReportRequest(BaseModel):
    to_email: str
    frequency: str  # "daily" | "weekly" | "monthly"
    report_types: list[str]


@app.post("/reports/scheduled/send")
def send_scheduled_report(req: ScheduledReportRequest, current_user: str = Depends(get_current_user)):
    """Generate and immediately email a scheduled report bundle (daily/weekly/monthly)."""
    valid_types = set(REPORT_TYPES.keys())
    bad = [r for r in req.report_types if r not in valid_types]
    if bad:
        raise HTTPException(400, f"Unknown report types: {bad}. Valid: {list(valid_types)}")

    freq_labels = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}
    freq_label = freq_labels.get(req.frequency, req.frequency.title())

    db = db_session()
    try:
        generated_reports = []
        for rt in req.report_types:
            try:
                result = _generate_report_data(rt, None, None, db)
                report = Report(
                    report_type=rt, name=f"{freq_label} {REPORT_TYPES[rt]}",
                    status="completed", created_by=current_user, result_json=json.dumps(result),
                )
                db.add(report)
                db.commit()
                db.refresh(report)
                generated_reports.append((report, result))
            except Exception as e:
                logging.warning(f"Scheduled report {rt} failed: {e}")

        if not generated_reports:
            raise HTTPException(502, "All scheduled reports failed to generate.")

        # Bundle all into one multi-sheet Excel
        wb = openpyxl.Workbook()
        first = True
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill("solid", fgColor="0E7490")
        thin_border = Border(bottom=Side(style="thin", color="334155"), right=Side(style="thin", color="334155"))

        for report, result in generated_reports:
            # Summary sheet
            ws_name = report.report_type[:31]
            ws = wb.active if first else wb.create_sheet(title=ws_name)
            if first:
                ws.title = ws_name
                first = False

            ws["A1"] = f"RetainAI — {report.name}"
            ws["A1"].font = Font(bold=True, color="06B6D4", size=13)
            ws["A2"] = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            ws["A2"].font = Font(color="64748B", size=10)

            ws["A4"] = "Metric"
            ws["B4"] = "Value"
            ws["A4"].font = ws["B4"].font = header_font
            ws["A4"].fill = ws["B4"].fill = header_fill
            ws.column_dimensions["A"].width = 30
            ws.column_dimensions["B"].width = 22

            row = 5
            for k, v in result.items():
                if isinstance(v, (int, float, str, bool)) and not isinstance(v, dict):
                    ws.cell(row, 1, k.replace("_", " ").title()).border = thin_border
                    ws.cell(row, 2, v).border = thin_border
                    row += 1
                elif isinstance(v, list):
                    ws.cell(row, 1, k.replace("_", " ").title()).border = thin_border
                    ws.cell(row, 2, f"{len(v)} records").border = thin_border
                    row += 1

            # Data tabs
            for key, records in result.items():
                if not isinstance(records, list) or not records:
                    continue
                tab_name = f"{ws_name[:20]}_{key[:10]}"[:31]
                ws2 = wb.create_sheet(title=tab_name)
                cols = list(records[0].keys()) if isinstance(records[0], dict) else ["value"]
                for ci, col in enumerate(cols, 1):
                    ws2.column_dimensions[get_column_letter(ci)].width = max(16, len(str(col)) + 4)
                    c = ws2.cell(1, ci, col.replace("_", " ").title())
                    c.font = header_font
                    c.fill = header_fill
                    c.border = thin_border
                for ri, rec in enumerate(records, 2):
                    if isinstance(rec, dict):
                        for ci, col in enumerate(cols, 1):
                            ws2.cell(ri, ci, rec.get(col, "")).border = thin_border
                    else:
                        ws2.cell(ri, 1, rec).border = thin_border

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        xlsx_bytes = buf.read()

        ts = datetime.utcnow().strftime("%Y%m%d")
        attachment_filename = f"RetainAI_{freq_label}_Bundle_{ts}.xlsx"
        subject = f"📊 RetainAI {freq_label} Report Bundle — {datetime.utcnow().strftime('%b %d, %Y')}"

        report_names_html = "".join(f"<li style='margin:4px 0;color:#94a3b8;font-size:13px'>{r.name}</li>" for r, _ in generated_reports)

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>RetainAI {freq_label} Reports</title></head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:Arial,Helvetica,sans-serif">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0f172a">
    <tr><td align="center" style="padding:32px 16px">
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background-color:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #334155">
        <tr>
          <td style="background:linear-gradient(135deg,#0e7490 0%,#065f46 100%);padding:36px 32px;text-align:center">
            <span style="font-size:36px">&#128202;</span>
            <h1 style="margin:12px 0 0;color:#fff;font-size:22px;font-weight:800">{freq_label} Report Bundle</h1>
            <p style="margin:8px 0 0;color:#a5f3fc;font-size:14px">{datetime.utcnow().strftime('%B %d, %Y')}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px">
            <p style="margin:0 0 16px;color:#94a3b8;font-size:13px">Your <strong style="color:#e2e8f0">{freq_label.lower()}</strong> RetainAI report bundle is attached. It contains <strong style="color:#e2e8f0">{len(generated_reports)}</strong> report(s):</p>
            <ul style="margin:0 0 20px;padding-left:20px">{report_names_html}</ul>
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0c2a1a;border:1px solid #065f46;border-radius:10px;margin-bottom:24px">
              <tr><td style="padding:14px 18px">
                <p style="margin:0;color:#6ee7b7;font-size:13px">&#128190;&nbsp;<strong>Excel bundle attached</strong> — Each report has its own summary tab plus detailed data sheets.</p>
              </td></tr>
            </table>
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin:0 auto">
              <tr><td style="background-color:#0e7490;border-radius:10px;text-align:center">
                <a href="http://localhost:5173" style="display:inline-block;padding:14px 36px;color:#fff;font-size:14px;font-weight:700;text-decoration:none;border-radius:10px">View Dashboard &#8594;</a>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;border-top:1px solid #334155;text-align:center;background-color:#0f172a">
            <p style="margin:0;color:#475569;font-size:11px">RetainAI &bull; Automated Customer Retention Intelligence</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        plain_body = (
            f"RetainAI {freq_label} Report Bundle\n"
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"Reports included:\n" + "\n".join(f"  - {r.name}" for r, _ in generated_reports) +
            f"\n\nThe full data is in the attached Excel file.\n— RetainAI System"
        )

        ok, detail = _send_smtp_email_with_attachment(
            req.to_email, subject, plain_body, html_body, xlsx_bytes, attachment_filename
        )
        if not ok:
            raise HTTPException(500, f"Failed to send scheduled report: {detail}")
        return {
            "sent": ok, "detail": detail,
            "frequency": req.frequency,
            "reports_generated": len(generated_reports),
            "attachment": attachment_filename,
        }
    finally:
        db.close()


CSV_UPLOAD_REQUIRED_COLS = ["customer_id", "Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins", "Last_Support_Ticket"]
CSV_UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5MB
CSV_UPLOAD_MAX_ROWS = 5000
PREDICTIONS_THRESHOLDS = {"low": 0.30, "medium": 0.60, "high": 0.80}  # matches the spec's Low/Medium/High/Critical cutoffs


def _risk_level(p: float) -> str:
    if p < PREDICTIONS_THRESHOLDS["low"]:
        return "Low"
    if p < PREDICTIONS_THRESHOLDS["medium"]:
        return "Medium"
    if p < PREDICTIONS_THRESHOLDS["high"]:
        return "High"
    return "Critical"


@app.post("/predictions/validate")
async def validate_prediction_csv(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    """Column/shape check only — lets the frontend show a preview + clear
    errors before committing to a full prediction run."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")
    contents = await file.read()
    if len(contents) > CSV_UPLOAD_MAX_BYTES:
        raise HTTPException(400, f"File is too large — max {CSV_UPLOAD_MAX_BYTES // (1024*1024)}MB")
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(400, f"Couldn't parse CSV: {e}")

    missing = [c for c in CSV_UPLOAD_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"CSV validation failed. Missing required column(s): {', '.join(missing)}")
    if len(df) == 0:
        raise HTTPException(400, "CSV has no data rows")
    if len(df) > CSV_UPLOAD_MAX_ROWS:
        raise HTTPException(400, f"CSV has {len(df)} rows — max is {CSV_UPLOAD_MAX_ROWS} per upload")

    return {
        "valid": True, "row_count": len(df), "columns": list(df.columns),
        "preview": df.head(5).fillna("").to_dict(orient="records"),
    }


@app.post("/predictions/upload")
async def run_csv_prediction(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    """Runs the live model over an uploaded CSV. Stateless by design — this
    does NOT write to customer_predictions, which stays owned exclusively by
    pipeline.run_scoring_pass() on the live roster. Use this for one-off
    what-if datasets, not for updating a tracked customer's live score."""
    if pipeline._model is None:
        raise HTTPException(503, "No trained model is loaded — run train_model.py first.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")
    contents = await file.read()
    if len(contents) > CSV_UPLOAD_MAX_BYTES:
        raise HTTPException(400, f"File is too large — max {CSV_UPLOAD_MAX_BYTES // (1024*1024)}MB")
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(400, f"Couldn't parse CSV: {e}")

    missing = [c for c in CSV_UPLOAD_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"CSV validation failed. Missing required column(s): {', '.join(missing)}")
    if len(df) == 0:
        raise HTTPException(400, "CSV has no data rows")
    if len(df) > CSV_UPLOAD_MAX_ROWS:
        raise HTTPException(400, f"CSV has {len(df)} rows — max is {CSV_UPLOAD_MAX_ROWS} per upload")

    for col in ["Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad_rows = df[df[["Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins"]].isna().any(axis=1)]
    if not bad_rows.empty:
        bad_ids = bad_rows["customer_id"].astype(str).head(10).tolist()
        raise HTTPException(
            400,
            f"{len(bad_rows)} row(s) have non-numeric values in Account_Age_Days/Login_Frequency/Daily_Usage_Mins "
            f"(e.g. customer_id: {', '.join(bad_ids)})",
        )
    df["Last_Support_Ticket"] = df["Last_Support_Ticket"].apply(ticket_urgency_score)

    probabilities, top_drivers, shap_dicts = pipeline.score_dataframe(df[FEATURE_COLS])

    results = []
    for i, row in df.iterrows():
        p = float(probabilities[i])
        results.append({
            "customer_id": str(row["customer_id"]),
            "name": row.get("name", "") if "name" in df.columns else "",
            "churn_probability": round(p, 4),
            "risk_level": _risk_level(p),
            "confidence": round(max(p, 1 - p) * 100, 1),  # distance from the 50/50 decision boundary, as a %
            "top_driver": top_drivers[i],
            "shap_values": shap_dicts[i],
        })

    return {
        "row_count": len(results),
        "model_version": pipeline._model_version,
        "thresholds": PREDICTIONS_THRESHOLDS,
        "results": results,
    }


class AppSettingsUpdate(BaseModel):
    high_risk_threshold: float


@app.get("/settings/app")
def get_app_settings(current_user: str = Depends(get_current_user)):
    """Readable by any logged-in user (it affects what they see on the
    dashboard); only admins can change it — see PUT below."""
    return {
        "high_risk_threshold": get_high_risk_threshold(),
        "default_high_risk_threshold": DEFAULT_HIGH_RISK_THRESHOLD,
        "scoring_interval_seconds": SCORING_INTERVAL_SECONDS,  # informational — set at process start, not editable here
    }


@app.put("/settings/app")
def update_app_settings(payload: AppSettingsUpdate, current_user: str = Depends(get_current_admin)):
    if not 0 < payload.high_risk_threshold < 1:
        raise HTTPException(400, "high_risk_threshold must be between 0 and 1")
    db = db_session()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "high_risk_threshold").first()
        if row:
            row.value, row.updated_by = str(payload.high_risk_threshold), current_user
        else:
            db.add(AppSetting(key="high_risk_threshold", value=str(payload.high_risk_threshold), updated_by=current_user))
        db.commit()
    finally:
        db.close()
    cache.delete_cached("customers:scored")  # so the new threshold takes effect immediately, not after the 60s TTL
    return {"high_risk_threshold": payload.high_risk_threshold}


@app.get("/billing/plans")
def list_plans(current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        plans = db.query(Plan).all()
        return {"plans": [
            {
                "id": p.id, "name": p.name, "max_seats": p.max_seats,
                "max_tracked_customers": p.max_tracked_customers,
                "ai_email_quota_monthly": p.ai_email_quota_monthly,
                "price_cents_monthly": p.price_cents_monthly,
            }
            for p in plans
        ]}
    finally:
        db.close()


@app.get("/billing/subscription")
def get_subscription(current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        sub = db.query(Subscription).first()
        if not sub:
            raise HTTPException(404, "No subscription found — this shouldn't happen once seed_default_plans has run.")
        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        seats_used = db.query(User).count()
        tracked_customers = db.query(MLCustomer).count()
        return {
            "plan_id": sub.plan_id, "plan_name": plan.name if plan else sub.plan_id,
            "status": sub.status,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "ai_emails_used_this_period": sub.ai_emails_used_this_period,
            "ai_email_quota_monthly": plan.ai_email_quota_monthly if plan else None,
            "seats_used": seats_used, "max_seats": plan.max_seats if plan else None,
            "tracked_customers": tracked_customers,
            "max_tracked_customers": plan.max_tracked_customers if plan else None,
            "price_cents_monthly": plan.price_cents_monthly if plan else None,
        }
    finally:
        db.close()


class SubscriptionUpdate(BaseModel):
    plan_id: str


@app.put("/billing/subscription")
def update_subscription(payload: SubscriptionUpdate, current_user: str = Depends(get_current_admin)):
    """Swaps the active plan. NOTE: this does not touch a real payment
    processor — there's no Stripe (or other) integration wired up yet, so
    this only updates which limits apply. Actually collecting payment means
    adding the `stripe` SDK, a Checkout Session on upgrade, and a webhook
    handler for invoice/subscription events — none of which exists here."""
    db = db_session()
    try:
        plan = db.query(Plan).filter(Plan.id == payload.plan_id).first()
        if not plan:
            raise HTTPException(404, f"No such plan '{payload.plan_id}'")
        sub = db.query(Subscription).first()
        if not sub:
            raise HTTPException(404, "No subscription row exists")

        seats_used = db.query(User).count()
        if seats_used > plan.max_seats:
            raise HTTPException(
                400,
                f"Can't switch to {plan.name} — you have {seats_used} team members, "
                f"which is over its {plan.max_seats}-seat limit. Remove people from Team first.",
            )

        sub.plan_id = plan.id
        sub.updated_by = current_user
        db.commit()
        return {"plan_id": sub.plan_id}
    finally:
        db.close()


@app.post("/admin/rescore")
def trigger_rescore(current_user: str = Depends(get_current_admin)):
    import time
    start = time.time()
    n = pipeline.run_scoring_pass()
    cache.delete_cached("customers:scored")
    return {"message": "Scoring complete", "rows_scored": n, "duration_seconds": round(time.time() - start, 2)}


@app.post("/admin/snapshot_risk_scores")
def trigger_snapshot(current_user: str = Depends(get_current_admin)):
    import scoring
    db = db_session()
    try:
        return scoring.write_daily_snapshot(db)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
