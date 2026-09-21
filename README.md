# RetainAI — simplified backend

Tested end-to-end in a live Postgres instance before delivery: training,
seeding, simulated activity, scoring, and every API endpoint below were
actually exercised, not just reviewed.

## What changed vs. the original

- **One pipeline, not three.** `pipeline.py` is now the only place that
  turns activity into a churn score. `main.py` never runs the model itself —
  every read endpoint just selects from `customer_predictions`.
- **`realtime.py`** simulates fake customers and fake ongoing activity
  (logins, usage, tickets, payments), written straight to Postgres.
  `pipeline.py` picks up whatever it finds — the two are fully decoupled.
- **No more fake Redis.** `cache.py` is an honest in-process TTL cache.
  If you outgrow one worker process, swap in a real `redis` client — nothing
  else needs to change.
- **No more CSV files sitting next to the database.** All activity lives in
  Postgres tables (`login_events`, `usage_events`, `support_tickets`,
  `payment_events`), and `Account_Age_Days` is derived from `signup_date` on
  every read instead of a static number that goes stale.
- **Bulk, vectorized scoring.** One scoring pass now takes ~0.3s for 500+
  customers (single upsert via `ON CONFLICT DO UPDATE`), instead of a
  per-row loop.
- **One risk threshold, defined once**, in `main.py`, instead of scattered
  0.7/0.75 constants that used to disagree with each other.
- **Training is decoupled from scoring.** `train_model.py` only runs when
  you run it — never on the live request path.

## Setup

```bash
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, etc.

python train_model.py   # trains model.pkl + model_metadata.json (project root)
python seed_db.py       # seeds ml_customers from Database/test_.csv

python main.py           # starts the API on :8000, scores on a schedule
python realtime.py       # separate process — simulates ongoing customer activity
```

`realtime.py` and `main.py` are independent processes talking through
Postgres — run them in two terminals (or two containers/services).

## Still on you before this is production-ready

This pass fixed the architecture and code-quality issues from the last
review. It did **not** add:
- Row-level authorization (every logged-in user can still see every customer)
- Rate limiting on `/login` / `/signup`
- Automated tests

Worth doing before real customer data touches this.
