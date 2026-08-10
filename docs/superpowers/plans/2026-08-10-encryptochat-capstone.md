# EncryptoChat Capstone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved EncryptoChat capstone: authenticated encrypted messaging, real-time delivery, browser demo, CI/CD container publishing, and resume-ready documentation.

**Architecture:** Keep FastAPI as the integrated app serving REST, WebSocket, and static frontend assets. Use PostgreSQL for durable users/prekeys/message state, Redis for inbox queues, PyNaCl for encryption/signatures, and GitHub Actions for tested Docker image publishing.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, PostgreSQL 15, Redis 7, PyNaCl, pytest, Docker, GitHub Actions, plain HTML/CSS/JavaScript.

## Global Constraints

- Preserve existing user changes unless a task explicitly requires modifying the same file.
- Use test-driven backend changes: write failing tests, verify failure, implement, verify green.
- Do not add a separate frontend framework or build system.
- Store demo browser private keys in localStorage and document that limitation.
- Treat the protocol as educational X3DH-style prekey messaging, not a full Signal implementation.
- Keep `docker compose up --build` as the main demo command.
- Publish Docker images only from `main`; do not add hosted deployment until a platform is chosen.

---

## File Structure

- `server.py`: FastAPI routes, WebSocket endpoint, static frontend mount, request models.
- `auth.py`: Challenge generation, signature verification, token creation, route authorization helpers.
- `settings.py`: Central environment-backed configuration.
- `models/database_models.py`: SQLAlchemy user/message/prekey fields and message status constants.
- `utils/validation.py`: Username, base64 key, ciphertext, and prekey validation helpers.
- `utils/redis_helper.py`: Redis inbox helpers, including message IDs in envelopes.
- `chat_client.py`: CLI client identity, signing auth, encryption, prekey health, and fingerprint display.
- `chat_script.py`: CLI command routing and argument fix.
- `static/index.html`: Browser demo structure.
- `static/styles.css`: Browser demo styling.
- `static/app.js`: Browser demo identity, auth, chat, WebSocket, and prekey actions.
- `test/integration/auth/test_auth.py`: Authentication and authorization integration tests.
- `test/integration/messaging/test_messaging.py`: Message send, inbox, status, and Redis behavior tests.
- `test/integration/prekeys/test_get_prekey.py`: Prekey retrieval and count tests.
- `test/integration/user/test_user_registration.py`: Registration validation tests.
- `.env.example`: Documented local configuration.
- `.github/workflows/pipeline.yml`: CI/CD with test, Docker build, and GHCR publish.
- `README.md`: Updated setup, usage, API, CI/CD, and security notes.
- `docs/LEARNING_GUIDE.md`: Explanation and interview prep.

---

### Task 1: Repair Existing CLI/API Prekey Flow

**Files:**
- Modify: `chat_script.py`
- Modify: `chat_client.py`
- Modify: `server.py`
- Test: `test/integration/prekeys/test_get_prekey.py`

**Interfaces:**
- Consumes: existing `GET /users/{username}/prekeys`.
- Produces: `GET /users/{username}/keys` alias returning `{"username": str, "public_key": str, "prekey": {"id": str, "key": str}}`.

- [ ] **Step 1: Write failing compatibility test**

Add to `test/integration/prekeys/test_get_prekey.py`:

```python
def test_get_user_keys_alias_returns_and_consumes_prekey(self, client, registered_user, upload_prekeys):
    username = registered_user()["username"]
    uploaded = upload_prekeys(username)["prekeys"]

    response = client.get(f"/users/{username}/keys")

    assert response.status_code == 200
    assert response.json()["username"] == username
    assert response.json()["prekey"]["id"] == uploaded[0]["id"]
```

- [ ] **Step 2: Verify failing test**

Run: `./venv/bin/pytest test/integration/prekeys/test_get_prekey.py::TestGetPrekey::test_get_user_keys_alias_returns_and_consumes_prekey -q`

Expected: FAIL with `404 Not Found` because `/users/{username}/keys` is not implemented.

- [ ] **Step 3: Implement route alias and CLI fixes**

In `server.py`, extract prekey retrieval into a helper and add the alias:

```python
def _consume_prekey_for_user(username: str, db: Session):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")

    prekey = (
        db.query(Prekey)
        .filter(Prekey.username == username, Prekey.used == False)
        .order_by(Prekey.created_at)
        .first()
    )
    if not prekey:
        raise HTTPException(410, "No prekeys available.")

    prekey.used = True
    prekey.used_at = datetime.now(UTC)
    db.commit()
    return {
        "username": user.username,
        "public_key": user.public_key,
        "prekey": {"id": prekey.id, "key": prekey.key},
    }

@app.get("/users/{username}/prekeys")
def get_prekey(username: str, db: Session = Depends(get_database)):
    return _consume_prekey_for_user(username, db)

@app.get("/users/{username}/keys")
def get_user_keys(username: str, db: Session = Depends(get_database)):
    return _consume_prekey_for_user(username, db)
```

In `chat_script.py`, fix the default argument:

```python
name = sys.argv[1] if len(sys.argv) > 1 else "alice"
```

In `chat_script.py`, replace `client.shared_boxes` with `client.sessions` in the `msg` branch:

```python
if peer not in client.sessions:
    client.handshake_with(peer)
```

- [ ] **Step 4: Verify task tests pass**

Run: `./venv/bin/pytest test/integration/prekeys/test_get_prekey.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py chat_client.py chat_script.py test/integration/prekeys/test_get_prekey.py
git commit -m "fix: align client and server prekey lookup"
```

---

### Task 2: Add Settings and Request Validation

**Files:**
- Create: `settings.py`
- Create: `utils/validation.py`
- Create: `.env.example`
- Modify: `database.py`
- Modify: `utils/redis_helper.py`
- Modify: `utils/constants.py`
- Modify: `server.py`
- Test: `test/integration/user/test_user_registration.py`
- Test: `test/integration/prekeys/test_prekey_upload.py`
- Test: `test/integration/messaging/test_messaging.py`

**Interfaces:**
- Produces: `settings.settings.database_url`, `settings.settings.redis_url`, `settings.settings.api_url`, `settings.settings.token_ttl_seconds`, `settings.settings.challenge_ttl_seconds`.
- Produces: validation helpers `normalize_username(value: str) -> str`, `validate_base64_key(value: str, expected_bytes: int) -> str`, and `validate_ciphertext(value: str) -> str`.

- [ ] **Step 1: Write failing validation tests**

Add to `test/integration/user/test_user_registration.py`:

```python
def test_register_invalid_username_returns_422(self, client):
    response = client.post("/register", json={
        "username": "1 bad name",
        "public_key": "abc",
        "signing_public_key": "abc",
    })

    assert response.status_code == 422
```

Add to `test/integration/prekeys/test_prekey_upload.py`:

```python
def test_upload_invalid_prekey_returns_422(self, client, registered_user):
    username = registered_user()["username"]

    response = client.post(f"/users/{username}/prekeys", json={
        "prekeys": [{"id": "bad id", "key": "not-base64"}]
    })

    assert response.status_code == 422
```

Add to `test/integration/messaging/test_messaging.py`:

```python
def test_send_message_rejects_invalid_ciphertext(self, client, registered_user):
    sender = registered_user()
    recipient = registered_user("Bob")

    response = client.post("/send", json={
        "to": recipient["username"],
        "frm": sender["username"],
        "ciphertext": "not-base64",
        "prekey_id": "abc",
    })

    assert response.status_code == 422
```

- [ ] **Step 2: Verify failing tests**

Run: `./venv/bin/pytest test/integration/user/test_user_registration.py test/integration/prekeys/test_prekey_upload.py test/integration/messaging/test_messaging.py -q`

Expected: at least the new invalid input tests fail because validation is incomplete.

- [ ] **Step 3: Implement settings and validation helpers**

Create `settings.py`:

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/encryptochat")
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    api_url: str = os.getenv("API_URL", "http://127.0.0.1:8000")
    token_ttl_seconds: int = int(os.getenv("TOKEN_TTL_SECONDS", "604800"))
    challenge_ttl_seconds: int = int(os.getenv("CHALLENGE_TTL_SECONDS", "300"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "")

settings = Settings()
```

Create `utils/validation.py`:

```python
import base64
import re

USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,31}$")
PREKEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-=]{8,80}$")

def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username must start with a letter and contain 3-32 letters, numbers, or underscores.")
    return username

def validate_base64_key(value: str, expected_bytes: int) -> str:
    try:
        decoded = base64.b64decode(value.encode(), validate=True)
    except Exception as exc:
        raise ValueError("Value must be valid base64.") from exc
    if len(decoded) != expected_bytes:
        raise ValueError(f"Decoded value must be {expected_bytes} bytes.")
    return value

def validate_ciphertext(value: str) -> str:
    try:
        decoded = base64.b64decode(value.encode(), validate=True)
    except Exception as exc:
        raise ValueError("Ciphertext must be valid base64.") from exc
    if not decoded:
        raise ValueError("Ciphertext cannot be empty.")
    if len(decoded) > 65536:
        raise ValueError("Ciphertext cannot exceed 65536 bytes.")
    return value

def validate_prekey_id(value: str) -> str:
    if not PREKEY_ID_PATTERN.fullmatch(value):
        raise ValueError("Prekey id contains invalid characters.")
    return value
```

Update config imports:

```python
from settings import settings
```

Use `settings.database_url`, `settings.redis_url`, and `settings.api_url` in existing modules.

Create `.env.example`:

```env
DATABASE_URL=postgresql://encryptochat:encryptochat_password@localhost:5432/encryptochat
REDIS_URL=redis://localhost:6379/0
API_URL=http://127.0.0.1:8000
TOKEN_TTL_SECONDS=604800
CHALLENGE_TTL_SECONDS=300
CORS_ORIGINS=http://localhost:8000
```

- [ ] **Step 4: Apply validation in Pydantic models**

In `server.py`, use Pydantic v2 field validators:

```python
from pydantic import BaseModel, Field, field_validator
from utils.validation import normalize_username, validate_base64_key, validate_ciphertext, validate_prekey_id

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    public_key: str
    signing_public_key: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        return normalize_username(value)

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, value):
        return validate_base64_key(value, 32)

    @field_validator("signing_public_key")
    @classmethod
    def validate_signing_public_key(cls, value):
        if value is None:
            return None
        return validate_base64_key(value, 32)
```

Apply equivalent validators to message recipient/sender, ciphertext, prekey id, and prekey public key.

- [ ] **Step 5: Verify validation tests pass**

Run: `./venv/bin/pytest test/integration/user/test_user_registration.py test/integration/prekeys/test_prekey_upload.py test/integration/messaging/test_messaging.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add settings.py utils/validation.py .env.example database.py utils/redis_helper.py utils/constants.py server.py test/integration/user/test_user_registration.py test/integration/prekeys/test_prekey_upload.py test/integration/messaging/test_messaging.py
git commit -m "feat: add settings and API validation"
```

---

### Task 3: Add Signing-Based Authentication and Authorization

**Files:**
- Create: `auth.py`
- Modify: `models/database_models.py`
- Modify: `server.py`
- Modify: `chat_client.py`
- Modify: `test/conftest.py`
- Test: `test/integration/auth/test_auth.py`
- Test: `test/integration/messaging/test_messaging.py`
- Test: `test/integration/prekeys/test_prekey_upload.py`

**Interfaces:**
- Produces: `create_challenge(username: str) -> str`.
- Produces: `login_with_signature(username: str, challenge: str, signature: str, db: Session) -> str`.
- Produces: FastAPI dependency `get_current_username(authorization: str = Header(...)) -> str`.
- Produces: helper `require_same_user(expected_username: str, current_username: str) -> None`.

- [ ] **Step 1: Write failing auth tests**

Create `test/integration/auth/test_auth.py`:

```python
from nacl.signing import SigningKey
from utils.base_64_utils import bytes_to_base64_str

def test_login_with_valid_challenge_signature_returns_token(client):
    signing_key = SigningKey.generate()
    response = client.post("/register", json={
        "username": "alice",
        "public_key": bytes_to_base64_str(bytes(SigningKey.generate().verify_key)[:32]),
        "signing_public_key": bytes_to_base64_str(bytes(signing_key.verify_key)),
    })
    assert response.status_code == 200

    challenge = client.get("/auth/challenge/alice").json()["challenge"]
    signature = signing_key.sign(challenge.encode()).signature

    login = client.post("/auth/login", json={
        "username": "alice",
        "challenge": challenge,
        "signature": bytes_to_base64_str(signature),
    })

    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"

def test_login_rejects_invalid_signature(client, registered_user):
    username = registered_user()["username"]
    challenge = client.get(f"/auth/challenge/{username}").json()["challenge"]

    response = client.post("/auth/login", json={
        "username": username,
        "challenge": challenge,
        "signature": bytes_to_base64_str(b"0" * 64),
    })

    assert response.status_code == 401
```

Add to messaging tests:

```python
def test_send_message_rejects_missing_token(client, registered_user):
    sender = registered_user()
    recipient = registered_user("Bob")

    response = client.post("/send", json={
        "to": recipient["username"],
        "frm": sender["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    })

    assert response.status_code == 401
```

- [ ] **Step 2: Verify failing tests**

Run: `./venv/bin/pytest test/integration/auth/test_auth.py test/integration/messaging/test_messaging.py::TestSendMessage::test_send_message_rejects_missing_token -q`

Expected: FAIL because auth routes and protected send are missing.

- [ ] **Step 3: Add database field**

In `models/database_models.py`, add:

```python
signing_public_key = Column(String, nullable=True)
```

Keep nullable during migration-free development so existing local data does not break immediately. Validation will require it for new registrations.

- [ ] **Step 4: Implement auth manager**

Create `auth.py`:

```python
import base64
import secrets
from datetime import datetime, timedelta, UTC
from fastapi import Header, HTTPException
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from settings import settings

_challenges = {}
_tokens = {}

def create_challenge(username: str) -> str:
    challenge = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.challenge_ttl_seconds)
    _challenges[(username, challenge)] = expires_at
    return challenge

def verify_challenge_signature(username: str, challenge: str, signature: str, signing_public_key: str) -> None:
    expires_at = _challenges.pop((username, challenge), None)
    if expires_at is None or expires_at < datetime.now(UTC):
        raise HTTPException(401, "Invalid or expired challenge.")
    try:
        VerifyKey(base64.b64decode(signing_public_key.encode(), validate=True)).verify(
            challenge.encode(),
            base64.b64decode(signature.encode(), validate=True),
        )
    except (BadSignatureError, ValueError):
        raise HTTPException(401, "Invalid signature.")

def create_access_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.token_ttl_seconds)
    _tokens[token] = {"username": username, "expires_at": expires_at}
    return token

def verify_access_token(token: str) -> str:
    data = _tokens.get(token)
    if not data or data["expires_at"] < datetime.now(UTC):
        raise HTTPException(401, "Invalid or expired token.")
    return data["username"]

def get_current_username(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token.")
    return verify_access_token(authorization.removeprefix("Bearer ").strip())

def require_same_user(expected_username: str, current_username: str) -> None:
    if expected_username != current_username:
        raise HTTPException(403, "Token does not match requested user.")
```

- [ ] **Step 5: Add auth routes and protect routes**

In `server.py`, add request model:

```python
class LoginRequest(BaseModel):
    username: str
    challenge: str
    signature: str
```

Add routes:

```python
@app.get("/auth/challenge/{username}")
def get_auth_challenge(username: str, db: Session = Depends(get_database)):
    username = normalize_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    return {"username": username, "challenge": create_challenge(username)}

@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_database)):
    username = normalize_username(request.username)
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.signing_public_key:
        raise HTTPException(404, "User not found.")
    verify_challenge_signature(username, request.challenge, request.signature, user.signing_public_key)
    return {"access_token": create_access_token(username), "token_type": "bearer"}
```

Protect `POST /send`, `GET /inbox/{username}`, `GET /inbox/{username}/count`, and `POST /users/{username}/prekeys`:

```python
def send_message(
    message_request: MessageRequest,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    require_same_user(message_request.frm, current_username)
```

- [ ] **Step 6: Update test fixtures to produce tokens**

In `test/conftest.py`, extend `registered_user` to create signing keys and return `token`:

```python
signing_key = SigningKey.generate()
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
```

Return:

```python
"signing_key": signing_key,
"token": login.json()["access_token"]
```

Update protected test calls with headers:

```python
headers={"Authorization": f"Bearer {user['token']}"}
```

- [ ] **Step 7: Verify auth suite passes**

Run: `./venv/bin/pytest test/integration/auth test/integration/messaging test/integration/prekeys test/integration/user -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add auth.py models/database_models.py server.py chat_client.py test/conftest.py test/integration/auth/test_auth.py test/integration/messaging/test_messaging.py test/integration/prekeys/test_prekey_upload.py test/integration/user/test_user_registration.py
git commit -m "feat: add signed challenge authentication"
```

---

### Task 4: Add Message Status Tracking

**Files:**
- Modify: `models/database_models.py`
- Modify: `server.py`
- Modify: `utils/redis_helper.py`
- Test: `test/integration/messaging/test_messaging.py`

**Interfaces:**
- Produces message statuses: `queued`, `delivered`, `read`.
- Produces `POST /messages/{message_id}/read`.
- Produces `GET /messages/sent/{username}`.

- [ ] **Step 1: Write failing status tests**

Add to `test/integration/messaging/test_messaging.py`:

```python
def test_inbox_marks_message_delivered(client, registered_user):
    sender = registered_user()
    recipient = registered_user("Bob")

    send = client.post("/send", headers={"Authorization": f"Bearer {sender['token']}"}, json={
        "to": recipient["username"],
        "frm": sender["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    })
    message_id = send.json()["message_id"]

    inbox = client.get(f"/inbox/{recipient['username']}", headers={"Authorization": f"Bearer {recipient['token']}"})

    assert inbox.status_code == 200
    statuses = client.get(f"/messages/sent/{sender['username']}", headers={"Authorization": f"Bearer {sender['token']}"})
    assert statuses.json()["messages"][0]["id"] == message_id
    assert statuses.json()["messages"][0]["status"] == "delivered"

def test_mark_message_read_updates_status(client, registered_user):
    sender = registered_user()
    recipient = registered_user("Bob")

    send = client.post("/send", headers={"Authorization": f"Bearer {sender['token']}"}, json={
        "to": recipient["username"],
        "frm": sender["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    })
    message_id = send.json()["message_id"]

    response = client.post(f"/messages/{message_id}/read", headers={"Authorization": f"Bearer {recipient['token']}"})

    assert response.status_code == 200
    assert response.json()["status"] == "read"
```

- [ ] **Step 2: Verify failing tests**

Run: `./venv/bin/pytest test/integration/messaging/test_messaging.py::TestSendMessage::test_inbox_marks_message_delivered test/integration/messaging/test_messaging.py::TestSendMessage::test_mark_message_read_updates_status -q`

Expected: FAIL because send responses lack `message_id` and status endpoints do not exist.

- [ ] **Step 3: Add model fields**

In `models/database_models.py`, add:

```python
status = Column(String, default="queued", nullable=False)
delivered_at = Column(DateTime(timezone=True), nullable=True)
read_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Include message IDs in Redis envelopes and send response**

In `server.py`, after `db.commit()`:

```python
db.refresh(message)
push_message_to_inbox(message_request.to, {
    "id": message.id,
    "from": message_request.frm,
    "ciphertext": message_request.ciphertext,
    "prekey_id": message_request.prekey_id,
    "status": message.status,
})
return {"status": "sent", "message_id": message.id}
```

- [ ] **Step 5: Mark delivered on inbox retrieval**

In `get_inbox`, after Redis pop:

```python
message_ids = [item["id"] for item in inbox if "id" in item]
if message_ids:
    now = datetime.now(UTC)
    db.query(Message).filter(Message.id.in_(message_ids), Message.to_user == username).update(
        {"status": "delivered", "delivered_at": now},
        synchronize_session=False,
    )
    db.commit()
```

- [ ] **Step 6: Add read and sent status routes**

In `server.py`:

```python
@app.post("/messages/{message_id}/read")
def mark_message_read(message_id: int, db: Session = Depends(get_database), current_username: str = Depends(get_current_username)):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(404, "Message not found.")
    require_same_user(message.to_user, current_username)
    message.status = "read"
    message.read_at = datetime.now(UTC)
    if not message.delivered_at:
        message.delivered_at = message.read_at
    db.commit()
    return {"id": message.id, "status": message.status}

@app.get("/messages/sent/{username}")
def get_sent_messages(username: str, db: Session = Depends(get_database), current_username: str = Depends(get_current_username)):
    username = normalize_username(username)
    require_same_user(username, current_username)
    rows = db.query(Message).filter(Message.from_user == username).order_by(Message.created_at.desc()).all()
    return {"messages": [{"id": row.id, "to": row.to_user, "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}
```

- [ ] **Step 7: Verify status tests pass**

Run: `./venv/bin/pytest test/integration/messaging/test_messaging.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add models/database_models.py server.py utils/redis_helper.py test/integration/messaging/test_messaging.py
git commit -m "feat: track encrypted message status"
```

---

### Task 5: Add Prekey Health and CLI Identity Updates

**Files:**
- Modify: `server.py`
- Modify: `chat_client.py`
- Modify: `chat_script.py`
- Test: `test/integration/prekeys/test_get_prekey.py`

**Interfaces:**
- Produces `GET /users/{username}/prekeys/count` returning `{"username": str, "count": int, "low": bool}`.
- Produces CLI commands `prekeys` and `refill [count]`.
- Produces CLI auth header helper `ChatClient._auth_headers() -> dict`.

- [ ] **Step 1: Write failing prekey count test**

Add to `test/integration/prekeys/test_get_prekey.py`:

```python
def test_prekey_count_reports_unused_prekeys(client, registered_user, upload_prekeys):
    user = registered_user()
    upload_prekeys(user["username"], count=2)

    response = client.get(
        f"/users/{user['username']}/prekeys/count",
        headers={"Authorization": f"Bearer {user['token']}"},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["low"] is True
```

- [ ] **Step 2: Verify failing test**

Run: `./venv/bin/pytest test/integration/prekeys/test_get_prekey.py::TestGetPrekey::test_prekey_count_reports_unused_prekeys -q`

Expected: FAIL because the endpoint does not exist.

- [ ] **Step 3: Implement prekey count endpoint**

In `server.py`:

```python
@app.get("/users/{username}/prekeys/count")
def get_prekey_count(username: str, db: Session = Depends(get_database), current_username: str = Depends(get_current_username)):
    username = normalize_username(username)
    require_same_user(username, current_username)
    count = db.query(Prekey).filter(Prekey.username == username, Prekey.used == False).count()
    return {"username": username, "count": count, "low": count < 3}
```

- [ ] **Step 4: Update CLI key storage and auth**

In `chat_client.py`, add Ed25519 signing key generation and persistence:

```python
from nacl.signing import SigningKey

self.signing_key = SigningKey.generate()
self.signing_public_key = self.signing_key.verify_key
```

Persist:

```python
"signing_key": bytes_to_base64_str(bytes(self.signing_key)),
"signing_public_key": bytes_to_base64_str(bytes(self.signing_public_key)),
"token": getattr(self, "token", None),
```

Load:

```python
self.signing_key = SigningKey(base64_str_to_bytes(data["signing_key"]))
self.signing_public_key = self.signing_key.verify_key
self.token = data.get("token")
```

Add methods:

```python
def authenticate(self):
    challenge_response = requests.get(f"{API}/auth/challenge/{self.username}")
    challenge_response.raise_for_status()
    challenge = challenge_response.json()["challenge"]
    signature = self.signing_key.sign(challenge.encode()).signature
    login = requests.post(f"{API}/auth/login", json={
        "username": self.username,
        "challenge": challenge,
        "signature": bytes_to_base64_str(signature),
    })
    login.raise_for_status()
    self.token = login.json()["access_token"]
    self._save_keys()

def _auth_headers(self):
    if not getattr(self, "token", None):
        self.authenticate()
    return {"Authorization": f"Bearer {self.token}"}
```

Update protected requests to pass `headers=self._auth_headers()`.

- [ ] **Step 5: Add CLI commands**

In `chat_script.py`, add:

```python
elif command == "prekeys":
    client.show_prekey_health()
elif command.startswith("refill"):
    parts = command.split()
    count = int(parts[1]) if len(parts) > 1 else 5
    client.refill_prekeys(count)
```

In `chat_client.py`, implement:

```python
def show_prekey_health(self):
    response = requests.get(f"{API}/users/{self.username}/prekeys/count", headers=self._auth_headers())
    response.raise_for_status()
    data = response.json()
    print(f"[{self.username}] unused prekeys: {data['count']}")

def refill_prekeys(self, count: int = 5):
    self._gen_prekeys(count)
    response = requests.post(f"{API}/users/{self.username}/prekeys", headers=self._auth_headers(), json={"prekeys": self.prekeys_upload})
    response.raise_for_status()
    self._save_keys()
    print(f"[{self.username}] uploaded {count} prekeys")
```

- [ ] **Step 6: Verify tests pass**

Run: `./venv/bin/pytest test/integration/prekeys -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add server.py chat_client.py chat_script.py test/integration/prekeys/test_get_prekey.py
git commit -m "feat: add prekey health checks"
```

---

### Task 6: Add WebSocket Live Delivery

**Files:**
- Modify: `server.py`
- Test: `test/integration/messaging/test_messaging.py`

**Interfaces:**
- Produces `WebSocket /ws/{username}?token=<token>`.
- Produces in-process connection manager `ConnectionManager`.

- [ ] **Step 1: Write failing WebSocket test**

Add to `test/integration/messaging/test_messaging.py`:

```python
def test_websocket_receives_sent_message(client, registered_user):
    sender = registered_user()
    recipient = registered_user("Bob")

    with client.websocket_connect(f"/ws/{recipient['username']}?token={recipient['token']}") as websocket:
        send = client.post("/send", headers={"Authorization": f"Bearer {sender['token']}"}, json={
            "to": recipient["username"],
            "frm": sender["username"],
            "ciphertext": "YWJj",
            "prekey_id": "prekey123",
        })
        assert send.status_code == 200
        envelope = websocket.receive_json()

    assert envelope["from"] == sender["username"]
    assert envelope["ciphertext"] == "YWJj"
```

- [ ] **Step 2: Verify failing test**

Run: `./venv/bin/pytest test/integration/messaging/test_messaging.py::TestSendMessage::test_websocket_receives_sent_message -q`

Expected: FAIL because `/ws/{username}` is missing.

- [ ] **Step 3: Implement connection manager**

In `server.py`:

```python
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(username, []).append(websocket)

    def disconnect(self, username: str, websocket: WebSocket):
        connections = self.active_connections.get(username, [])
        if websocket in connections:
            connections.remove(websocket)

    async def send_to_user(self, username: str, payload: dict):
        for websocket in list(self.active_connections.get(username, [])):
            await websocket.send_json(payload)

manager = ConnectionManager()
```

Add WebSocket route:

```python
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str, token: str):
    username = normalize_username(username)
    current_username = verify_access_token(token)
    require_same_user(username, current_username)
    await manager.connect(username, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(username, websocket)
```

In `send_message`, after Redis push:

```python
payload = {
    "id": message.id,
    "from": message_request.frm,
    "ciphertext": message_request.ciphertext,
    "prekey_id": message_request.prekey_id,
    "status": message.status,
}
push_message_to_inbox(message_request.to, payload)
await manager.send_to_user(message_request.to, payload)
```

Convert `send_message` to `async def`.

- [ ] **Step 4: Verify WebSocket test passes**

Run: `./venv/bin/pytest test/integration/messaging/test_messaging.py::TestSendMessage::test_websocket_receives_sent_message -q`

Expected: PASS.

- [ ] **Step 5: Run messaging tests**

Run: `./venv/bin/pytest test/integration/messaging -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py test/integration/messaging/test_messaging.py
git commit -m "feat: stream encrypted messages over websocket"
```

---

### Task 7: Add Static Browser Demo

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`
- Modify: `server.py`

**Interfaces:**
- Produces browser demo at `GET /`.
- Consumes existing REST and WebSocket APIs.

- [ ] **Step 1: Add static file mount test**

Add to a new or existing integration test:

```python
def test_homepage_serves_browser_demo(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "EncryptoChat" in response.text
```

- [ ] **Step 2: Verify failing test**

Run: `./venv/bin/pytest test/integration/user/test_get_user.py::test_homepage_serves_browser_demo -q`

Expected: FAIL because `/` is not serving a page.

- [ ] **Step 3: Mount static files**

In `server.py`:

```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def homepage():
    return FileResponse("static/index.html")
```

- [ ] **Step 4: Create `static/index.html`**

Include:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EncryptoChat</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <main class="app-shell">
    <aside class="sidebar">
      <h1>EncryptoChat</h1>
      <section class="panel">
        <input id="username" aria-label="Username" autocomplete="username">
        <button id="registerBtn">Register / Login</button>
        <p id="authState">Signed out</p>
      </section>
      <section class="panel">
        <input id="contactName" aria-label="Contact username">
        <button id="addContactBtn">Open Contact</button>
        <div id="prekeyHealth"></div>
        <button id="refillPrekeysBtn">Refill Prekeys</button>
      </section>
    </aside>
    <section class="chat">
      <header>
        <h2 id="activeContact">No contact selected</h2>
        <p id="fingerprint"></p>
      </header>
      <div id="messages" class="messages"></div>
      <form id="composer">
        <input id="messageText" aria-label="Encrypted message" autocomplete="off">
        <button type="submit">Send</button>
      </form>
    </section>
    <aside class="details">
      <h2>Status</h2>
      <div id="statusList"></div>
    </aside>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 5: Create restrained responsive CSS**

Create `static/styles.css` with fixed tool dimensions, readable colors, and responsive layout:

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7f8; color: #1b1f23; }
.app-shell { min-height: 100vh; display: grid; grid-template-columns: 280px minmax(0, 1fr) 260px; }
.sidebar, .details { background: #ffffff; border-right: 1px solid #d7dde2; padding: 16px; }
.details { border-right: 0; border-left: 1px solid #d7dde2; }
h1, h2 { margin: 0 0 12px; font-size: 20px; letter-spacing: 0; }
.panel { margin-bottom: 16px; display: grid; gap: 8px; }
input, button { height: 40px; border-radius: 6px; font: inherit; }
input { border: 1px solid #bcc6cf; padding: 0 10px; min-width: 0; }
button { border: 1px solid #1d6f8f; background: #1d6f8f; color: #fff; padding: 0 12px; cursor: pointer; }
.chat { min-width: 0; display: grid; grid-template-rows: auto 1fr auto; }
.chat header { background: #ffffff; border-bottom: 1px solid #d7dde2; padding: 16px; }
.messages { padding: 16px; overflow: auto; display: grid; align-content: start; gap: 10px; }
.message { max-width: 70%; padding: 10px 12px; border-radius: 8px; background: #ffffff; border: 1px solid #d7dde2; }
.message.mine { margin-left: auto; background: #e7f3f7; border-color: #b8dbe7; }
#composer { display: grid; grid-template-columns: minmax(0, 1fr) 92px; gap: 8px; padding: 16px; background: #ffffff; border-top: 1px solid #d7dde2; }
@media (max-width: 860px) { .app-shell { grid-template-columns: 1fr; } .sidebar, .details { border: 0; border-bottom: 1px solid #d7dde2; } .message { max-width: 92%; } }
```

- [ ] **Step 6: Create browser demo JavaScript**

Create `static/app.js` using Web Crypto APIs for local demo key generation where possible. If PyNaCl-compatible browser encryption is unavailable without dependencies, implement the browser UI as a REST/WebSocket demo shell that stores and sends already-encrypted envelopes produced by the CLI-compatible API shape, and document the limitation in `docs/LEARNING_GUIDE.md`.

Required functions:

```javascript
const state = { username: "", token: "", contact: "", socket: null };

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function addMessage(text, mine = false) {
  const el = document.createElement("div");
  el.className = mine ? "message mine" : "message";
  el.textContent = text;
  document.querySelector("#messages").appendChild(el);
}
```

- [ ] **Step 7: Verify static page test passes**

Run: `./venv/bin/pytest test/integration/user/test_get_user.py::test_homepage_serves_browser_demo -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add server.py static/index.html static/styles.css static/app.js test/integration/user/test_get_user.py
git commit -m "feat: add browser chat demo"
```

---

### Task 8: Expand CI/CD Pipeline

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `README.md`

**Interfaces:**
- Produces GitHub Actions job that builds Docker image on PR/push.
- Produces GHCR publish job only on `main`.

- [ ] **Step 1: Update workflow**

Modify `.github/workflows/pipeline.yml` to add permissions:

```yaml
permissions:
  contents: read
  packages: write
```

Add Docker build validation after tests:

```yaml
    - name: Build Docker image
      run: |
        docker build -t encryptochat:${{ github.sha }} .
```

Add publish step guarded to `main`:

```yaml
    - name: Login to GitHub Container Registry
      if: github.ref == 'refs/heads/main' && github.event_name == 'push'
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Publish Docker image
      if: github.ref == 'refs/heads/main' && github.event_name == 'push'
      run: |
        IMAGE_NAME=ghcr.io/${{ github.repository_owner }}/encryptochat
        docker tag encryptochat:${{ github.sha }} $IMAGE_NAME:${{ github.sha }}
        docker tag encryptochat:${{ github.sha }} $IMAGE_NAME:latest
        docker push $IMAGE_NAME:${{ github.sha }}
        docker push $IMAGE_NAME:latest
```

- [ ] **Step 2: Validate workflow syntax locally**

Run: `./venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/pipeline.yml'))"`

Expected: exit code 0.

- [ ] **Step 3: Build Docker image locally**

Run: `docker build -t encryptochat:local .`

Expected: image builds successfully.

- [ ] **Step 4: Add README CI/CD note**

Add a section:

```markdown
## CI/CD

GitHub Actions runs the test suite against PostgreSQL and Redis service containers on pushes and pull requests. The pipeline also validates the Docker image build. Pushes to `main` publish a versioned image and `latest` tag to GitHub Container Registry.
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pipeline.yml README.md
git commit -m "ci: publish tested docker image"
```

---

### Task 9: Update README and Learning Guide

**Files:**
- Modify: `README.md`
- Create: `docs/LEARNING_GUIDE.md`

**Interfaces:**
- Produces resume/interview learning document.
- Produces current setup and demo docs.

- [ ] **Step 1: Update README**

Ensure README includes:

```markdown
## What This Demonstrates

- FastAPI API design with PostgreSQL and Redis.
- End-to-end encrypted message envelopes using PyNaCl.
- Signed challenge authentication with Ed25519.
- Real-time delivery over WebSockets.
- CI/CD with integration tests and Docker image publishing.
```

Update endpoint table to include auth, message status, prekey count, WebSocket, and browser demo.

- [ ] **Step 2: Create learning guide**

Create `docs/LEARNING_GUIDE.md` with these sections:

```markdown
# EncryptoChat Learning Guide

## Elevator Pitch

EncryptoChat is a Dockerized end-to-end encrypted chat demo built with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl. It demonstrates encrypted message envelopes, signed challenge authentication, one-time prekey exchange, real-time delivery, integration testing, and CI/CD container publishing.

## Architecture

The FastAPI server stores public identity material, one-time prekeys, encrypted message metadata, and message status. Redis acts as a fast inbox queue. Clients hold private keys locally and send only public keys, signatures, and ciphertext to the server.

## Message Lifecycle

1. Bob registers and uploads prekeys.
2. Alice retrieves Bob's public identity and one unused prekey.
3. Alice encrypts plaintext locally using PyNaCl.
4. Alice sends ciphertext to the server.
5. The server stores ciphertext and queues an envelope in Redis.
6. Bob receives the envelope through WebSocket or inbox polling.
7. Bob decrypts locally with the matching private prekey.
8. Status moves from queued to delivered to read.

## Security Model

The server cannot decrypt message bodies because private encryption keys stay on the client. Authentication uses a separate signing key so the server can verify user ownership without receiving a password or private key.

## Limitations

This is an educational secure messaging project. It does not implement the full Signal protocol, does not include a double ratchet, and does not hide metadata such as sender, recipient, or timestamps.

## Resume Bullets

- Built a Dockerized encrypted messaging platform with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl.
- Implemented signed challenge authentication using Ed25519 and protected user-scoped API routes with bearer tokens.
- Designed one-time prekey exchange for forward-secrecy-style message setup and tracked encrypted message delivery state.
- Built GitHub Actions CI/CD with PostgreSQL and Redis integration tests, coverage reporting, Docker build validation, and GHCR image publishing.

## Interview Talking Points

Explain why private keys stay on the client, why the server stores ciphertext only, why Redis is used for fast inbox delivery, and why WebSockets improve real-time behavior while polling remains a fallback.

## Demo Script

Run `docker compose up --build`, open `http://localhost:8000`, register Alice and Bob, exchange messages, show the database stores ciphertext, show prekey count changes, and point to GitHub Actions for CI/CD.
```

- [ ] **Step 3: Self-review docs**

Run: `rg -n "incomplete-section|needs-final-copy|unresolved-question" README.md docs/LEARNING_GUIDE.md`

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/LEARNING_GUIDE.md
git commit -m "docs: explain encryptochat capstone architecture"
```

---

### Task 10: Final Verification

**Files:**
- Verify all changed files.

**Interfaces:**
- Produces final confidence that capstone behavior works locally.

- [ ] **Step 1: Run full test suite**

Run: `./venv/bin/pytest -q`

Expected: PASS.

- [ ] **Step 2: Run coverage**

Run: `./venv/bin/pytest --cov=. --cov-report=term`

Expected: PASS with coverage output.

- [ ] **Step 3: Build Docker image**

Run: `docker build -t encryptochat:local .`

Expected: image builds successfully.

- [ ] **Step 4: Start stack**

Run: `docker compose up --build`

Expected: API starts on `http://localhost:8000`, Postgres is healthy, Redis is healthy.

- [ ] **Step 5: Manual browser demo**

Open `http://localhost:8000` and verify:

- Register/login works.
- Contact selection works.
- Prekey health displays.
- Refill prekeys works.
- Sending creates visible message output.
- WebSocket receives live message envelopes when both users are active.

- [ ] **Step 6: Manual CLI demo**

Run in two terminals:

```bash
python chat_script.py alice
python chat_script.py bob
```

Verify:

- `hi bob` succeeds.
- `msg bob hello` succeeds.
- `inbox` decrypts and displays messages.
- `prekeys` displays count.
- `refill 5` uploads more prekeys.

- [ ] **Step 7: Final git status check**

Run: `git status --short`

Expected: only intentional user changes remain uncommitted, or all capstone changes are committed.
