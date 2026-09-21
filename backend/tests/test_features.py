import pandas as pd
from features import engineer_dataframe, ticket_urgency_score, LOGIN_FREQ_MAP


def test_login_freq_map_covers_expected_values():
    assert LOGIN_FREQ_MAP == {"Daily": 30, "Weekly": 4, "Rarely": 1}


def test_ticket_urgency_score_empty_is_zero():
    assert ticket_urgency_score("") == 0
    assert ticket_urgency_score(None) == 0


def test_ticket_urgency_score_negative_language_scores_higher():
    angry = ticket_urgency_score("I want to cancel, this is broken and I'm so frustrated")
    neutral = ticket_urgency_score("How do I add a teammate?")
    assert angry > neutral


def test_ticket_urgency_score_positive_language_scores_lower():
    happy = ticket_urgency_score("Thanks so much, this is great and really helpful!")
    neutral_baseline = 5
    assert happy < neutral_baseline


def test_ticket_urgency_score_clamped_0_to_10():
    extremely_negative = ticket_urgency_score(
        "cancel cancel broken broken bug bug angry angry frustrated frustrated issue issue"
    )
    assert 0 <= extremely_negative <= 10


def test_engineer_dataframe_transforms_expected_columns():
    df = pd.DataFrame({
        "Login_Frequency": ["Daily", "Weekly", "Rarely"],
        "Last_Support_Ticket": ["cancel this now", "", "thanks, great job"],
        "Other_Column": [1, 2, 3],
    })
    engineered = engineer_dataframe(df)

    assert engineered["Login_Frequency"].tolist() == [30, 4, 1]
    assert engineered.loc[0, "Last_Support_Ticket"] > engineered.loc[2, "Last_Support_Ticket"]
    # original untouched
    assert df["Login_Frequency"].tolist() == ["Daily", "Weekly", "Rarely"]
