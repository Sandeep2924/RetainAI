"""
database.py — single source of truth for the DB schema.

Everything lives in Postgres now (no more mockaroo_pull/*.csv files sitting
next to the DB). Real-time activity, users, notes, owners, and predictions
are all just tables here, and everything talks to them through SQLAlchemy —
no raw psycopg2 / no %s-placeholder SQL mixed in with ORM code.

Tables:
  users                — login accounts
  ml_customers         — the customer roster (seeded from CSV once)
  login_events         — one row per login (written by realtime.py)
  usage_events         — one row per usage/session event (written by realtime.py)
  support_tickets      — one row per support ticket (written by realtime.py)
  payment_events       — one row per payment/invoice event (written by realtime.py)
  customer_notes       — free-text notes a user leaves on a customer
  customer_owners      — which team member "owns" a customer account
  customer_predictions — latest churn score per customer (written by pipeline.py)
"""
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime, Text, Date, ForeignKey, text
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. RetainAI needs Postgres — set DATABASE_URL "
        "in backend/.env (see .env.example)."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, default="")
    job_title = Column(String, default="")
    company_name = Column(String, default="")
    avatar_url = Column(String, default="")
    preferences = Column(Text, default="{}")
    role = Column(String, nullable=False, default="member")  # "member" | "admin"


class MLCustomer(Base):
    """The customer roster. Account_Age_Days is DERIVED from signup_date at
    query time (see pipeline.py) instead of stored as a static number that
    goes stale — one less thing to keep in sync."""
    __tablename__ = "ml_customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    signup_date = Column(Date, nullable=False)
    churn_label = Column(Integer, nullable=True)  # historical label, training only


class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, ForeignKey("ml_customers.customer_id"), index=True, nullable=False)
    login_at = Column(DateTime, nullable=False, index=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, ForeignKey("ml_customers.customer_id"), index=True, nullable=False)
    occurred_at = Column(DateTime, nullable=False, index=True)
    duration_secs = Column(Float, nullable=False)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, ForeignKey("ml_customers.customer_id"), index=True, nullable=False)
    created_at = Column(DateTime, nullable=False, index=True)
    subject = Column(Text, nullable=False)


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, ForeignKey("ml_customers.customer_id"), index=True, nullable=False)
    occurred_at = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # succeeded / failed / refunded


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, index=True, nullable=False)
    author = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class CustomerOwner(Base):
    __tablename__ = "customer_owners"

    customer_id = Column(String, primary_key=True)
    owner_email = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class CustomerPrediction(Base):
    """One row per customer. Upserted by pipeline.run_scoring_pass().
    API endpoints only ever READ this table — they never run the model
    themselves, so a request is always fast regardless of dataset size."""
    __tablename__ = "customer_predictions"

    customer_id = Column(String, primary_key=True)
    churn_probability = Column(Float, nullable=False)
    top_driver = Column(String, nullable=True)
    shap_values = Column(Text, nullable=True)  # JSON-encoded {feature: value}
    scored_at = Column(DateTime, default=_utcnow)
    model_version = Column(String, nullable=True)


class EmailDraft(Base):
    """A retention email drafted (by AI or by hand) for a customer.
    Lives independently of CustomerNote — this is a compose/send workflow,
    not a log entry."""
    __tablename__ = "email_drafts"

    id = Column(Integer, primary_key=True)
    customer_id = Column(String, ForeignKey("ml_customers.customer_id"), index=True, nullable=False)
    subject = Column(String, nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    tone = Column(String, nullable=False, default="professional")  # professional | friendly | empathetic | urgent
    length = Column(String, nullable=False, default="medium")  # short | medium | long
    status = Column(String, nullable=False, default="draft")  # draft | sent
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    sent_at = Column(DateTime, nullable=True)


class Report(Base):
    """A generated analytics report, snapshotted at generation time.
    `result_json` holds the full payload so re-opening a report later shows
    exactly what was true when it was generated, not live numbers."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    report_type = Column(String, nullable=False)  # churn_overview | customer_risk | revenue_at_risk | model_performance | retention_campaign
    name = Column(String, nullable=False)
    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)
    status = Column(String, nullable=False, default="completed")  # completed | failed
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    result_json = Column(Text, nullable=False, default="{}")


class AppSetting(Base):
    """A small admin-managed key/value store for global settings that need to
    change at runtime without a redeploy (e.g. the org-wide high-risk alert
    threshold). Not for per-user preferences — those live on User.preferences."""
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    updated_by = Column(String, nullable=True)


class Plan(Base):
    """A billing tier's limits and price. Seeded with 3 defaults at startup
    (see seed_default_plans) — not user-editable, since changing what a
    plan includes should be a deliberate product decision, not a runtime
    setting."""
    __tablename__ = "plans"

    id = Column(String, primary_key=True)  # "starter" | "growth" | "enterprise"
    name = Column(String, nullable=False)
    max_seats = Column(Integer, nullable=False)
    max_tracked_customers = Column(Integer, nullable=False)
    ai_email_quota_monthly = Column(Integer, nullable=False)
    price_cents_monthly = Column(Integer, nullable=False)


class Subscription(Base):
    """There is exactly one row in this table — this app has no
    multi-tenancy, so there's one subscription for the whole deployed
    instance, not one per company using it. Modeling per-tenant billing
    would require a real Organization/Account layer first."""
    __tablename__ = "subscription"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    status = Column(String, nullable=False, default="active")  # active | past_due | canceled
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    current_period_start = Column(DateTime, default=_utcnow)
    current_period_end = Column(DateTime, nullable=True)
    ai_emails_used_this_period = Column(Integer, nullable=False, default=0)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


def seed_default_plans():
    """Idempotent — safe to call on every startup. Inserts the 3 default
    plans and a starter subscription if none exists yet."""
    db = SessionLocal()
    try:
        defaults = [
            Plan(id="starter", name="Starter", max_seats=3, max_tracked_customers=500,
                 ai_email_quota_monthly=50, price_cents_monthly=9900),
            Plan(id="growth", name="Growth", max_seats=10, max_tracked_customers=5000,
                 ai_email_quota_monthly=500, price_cents_monthly=49900),
            Plan(id="enterprise", name="Enterprise", max_seats=999999, max_tracked_customers=999999,
                 ai_email_quota_monthly=999999, price_cents_monthly=0),  # 0 = "contact sales", not free
        ]
        for plan in defaults:
            if not db.query(Plan).filter(Plan.id == plan.id).first():
                db.add(plan)
        db.commit()

        if not db.query(Subscription).first():
            db.add(Subscription(plan_id="starter", status="active",
                                 current_period_start=_utcnow(),
                                 current_period_end=_utcnow() + timedelta(days=30)))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_all_tables():
    """Create every table if it doesn't exist yet. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)
    # `role` was added after `users` originally shipped — create_all() only creates
    # missing *tables*, not missing *columns* on an existing one, so patch it in
    # directly for anyone upgrading an already-seeded database.
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'member'"
        ))
