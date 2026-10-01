"""
models.py — SQLAlchemy ORM models. Replaces the old raw sqlite3 tables.

RiskScoreSnapshot is the important new one: it stores one row per customer
per day, so /customers/{id}/risk_trend can read real recorded history
instead of reconstructing it from mock event data every request.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, UniqueConstraint, Boolean
from sqlalchemy.sql import func

from database import Base, User, CustomerNote, CustomerOwner, RiskScoreSnapshot
