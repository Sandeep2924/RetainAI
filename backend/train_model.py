"""
train_model.py — trains the churn model from Database/test_.csv.

Run manually or on a slow schedule (daily cron). Never called from the
real-time scoring path — training is decoupled from scoring on purpose.

Usage:
    python train_model.py

Produces:
    ../model.pkl           — the trained RandomForestClassifier
    ../model_metadata.json — trained_at, row_count, auc, precision, recall, model_version
"""
import os
import json
import joblib
import pandas as pd
from datetime import datetime, timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, precision_score, recall_score

from features import FEATURE_COLS, ticket_urgency_score

HERE = os.path.dirname(__file__)
CSV_PATH = os.path.join(HERE, "Database", "test_.csv")
MODEL_OUT = os.path.join(HERE, "..", "model.pkl")
META_OUT = os.path.join(HERE, "..", "model_metadata.json")

LOGIN_FREQ_MAP = {"Daily": 30, "Weekly": 4, "Rarely": 1}


def load_training_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["Account_Age_Days"] = df["Account_Age_Days"].astype(int)
    df["Daily_Usage_Mins"] = df["Daily_Usage_Mins"].astype(float)
    df["Login_Frequency"] = df["Login_Frequency"].map(LOGIN_FREQ_MAP)
    df["Last_Support_Ticket"] = df["Last_Support_Ticket"].apply(ticket_urgency_score)
    df["Churn"] = df["Churn"].astype(int)
    return df


def main():
    print(f"Loading training data from {CSV_PATH} ...")
    df = load_training_data()
    print(f"Loaded {len(df)} rows.")

    X = df[FEATURE_COLS]
    y = df["Churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    auc = round(roc_auc_score(y_test, proba), 4)
    precision = round(precision_score(y_test, preds), 4)
    recall = round(recall_score(y_test, preds), 4)

    print("\n=== Holdout evaluation ===")
    print(classification_report(y_test, preds, target_names=["Retained", "Churned"]))
    print(f"ROC AUC: {auc}  Precision: {precision}  Recall: {recall}")
    print("\nFeature importances:")
    for col, imp in sorted(zip(FEATURE_COLS, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {col:<22} {imp:.3f}")

    joblib.dump(model, MODEL_OUT)
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "auc": auc,
        "precision": precision,
        "recall": recall,
        "model_version": "v_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    }
    with open(META_OUT, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model    -> {os.path.abspath(MODEL_OUT)}")
    print(f"Saved metadata -> {os.path.abspath(META_OUT)}")


if __name__ == "__main__":
    main()
