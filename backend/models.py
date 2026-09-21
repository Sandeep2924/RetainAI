"""
models.py — SQLAlchemy ORM models. Replaces the old raw sqlite3 tables.

RiskScoreSnapshot is the important new one: it stores one row per customer
per day, so /customers/{id}/risk_trend can read real recorded history
instead of reconstructing it from mock event data every request.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")  # "admin" or "member"
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, nullable=False, index=True)
    author = Column(String, nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomerOwner(Base):
    __tablename__ = "customer_owners"

    customer_id = Column(String, primary_key=True)
    owner_email = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RiskScoreSnapshot(Base):
    """One row per customer per day. Populated by the daily snapshot job
    (scripts/snapshot_risk_scores.py) or the admin-triggered endpoint."""
    __tablename__ = "risk_score_snapshots"
    __table_args__ = (UniqueConstraint("customer_id", "snapshot_date", name="uq_customer_day"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False)
    churn_risk_score = Column(Float, nullable=False)
    top_driver = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
