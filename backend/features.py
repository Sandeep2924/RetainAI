"""
features.py — the ONE place that turns raw activity into model features.

Used by train_model.py (training) and pipeline.py (scoring), so training and
inference are always looking at numbers computed the exact same way.

The model was trained on 4 features:
  Account_Age_Days   — days since signup
  Login_Frequency     — number of logins in the trailing 30 days
  Daily_Usage_Mins    — average session length (mins) in the trailing 7 days
  Last_Support_Ticket — 0-10 urgency score of the most recent ticket (90-day window)
"""
from datetime import timedelta

FEATURE_COLS = ["Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins", "Last_Support_Ticket"]

NEGATIVE_WORDS = [
    "cancel", "cancelling", "confus", "wait", "waiting", "angry", "frustrat",
    "broken", "bug", "increase", "unhappy", "disappoint", "complain",
    "refund", "downgrade", "slow", "issue", "problem", "error", "fail",
]
POSITIVE_WORDS = [
    "thanks", "thank you", "helpful", "great", "excited", "love", "upgrad",
    "tutorial", "question", "how do i", "easy",
]


def ticket_urgency_score(text) -> int:
    """Heuristic 0-10 urgency score from a support ticket subject/message."""
    import math
    if isinstance(text, (int, float)):
        if math.isnan(text): return 0
        return max(0, min(10, int(text)))
    if not isinstance(text, str) or not text.strip():
        return 0
    t = text.lower()
    score = 5  # neutral baseline
    score += sum(2 for w in NEGATIVE_WORDS if w in t)
    score -= sum(1 for w in POSITIVE_WORDS if w in t)
    return max(0, min(10, score))


def engineer_from_events(account_age_days, logins_30d, avg_usage_7d_mins, latest_ticket_subject):
    """Turns raw aggregates into the exact feature dict the model expects."""
    return {
        "Account_Age_Days": account_age_days,
        "Login_Frequency": logins_30d,
        "Daily_Usage_Mins": avg_usage_7d_mins,
        "Last_Support_Ticket": ticket_urgency_score(latest_ticket_subject),
    }


# Windows used everywhere features are computed, so pipeline.py and any
# ad-hoc trend/backfill code stay consistent.
LOGIN_WINDOW_DAYS = 30
USAGE_WINDOW_DAYS = 7
TICKET_WINDOW_DAYS = 90
