"""
Tests for /auth endpoints.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_register_success(client: TestClient):
  """New user can register."""
  with patch("api.auth.route.send_email_task") as mock_task:
    mock_task.delay = lambda **kwargs: None
    resp = client.post("/auth/register", json={
      "username": "newuser",
      "email": "newuser@example.com",
      "password": "securepassword123",
    })
  assert resp.status_code == 200


def test_register_duplicate(client: TestClient, verified_user):
  """Registering an existing user returns 409."""
  resp = client.post("/auth/register", json={
    "username": verified_user.username,
    "email": verified_user.email,
    "password": "somepassword",
  })
  assert resp.status_code == 409


def test_login_unverified_user(client: TestClient, db_session):
  """Unverified user cannot log in."""
  import uuid, bcrypt
  from database.models import User
  hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
  user = User(
    id=uuid.uuid4(),
    username="unverified",
    email="unverified@example.com",
    hashed_password=hashed,
    is_verified=False,
  )
  db_session.add(user)
  db_session.flush()

  resp = client.post("/auth/login", json={
    "email": "unverified@example.com",
    "password": "password123",
    "rememberMe": False,
  })
  assert resp.status_code == 401


def test_login_success(client: TestClient, verified_user):
  """Verified user can log in and receives a token."""
  resp = client.post("/auth/login", json={
    "email": verified_user.email,
    "password": "testpassword123",
    "rememberMe": False,
  })
  assert resp.status_code == 200
  data = resp.json()
  assert "access_token" in data
  assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, verified_user):
  """Wrong password returns 401."""
  resp = client.post("/auth/login", json={
    "email": verified_user.email,
    "password": "wrongpassword",
    "rememberMe": False,
  })
  assert resp.status_code == 401


def test_get_me_authenticated(client: TestClient, verified_user, auth_headers):
  """Authenticated user can fetch their own profile."""
  resp = client.get("/auth/me", headers=auth_headers)
  assert resp.status_code == 200
  data = resp.json()
  assert data["email"] == verified_user.email
  assert data["username"] == verified_user.username


def test_get_me_unauthenticated(client: TestClient):
  """No token returns 401."""
  resp = client.get("/auth/me")
  assert resp.status_code == 401


def test_get_me_invalid_token(client: TestClient):
  """Invalid token returns 401."""
  resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
  assert resp.status_code == 401
