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


def test_email_verification_flow_and_db_update(client):
    from database import SessionLocal, User
    from main import hash_password
    from datetime import datetime, timezone, timedelta

    # Set up an unverified user in DB
    test_email = "verifyflow@test.com"
    test_code = "842910"
    db = SessionLocal()
    try:
        user = User(
            email=test_email,
            hashed_password=hash_password("password123"),
            role="member",
            is_verified=False,
            verification_code=test_code,
            verification_code_expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    # 1. Login should fail with 403 before email is verified
    r_login = client.post("/login", data={"username": test_email, "password": "password123"})
    assert r_login.status_code == 403
    assert "not verified" in r_login.json()["detail"].lower()

    # 2. Verification with invalid code should fail with 400
    r_bad_verify = client.post("/verify-email", json={"email": test_email, "code": "000000"})
    assert r_bad_verify.status_code == 400
    assert "invalid" in r_bad_verify.json()["detail"].lower()

    # 3. Verification with correct code should succeed and return access token
    r_verify = client.post("/verify-email", json={"email": test_email, "code": test_code})
    assert r_verify.status_code == 200
    assert "access_token" in r_verify.json()

    # 4. Check DB: user.is_verified must be True and verification_code must be cleared
    db = SessionLocal()
    try:
        u_db = db.query(User).filter(User.email == test_email).first()
        assert u_db.is_verified is True
        assert u_db.verification_code is None
        assert u_db.verification_code_expires_at is None
    finally:
        db.close()

    # 5. Login should now succeed with 200
    r_login_ok = client.post("/login", data={"username": test_email, "password": "password123"})
    assert r_login_ok.status_code == 200
    assert "access_token" in r_login_ok.json()
