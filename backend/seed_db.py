"""
seed_db.py — one-time seed of the ml_customers table from Database/test_.csv.

Converts each row's static Account_Age_Days into a signup_date, so age
keeps advancing naturally on every future query instead of being frozen
at whatever value was in the CSV.

Safe to re-run: skips seeding if ml_customers already has rows.
    python seed_db.py            # seed if empty
    python seed_db.py --force    # drop + reseed
"""
import os
import sys
import argparse
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import inspect, text

from database import engine, init_all_tables, MLCustomer, SessionLocal

CSV_PATH = os.path.join(os.path.dirname(__file__), "Database", "test_.csv")


def seed(force: bool = False):
    init_all_tables()
    insp = inspect(engine)

    if force:
        print("--force: clearing ml_customers ...")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM ml_customers"))

    with engine.connect() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM ml_customers")).scalar()
    if existing and existing > 0 and not force:
        print(f"ml_customers already has {existing} rows. Nothing to do (use --force to reseed).")
        return

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found.")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    today = date.today()

    db = SessionLocal()
    try:
        rows = []
        for _, r in df.iterrows():
            signup = today - timedelta(days=int(r["Account_Age_Days"]))
            rows.append(MLCustomer(
                customer_id=r["Customer_ID"],
                name=r["Name"],
                email=r["Email"],
                signup_date=signup,
                churn_label=int(r["Churn"]),
            ))
        db.bulk_save_objects(rows)
        db.commit()
        print(f"Seeded ml_customers with {len(rows)} customers.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    seed(force=args.force)
