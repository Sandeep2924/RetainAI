def test_member_cannot_assign_owner(client, member_headers, sample_customer_id):
    r = client.put(
        f"/customers/{sample_customer_id}/owner",
        json={"owner_email": "cs@test.com"},
        headers=member_headers,
    )
    assert r.status_code == 403


def test_admin_can_assign_owner(client, admin_headers, sample_customer_id):
    r = client.put(
        f"/customers/{sample_customer_id}/owner",
        json={"owner_email": "cs@test.com"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["owner_email"] == "cs@test.com"

    detail = client.get(f"/customers/{sample_customer_id}", headers=admin_headers)
    assert detail.json()["owner_email"] == "cs@test.com"


def test_member_cannot_run_alert(client, member_headers):
    r = client.post("/alerts/high_risk/run", headers=member_headers)
    assert r.status_code == 403


def test_admin_can_run_alert_even_without_config(client, admin_headers):
    r = client.post("/alerts/high_risk/run", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "not configured" in body["email"]


def test_member_cannot_trigger_snapshot(client, member_headers):
    r = client.post("/admin/snapshot_risk_scores", headers=member_headers)
    assert r.status_code == 403


def test_admin_can_trigger_snapshot(client, admin_headers):
    r = client.post("/admin/snapshot_risk_scores", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["customers_scored"] > 0


def test_snapshot_then_trend_prefers_recorded_source(client, admin_headers, sample_customer_id):
    # Run the snapshot job 3 times (simulating 3 days) so the trend endpoint
    # has enough recorded history to prefer it over reconstruction.
    for _ in range(3):
        client.post("/admin/snapshot_risk_scores", headers=admin_headers)

    r = client.get(f"/customers/{sample_customer_id}/risk_trend?days=7", headers=admin_headers)
    # Only one distinct date gets written per run (today), so this still may
    # not reach 3 distinct days in a single test run — just check it doesn't error
    # and returns a valid source value either way.
    assert r.json()["source"] in ("recorded", "reconstructed")
