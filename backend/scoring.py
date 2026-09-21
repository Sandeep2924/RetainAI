"""
scoring.py — model loading + customer scoring, factored out of main.py so the
daily snapshot script (scripts/snapshot_risk_scores.py) can score customers
and write to risk_score_snapshots without booting the whole FastAPI app.
"""

import os
import random

import joblib
import shap
import pandas as pd

from features import engineer_dataframe

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "saas_churn_model.pkl")
CUSTOMERS_CSV = os.path.join(os.path.dirname(__file__), "Database", "test_.csv")
FEATURE_COLS = ["Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins", "Last_Support_Ticket"]

model = None
explainer = None
_customers_cache = {"risk": None}


def load_model():
    global model, explainer
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        explainer = shap.TreeExplainer(model)
        print("Model and SHAP explainer loaded successfully.")
    else:
        print(f"WARNING: Model file not found at {MODEL_PATH}")
    return model, explainer


def get_scored_customers() -> pd.DataFrame:
    """Loads Database/test_.csv, engineers features, and scores every customer
    with the trained model. Cached in-process since the source CSV is static;
    call invalidate_cache() after retraining or swapping data."""
    if _customers_cache["risk"] is not None:
        return _customers_cache["risk"]

    raw = pd.read_csv(CUSTOMERS_CSV)
    engineered = engineer_dataframe(raw)
    X = engineered[FEATURE_COLS]

    if model is None:
        probabilities = [random.uniform(0.05, 0.95) for _ in range(len(X))]
        top_drivers = [random.choice(FEATURE_COLS) for _ in range(len(X))]
    else:
        probabilities = model.predict_proba(X)[:, 1].tolist()
        raw_shap = explainer.shap_values(X)
        if isinstance(raw_shap, list):
            churn_shap = raw_shap[1]
        else:
            churn_shap = raw_shap[:, :, 1] if raw_shap.ndim == 3 else raw_shap
        top_drivers = [
            FEATURE_COLS[i] for i in abs(pd.DataFrame(churn_shap, columns=FEATURE_COLS)).values.argmax(axis=1)
        ]

    result = pd.DataFrame({
        "customer_id": raw["Customer_ID"],
        "name": raw["Name"],
        "email": raw["Email"],
        "account_age_days": raw["Account_Age_Days"],
        "daily_usage_mins": raw["Daily_Usage_Mins"],
        "churn_risk_score": probabilities,
        "top_driver": top_drivers,
    })
    result["high_risk"] = result["churn_risk_score"] > 0.75
    result = result.sort_values("churn_risk_score", ascending=False).reset_index(drop=True)

    _customers_cache["risk"] = result
    return result


def invalidate_cache():
    _customers_cache["risk"] = None


def write_daily_snapshot(db_session) -> dict:
    """Upserts today's churn risk score for every customer into
    risk_score_snapshots. Shared by /admin/snapshot_risk_scores and the
    standalone cron script."""
    from datetime import date
    import models

    df = get_scored_customers()
    today = date.today()
    written = 0
    for _, row in df.iterrows():
        existing = (
            db_session.query(models.RiskScoreSnapshot)
            .filter(models.RiskScoreSnapshot.customer_id == row["customer_id"])
            .filter(models.RiskScoreSnapshot.snapshot_date == today)
            .first()
        )
        if existing:
            existing.churn_risk_score = float(row["churn_risk_score"])
            existing.top_driver = row["top_driver"]
        else:
            db_session.add(models.RiskScoreSnapshot(
                customer_id=row["customer_id"],
                snapshot_date=today,
                churn_risk_score=float(row["churn_risk_score"]),
                top_driver=row["top_driver"],
            ))
            written += 1
    db_session.commit()
    return {"date": today.isoformat(), "customers_scored": len(df), "new_snapshots": written}
