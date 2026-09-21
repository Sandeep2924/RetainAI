"""
scripts/snapshot_risk_scores.py — records today's churn risk score for every
customer, so /customers/{id}/risk_trend has real recorded history to read
instead of falling back to reconstruction from raw event logs.

Run once:
    python scripts/snapshot_risk_scores.py

Run continuously (for docker-compose, one snapshot per day):
    python scripts/snapshot_risk_scores.py --loop

This talks directly to the database and the model — no HTTP call, no auth
token needed — since it's meant to run as a trusted background job sharing
the same codebase and DATABASE_URL as the API.
"""

import os
import sys
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Base, engine
import models  # noqa: F401 — must import before create_all() so tables register
import scoring


def run_once():
    Base.metadata.create_all(bind=engine)
    scoring.load_model()
    db = SessionLocal()
    try:
        result = scoring.write_daily_snapshot(db)
        print(f"[{datetime.now().isoformat()}] snapshot done: {result}")
    finally:
        db.close()


def run_loop(interval_seconds: int):
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] snapshot failed: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run forever, once per day")
    parser.add_argument("--interval-hours", type=float, default=24, help="Hours between runs in --loop mode")
    args = parser.parse_args()

    if args.loop:
        run_loop(int(args.interval_hours * 3600))
    else:
        run_once()
