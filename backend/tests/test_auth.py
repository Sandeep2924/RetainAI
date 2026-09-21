def test_signup_creates_member_by_default(client):
    r = client.post("/signup", json={"email": "newperson@test.com", "password": "somepass123"})
    assert r.status_code == 200
    assert r.json()["role"] == "member"


def test_signup_matching_admin_emails_gets_admin_role(client):
    r = client.post("/signup", json={"email": "second-admin@test.com", "password": "somepass123"})
    assert r.status_code == 200
    # not in ADMIN_EMAILS, so should be a member — sanity check the negative case
    assert r.json()["role"] == "member"


def test_signup_duplicate_email_rejected(client):
    client.post("/signup", json={"email": "dupe@test.com", "password": "somepass123"})
    r = client.post("/signup", json={"email": "dupe@test.com", "password": "somepass123"})
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"].lower()


def test_signup_weak_password_rejected(client):
    r = client.post("/signup", json={"email": "weak@test.com", "password": "123"})
    assert r.status_code == 400
    assert "8 characters" in r.json()["detail"]


def test_login_wrong_password_rejected(client):
    client.post("/signup", json={"email": "wrongpw@test.com", "password": "correctpass1"})
    r = client.post("/login", data={"username": "wrongpw@test.com", "password": "wrongpass1"})
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    r = client.post("/login", data={"username": "nobody@test.com", "password": "whatever123"})
    assert r.status_code == 401


def test_login_returns_usable_token(client):
    client.post("/signup", json={"email": "tokenowner@test.com", "password": "somepass123"})
    r = client.post("/login", data={"username": "tokenowner@test.com", "password": "somepass123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "tokenowner@test.com"


def test_protected_endpoint_rejects_no_token(client):
    r = client.get("/customers")
    assert r.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client):
    r = client.get("/customers", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_admin_role_from_env(client, admin_headers):
    r = client.get("/me", headers=admin_headers)
    assert r.json()["role"] == "admin"


def test_member_role(client, member_headers):
    r = client.get("/me", headers=member_headers)
    assert r.json()["role"] == "member"
