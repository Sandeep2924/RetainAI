def test_customers_summary_shape(client, admin_headers):
    r = client.get("/customers/summary", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    for key in ["total_customers", "high_risk_count", "avg_risk_score", "risk_distribution", "top_driver_breakdown"]:
        assert key in body
    assert body["total_customers"] > 0
    assert 0 <= body["avg_risk_score"] <= 1


def test_customers_list_sorted_by_risk_desc(client, admin_headers):
    r = client.get("/customers", headers=admin_headers)
    scores = [c["churn_risk_score"] for c in r.json()["customers"]]
    assert scores == sorted(scores, reverse=True)


def test_customers_high_risk_filter(client, admin_headers):
    r = client.get("/customers?high_risk_only=true", headers=admin_headers)
    customers = r.json()["customers"]
    assert all(c["churn_risk_score"] > 0.75 for c in customers)
    assert all(c["high_risk"] for c in customers)


def test_customer_detail_includes_shap(client, admin_headers, sample_customer_id):
    r = client.get(f"/customers/{sample_customer_id}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["customer_id"] == sample_customer_id
    assert set(body["shap_explanations"].keys()) == {
        "Account_Age_Days", "Login_Frequency", "Daily_Usage_Mins", "Last_Support_Ticket"
    }


def test_customer_detail_404_for_unknown_id(client, admin_headers):
    r = client.get("/customers/not-a-real-customer-id", headers=admin_headers)
    assert r.status_code == 404


def test_export_csv_returns_csv(client, admin_headers):
    r = client.get("/customers/export", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "customer_id" in r.text.splitlines()[0]


def test_notes_add_and_list(client, admin_headers, sample_customer_id):
    add = client.post(
        f"/customers/{sample_customer_id}/notes",
        json={"text": "Called about renewal, seemed positive."},
        headers=admin_headers,
    )
    assert add.status_code == 200
    assert add.json()["author"] == "admin@test.com"

    listing = client.get(f"/customers/{sample_customer_id}/notes", headers=admin_headers)
    texts = [n["text"] for n in listing.json()["notes"]]
    assert "Called about renewal, seemed positive." in texts


def test_notes_empty_text_rejected(client, admin_headers, sample_customer_id):
    r = client.post(f"/customers/{sample_customer_id}/notes", json={"text": "   "}, headers=admin_headers)
    assert r.status_code == 400


def test_risk_trend_returns_points_with_source(client, admin_headers, sample_customer_id):
    r = client.get(f"/customers/{sample_customer_id}/risk_trend?days=7", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["trend"]) == 7
    assert body["source"] in ("recorded", "reconstructed")
    assert all(0 <= p["churn_risk_score"] <= 1 for p in body["trend"])
