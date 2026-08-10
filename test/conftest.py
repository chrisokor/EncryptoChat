import os
from nacl.public import PrivateKey
from nacl.signing import SigningKey
from utils.base_64_utils import bytes_to_base64_str
from uuid import uuid4

# test database url
TEST_DATABASE_URL = "postgresql://encryptochat:encryptochat_password@127.0.0.1/encryptochat_test"
TEST_REDIS_URL = "redis://127.0.0.1:6379/1" # DB 1 for tests

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import redis

from server import app
from database import get_database
from models.database_models import Base


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for each test"""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()

    # Clear all tables before each test
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_database] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def redis_client():
    """Create a Redis client for tests"""
    client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    client.flushdb() # clear test redis db before each test
    yield client
    client.flushdb() # clean up after test
    client.close()


@pytest.fixture
def registered_user(client):
    """Register a user and return their credentials"""

    user_secret_key = PrivateKey.generate()
    user_public_key = user_secret_key.public_key
    signing_key = SigningKey.generate()
    username = "alice"

    client.post("/register", json={
        "username": username,
        "public_key": bytes_to_base64_str(bytes(user_public_key)),
        "signing_public_key": bytes_to_base64_str(bytes(signing_key.verify_key)),
    })

    challenge = client.get(f"/auth/challenge/{username.lower()}").json()["challenge"]
    signature = signing_key.sign(challenge.encode()).signature
    login = client.post("/auth/login", json={
        "username": username,
        "challenge": challenge,
        "signature": bytes_to_base64_str(signature),
    })

    return {
        "username": username,
        "secret_key": user_secret_key,
        "public_key": user_public_key,
        "signing_key": signing_key,
        "token": login.json()["access_token"],
    }


@pytest.fixture
def upload_prekeys(client):
    """"Upload list of user's prekeys to database"""

    def _upload_prekeys(user, count=5):
        """Create list of a user's prekeys"""
        username = user["username"]
        prekeys = []
        for _ in range(count):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4().hex,
                "key": bytes_to_base64_str(bytes(prekey))
            })

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        }, headers={"Authorization": f"Bearer {user['token']}"})
        return {"prekeys": prekeys, "response": response}

    return _upload_prekeys
