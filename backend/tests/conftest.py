# STL
import uuid

# External
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Custom
from database.make_db import Base, get_session
from database.models import User
from api.auth.service import create_jwt_token, get_time_tuple
from api.auth.schemas import JwtToken
from app_common.enums import PayloadEnum

# Use an in-memory SQLite DB for tests (fast, no Docker needed)
TEST_DB_URL = "sqlite:///./test.db"

test_engine = create_engine(
  TEST_DB_URL,
  connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def override_get_session():
  session = TestingSessionLocal()
  try:
    yield session
    session.commit()
  except Exception:
    session.rollback()
    raise
  finally:
    session.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
  """Create all tables once for the test session."""
  Base.metadata.create_all(bind=test_engine)
  yield
  Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session() -> Session:
  """Fresh DB session per test, rolled back after."""
  connection = test_engine.connect()
  transaction = connection.begin()
  session = TestingSessionLocal(bind=connection)
  yield session
  session.close()
  transaction.rollback()
  connection.close()


@pytest.fixture()
def client(db_session: Session):
  """TestClient with DB override."""
  from server import create_app
  app = create_app()
  app.dependency_overrides[get_session] = lambda: db_session
  with TestClient(app) as c:
    yield c


@pytest.fixture()
def verified_user(db_session: Session) -> User:
  """A verified user in the test DB."""
  import bcrypt
  hashed = bcrypt.hashpw(b"testpassword123", bcrypt.gensalt()).decode()
  user = User(
    id=uuid.uuid4(),
    username="testuser",
    email="test@example.com",
    hashed_password=hashed,
    is_verified=True,
  )
  db_session.add(user)
  db_session.flush()
  return user


@pytest.fixture()
def auth_token(verified_user: User) -> str:
  """A valid JWT token for the verified user."""
  now, exp = get_time_tuple(rememberMe=False)
  token_data = JwtToken(
    sub=str(verified_user.id),
    what=PayloadEnum.LOGIN,
    exp=exp,
    iat=now,
  )
  return create_jwt_token(data=token_data)


@pytest.fixture()
def auth_headers(auth_token: str) -> dict:
  return {"Authorization": f"Bearer {auth_token}"}
