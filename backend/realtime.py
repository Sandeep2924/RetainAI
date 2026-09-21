"""
realtime.py — acts as a stream of fake customers, continuously generating
believable activity so the dashboard has something to react to.

Run as its own process, separate from the API:
    python realtime.py                  # runs forever, one event every ~2s
    python realtime.py --once           # write a single batch of events and exit
    python realtime.py --new-customers 5  # also add 5 brand-new fake customers first

It only ever WRITES raw activity (logins, usage, tickets, payments) to
Postgres. It never touches the model or the predictions table — that's
pipeline.py's job, running on its own schedule and picking up whatever
realtime.py has written since the last pass.
"""
import argparse
import random
import time
import uuid
from datetime import datetime, timedelta, date

from faker import Faker

from database import (
    SessionLocal, init_all_tables, MLCustomer, LoginEvent, UsageEvent,
    SupportTicket, PaymentEvent,
)

fake = Faker()

TICKET_SUBJECTS_NEUTRAL = [
    "How do I export my report to CSV?",
    "Is there a mobile app for this?",
    "Question about upgrading my plan",
    "Where can I find the API docs?",
    "Thanks for the quick help yesterday!",
]
TICKET_SUBJECTS_NEGATIVE = [
    "I've been waiting 3 days for a reply, this is unacceptable.",
    "The dashboard keeps throwing an error when I try to save.",
    "This is way too confusing, I can't find the export button.",
    "Thinking about cancelling, the last update broke my workflow.",
    "Why did my bill increase without any notice? I want a refund.",
]

PAYMENT_STATUSES = ["succeeded", "succeeded", "succeeded", "failed", "refunded"]


def add_fake_customers(db, n: int):
    created = []
    for _ in range(n):
        cid = str(uuid.uuid4())
        c = MLCustomer(
            customer_id=cid,
            name=fake.name(),
            email=fake.unique.email(),
            signup_date=date.today() - timedelta(days=random.randint(0, 30)),
            churn_label=None,  # unknown — this customer has no historical label
        )
        db.add(c)
        created.append(cid)
    db.commit()
    print(f"[realtime] added {n} new fake customers")
    return created


def emit_one_event(db, customer_ids):
    """Writes exactly one random event for a random existing customer."""
    if not customer_ids:
        return
    cid = random.choice(customer_ids)
    now = datetime.utcnow()
    kind = random.choices(
        ["login", "usage", "ticket", "payment"],
        weights=[40, 40, 10, 10],
    )[0]

    if kind == "login":
        db.add(LoginEvent(customer_id=cid, login_at=now))
    elif kind == "usage":
        db.add(UsageEvent(customer_id=cid, occurred_at=now, duration_secs=random.uniform(30, 1800)))
    elif kind == "ticket":
        # Occasionally simulate an unhappy customer opening a negative ticket —
        # this is what should push their churn score up on the next scoring pass.
        subject = random.choice(TICKET_SUBJECTS_NEGATIVE if random.random() < 0.4 else TICKET_SUBJECTS_NEUTRAL)
        db.add(SupportTicket(customer_id=cid, created_at=now, subject=subject))
    elif kind == "payment":
        db.add(PaymentEvent(
            customer_id=cid, occurred_at=now,
            amount=round(random.uniform(19, 299), 2),
            status=random.choice(PAYMENT_STATUSES),
        ))

    db.commit()


def get_customer_ids(db):
    return [row[0] for row in db.query(MLCustomer.customer_id).all()]


def run(interval_seconds: float, new_customers: int, once: bool):
    init_all_tables()
    db = SessionLocal()
    try:
        if new_customers:
            add_fake_customers(db, new_customers)

        customer_ids = get_customer_ids(db)
        if not customer_ids:
            print("[realtime] No customers in ml_customers yet — run seed_db.py first.")
            return

        if once:
            for _ in range(20):
                emit_one_event(db, customer_ids)
            print("[realtime] wrote one batch of 20 events.")
            return

        print(f"[realtime] simulating activity for {len(customer_ids)} customers "
              f"(1 event every ~{interval_seconds}s, Ctrl+C to stop)")
        while True:
            emit_one_event(db, customer_ids)
            time.sleep(interval_seconds)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between events")
    parser.add_argument("--new-customers", type=int, default=0, help="add N new fake customers first")
    parser.add_argument("--once", action="store_true", help="write one batch and exit (for testing)")
    args = parser.parse_args()
    run(args.interval, args.new_customers, args.once)
