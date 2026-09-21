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
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone, date
from typing import Optional

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
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RetainAI")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model.pkl")
META_PATH = os.path.join(os.path.dirname(__file__), "..", "model_metadata.json")

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
def root():
    return {"message": "RetainAI backend is running", "docs": "/docs"}


# ── Auth endpoints ───────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str


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
        if db.query(User).filter(User.email == user.email).first():
            raise HTTPException(400, "Email already registered")

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

        role = "admin" if user.email.lower() in ADMIN_EMAILS else "member"
        db.add(User(email=user.email, hashed_password=hash_password(user.password), role=role))
        db.commit()
        return {"message": "User created successfully"}
    finally:
        db.close()


@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    db = db_session()
    try:
        user = db.query(User).filter(User.email == form.username).first()
        if not user or not verify_password(form.password, user.hashed_password):
            raise HTTPException(401, "Incorrect email or password")
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

    points = pipeline.get_customer_trend(customer_id, days)
    if points is None:
        raise HTTPException(404, "Customer not found")

    result = {"customer_id": customer_id, "trend": points}
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


def _get_draft_or_404(db: Session, draft_id: int) -> EmailDraft:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


@app.get("/emails/drafts/{draft_id}")
def get_draft(draft_id: int, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        return _draft_to_dict(_get_draft_or_404(db, draft_id))
    finally:
        db.close()


@app.put("/emails/drafts/{draft_id}")
def update_draft(draft_id: int, payload: EmailDraftUpdate, current_user: str = Depends(get_current_user)):
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
def delete_draft(draft_id: int, current_user: str = Depends(get_current_user)):
    db = db_session()
    try:
        draft = _get_draft_or_404(db, draft_id)
        db.delete(draft)
        db.commit()
        return {"deleted": True, "id": draft_id}
    finally:
        db.close()


def _send_smtp_email(to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    host, user = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    port = int(os.environ.get("SMTP_PORT", "587"))
    if not all([host, user, password, to_addr]):
        return False, "SMTP is not configured (set SMTP_HOST / SMTP_USER / SMTP_PASSWORD)"
    msg = MIMEText(body)
    msg["Subject"], msg["From"], msg["To"] = subject, user, to_addr
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True, "sent"
    except Exception as e:
        logging.warning(f"SMTP send failed: {e}")
        return False, f"send failed: {e}"


@app.post("/emails/drafts/{draft_id}/send_test")
def send_test_draft(draft_id: int, current_user: str = Depends(get_current_user)):
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
def send_draft(draft_id: int, current_user: str = Depends(get_current_user)):
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


def _send_email_alert(high_risk_df: pd.DataFrame) -> bool:
    host, user = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER")
    password, to_addr = os.environ.get("SMTP_PASSWORD"), os.environ.get("ALERT_EMAIL_TO")
    port = int(os.environ.get("SMTP_PORT", "587"))
    if not all([host, user, password, to_addr]):
        return False
    body = "\n".join(f"- {r['name']} ({r['email']}) — {round(r['churn_risk_score']*100)}% risk"
                      for _, r in high_risk_df.iterrows())
    msg = MIMEText(body)
    msg["Subject"] = f"RetainAI: {len(high_risk_df)} customers at high churn risk"
    msg["From"], msg["To"] = user, to_addr
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True
    except Exception:
        return False


@app.post("/alerts/high_risk/run")
def run_high_risk_alert(threshold: Optional[float] = None, current_user: str = Depends(get_current_admin)):
    threshold = threshold if threshold is not None else get_high_risk_threshold()
    df = _scored_customers_df()
    high_risk_df = df[df["churn_risk_score"] > threshold] if not df.empty else df
    if high_risk_df.empty:
        return {"sent": False, "reason": "No customers above threshold", "count": 0}

    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    slack_sent = _send_slack_alert(slack_webhook, high_risk_df) if slack_webhook else None
    email_sent = _send_email_alert(high_risk_df)
    return {
        "count": len(high_risk_df),
        "slack": "sent" if slack_sent else ("failed" if slack_sent is False else "not configured (set SLACK_WEBHOOK_URL)"),
        "email": "sent" if email_sent else "not configured (set SMTP_* vars)",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
