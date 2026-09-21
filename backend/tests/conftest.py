"""
conftest.py — sets up an isolated SQLite test database BEFORE main.py (and
therefore database.py) is ever imported, so tests never touch your real dev
database or Postgres. Also provides ready-made admin/member auth tokens.
"""

import os
import tempfile

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)

os.environ["DB_PATH"] = _test_db_path
os.environ.pop("DATABASE_URL", None)  # force the SQLite fallback, never real Postgres
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_EMAILS"] = "admin@test.com"
os.environ["ENV"] = "test"
os.environ.pop("SENTRY_DSN", None)
os.environ.pop("SLACK_WEBHOOK_URL", None)
os.environ.pop("SMTP_HOST", None)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from main import app
    with TestClient(app) as c:
        yield c
    os.unlink(_test_db_path)


@pytest.fixture(scope="session")
def admin_token(client):
    client.post("/signup", json={"email": "admin@test.com", "password": "adminpass123"})
    r = client.post("/login", data={"username": "admin@test.com", "password": "adminpass123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def member_token(client):
    client.post("/signup", json={"email": "member@test.com", "password": "memberpass123"})
    r = client.post("/login", data={"username": "member@test.com", "password": "memberpass123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def member_headers(member_token):
    return {"Authorization": f"Bearer {member_token}"}


@pytest.fixture(scope="session")
def sample_customer_id(client, admin_token):
    r = client.get("/customers?high_risk_only=true", headers={"Authorization": f"Bearer {admin_token}"})
    customers = r.json()["customers"]
    assert customers, "expected at least one high-risk customer in the sample data"
    return customers[0]["customer_id"]
