"""
pipeline.py — the ONE place that turns raw activity into churn scores.

run_scoring_pass():
    1. Load every customer + their recent activity from Postgres.
    2. Aggregate that activity into the 4 model features (vectorized, one
       pass over the whole table — no per-customer queries).
    3. Run the model + SHAP explainer once over the full batch.
    4. Upsert every row into customer_predictions.

Called on a schedule by main.py (every SCORING_INTERVAL_SECONDS) and by
POST /admin/rescore for a manual trigger. Nothing else in the codebase
runs the model — every read endpoint just selects from customer_predictions.

get_customer_trend() reuses the exact same feature math to reconstruct a
day-by-day risk trend for one customer, so "today's score" and "the last
point on the trend chart" can never disagree.
"""
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

import joblib
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from features import FEATURE_COLS, ticket_urgency_score, LOGIN_WINDOW_DAYS, USAGE_WINDOW_DAYS, TICKET_WINDOW_DAYS
from database import engine, SessionLocal, CustomerPrediction

logger = logging.getLogger(__name__)

_scoring_lock = threading.Lock()

# Injected once at startup by main.py
_model = None
_explainer = None
_model_version = "unknown"


def configure(model, explainer, model_version):
    global _model, _explainer, _model_version
    _model, _explainer, _model_version = model, explainer, model_version


def _load_roster_and_activity():
    """One round trip per table, not one per customer."""
    now = datetime.utcnow()
    login_cutoff = now - timedelta(days=LOGIN_WINDOW_DAYS)
    usage_cutoff = now - timedelta(days=USAGE_WINDOW_DAYS)
    ticket_cutoff = now - timedelta(days=TICKET_WINDOW_DAYS)

    roster = pd.read_sql(text('SELECT customer_id, name, email, signup_date FROM ml_customers'), engine)
    logins = pd.read_sql(
        text('SELECT customer_id, login_at FROM login_events WHERE login_at > :cutoff'),
        engine, params={"cutoff": login_cutoff},
    )
    usage = pd.read_sql(
        text('SELECT customer_id, occurred_at, duration_secs FROM usage_events WHERE occurred_at > :cutoff'),
        engine, params={"cutoff": usage_cutoff},
    )
    tickets = pd.read_sql(
        text('SELECT customer_id, created_at, subject FROM support_tickets WHERE created_at > :cutoff '
             'ORDER BY created_at DESC'),
        engine, params={"cutoff": ticket_cutoff},
    )
    return roster, logins, usage, tickets


def _build_feature_frame(roster, logins, usage, tickets, as_of: datetime | None = None):
    as_of = as_of or datetime.utcnow()

    df = roster.copy()
    df["Account_Age_Days"] = df["signup_date"].apply(
        lambda d: max(1, (as_of.date() - d).days)
    )

    login_counts = logins.groupby("customer_id").size() if not logins.empty else pd.Series(dtype=int)
    df["Login_Frequency"] = df["customer_id"].map(login_counts).fillna(0).astype(int)

    if not usage.empty:
        usage_avg = usage.groupby("customer_id")["duration_secs"].mean() / 60.0
    else:
        usage_avg = pd.Series(dtype=float)
    df["Daily_Usage_Mins"] = df["customer_id"].map(usage_avg).fillna(0.0)

    if not tickets.empty:
        latest_ticket = tickets.drop_duplicates(subset="customer_id", keep="first").set_index("customer_id")["subject"]
    else:
        latest_ticket = pd.Series(dtype=object)
    df["Last_Support_Ticket"] = df["customer_id"].map(latest_ticket)
    df["Last_Support_Ticket"] = df["Last_Support_Ticket"].where(df["Last_Support_Ticket"].notna(), None)
    df["Last_Support_Ticket"] = df["Last_Support_Ticket"].apply(ticket_urgency_score)

    return df


def _score_frame(df: pd.DataFrame):
    """Runs the model + SHAP over an already-engineered feature frame."""
    X = df[FEATURE_COLS]

    if _model is None:
        probabilities = [0.5] * len(X)
        top_drivers = [FEATURE_COLS[0]] * len(X)
        shap_dicts = [{c: 0.0 for c in FEATURE_COLS} for _ in range(len(X))]
        return probabilities, top_drivers, shap_dicts

    probabilities = _model.predict_proba(X)[:, 1].tolist()

    if _explainer is not None:
        raw_shap = _explainer.shap_values(X)
        churn_shap = raw_shap[1] if isinstance(raw_shap, list) else (
            raw_shap[:, :, 1] if raw_shap.ndim == 3 else raw_shap
        )
        shap_df = pd.DataFrame(churn_shap, columns=FEATURE_COLS)
        top_drivers = [FEATURE_COLS[i] for i in shap_df.abs().values.argmax(axis=1)]
        shap_dicts = [dict(zip(FEATURE_COLS, [float(v) for v in row])) for row in churn_shap]
    else:
        fi = getattr(_model, "feature_importances_", None)
        top_driver = FEATURE_COLS[fi.argmax()] if fi is not None else FEATURE_COLS[0]
        top_drivers = [top_driver] * len(X)
        shap_dicts = [{c: 0.0 for c in FEATURE_COLS} for _ in range(len(X))]

    return probabilities, top_drivers, shap_dicts


def run_scoring_pass() -> int:
    """Thread-safe entry point. Returns rows scored, or -1 if skipped
    because a previous pass is still running."""
    if not _scoring_lock.acquire(blocking=False):
        logger.info("[pipeline] skipped — previous pass still running")
        return -1
    try:
        return _do_scoring_pass()
    except Exception:
        logger.exception("[pipeline] scoring pass failed")
        return 0
    finally:
        _scoring_lock.release()


def _do_scoring_pass() -> int:
    roster, logins, usage, tickets = _load_roster_and_activity()
    if roster.empty:
        logger.warning("[pipeline] ml_customers is empty — nothing to score")
        return 0

    df = _build_feature_frame(roster, logins, usage, tickets)
    probabilities, top_drivers, shap_dicts = _score_frame(df)

    scored_at = datetime.now(timezone.utc)
    rows = [
        {
            "customer_id": cid,
            "churn_probability": float(prob),
            "top_driver": driver,
            "shap_values": json.dumps(shap),
            "scored_at": scored_at,
            "model_version": _model_version,
        }
        for cid, prob, driver, shap in zip(df["customer_id"], probabilities, top_drivers, shap_dicts)
    ]

    # One bulk upsert instead of N ORM updates in a loop.
    stmt = pg_insert(CustomerPrediction).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["customer_id"],
        set_={
            "churn_probability": stmt.excluded.churn_probability,
            "top_driver": stmt.excluded.top_driver,
            "shap_values": stmt.excluded.shap_values,
            "scored_at": stmt.excluded.scored_at,
            "model_version": stmt.excluded.model_version,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)

    logger.info(f"[pipeline] scored {len(rows)} customers @ {scored_at.isoformat()}")
    return len(rows)


def score_dataframe(df: pd.DataFrame):
    """Public entry point for scoring a feature-engineered DataFrame that
    isn't part of the live roster (e.g. a one-off CSV upload from the
    Predictions page). Reuses the exact same model + SHAP explainer as the
    scheduled pipeline — same math, same model version, just not persisted
    to customer_predictions (that table stays owned by run_scoring_pass())."""
    return _score_frame(df)


def get_customer_trend(customer_id: str, days: int = 14):
    """Re-derives what the churn score WOULD have been on each of the last
    `days` days, using the same feature math as run_scoring_pass — just
    windowed as-of each day instead of as-of now.

    Pulls activity from a window wide enough to cover the whole trend
    (days + each feature's own lookback), not just "now", since a point
    14 days ago still needs its own trailing 7/30/90-day windows."""
    with engine.connect() as conn:
        roster = pd.read_sql(
            text('SELECT customer_id, name, email, signup_date FROM ml_customers WHERE customer_id = :cid'),
            conn, params={"cid": customer_id},
        )
    if roster.empty:
        return None

    today = datetime.utcnow()
    wide_cutoff = today - timedelta(days=days + max(LOGIN_WINDOW_DAYS, USAGE_WINDOW_DAYS, TICKET_WINDOW_DAYS))

    logins = pd.read_sql(
        text('SELECT customer_id, login_at FROM login_events WHERE customer_id = :cid AND login_at > :cutoff'),
        engine, params={"cid": customer_id, "cutoff": wide_cutoff},
    )
    usage = pd.read_sql(
        text('SELECT customer_id, occurred_at, duration_secs FROM usage_events '
             'WHERE customer_id = :cid AND occurred_at > :cutoff'),
        engine, params={"cid": customer_id, "cutoff": wide_cutoff},
    )
    tickets = pd.read_sql(
        text('SELECT customer_id, created_at, subject FROM support_tickets '
             'WHERE customer_id = :cid AND created_at > :cutoff ORDER BY created_at DESC'),
        engine, params={"cid": customer_id, "cutoff": wide_cutoff},
    )

    points = []
    for i in range(days - 1, -1, -1):
        as_of = today - timedelta(days=i)
        login_win = as_of - timedelta(days=LOGIN_WINDOW_DAYS)
        usage_win = as_of - timedelta(days=USAGE_WINDOW_DAYS)
        ticket_win = as_of - timedelta(days=TICKET_WINDOW_DAYS)

        day_logins = logins[(logins["login_at"] <= as_of) & (logins["login_at"] > login_win)]
        day_usage = usage[(usage["occurred_at"] <= as_of) & (usage["occurred_at"] > usage_win)]
        day_tickets = tickets[(tickets["created_at"] <= as_of) & (tickets["created_at"] > ticket_win)]

        row = _build_feature_frame(roster, day_logins, day_usage, day_tickets, as_of=as_of)
        probs, _, _ = _score_frame(row)
        points.append({"date": as_of.strftime("%Y-%m-%d"), "churn_risk_score": round(probs[0], 4)})

    return points
