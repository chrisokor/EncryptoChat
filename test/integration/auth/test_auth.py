from datetime import UTC, datetime, timedelta
from uuid import uuid4

import auth
from nacl.public import PrivateKey
from nacl.signing import SigningKey

from utils.base_64_utils import bytes_to_base64_str


def register_and_login(client, username):
    signing_key = SigningKey.generate()
    response = client.post("/register", json={
        "username": username,
        "public_key": bytes_to_base64_str(bytes(PrivateKey.generate().public_key)),
        "signing_public_key": bytes_to_base64_str(bytes(signing_key.verify_key)),
    })
    assert response.status_code == 200

    challenge = client.get(f"/auth/challenge/{username}").json()["challenge"]
    signature = signing_key.sign(challenge.encode()).signature
    login = client.post("/auth/login", json={
        "username": username,
        "challenge": challenge,
        "signature": bytes_to_base64_str(signature),
    })
    assert login.status_code == 200
    return {"username": username, "token": login.json()["access_token"]}


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
    challenge = client.get(f"/auth/challenge/{registered_user['username']}").json()["challenge"]

    response = client.post("/auth/login", json={
        "username": registered_user["username"],
        "challenge": challenge,
        "signature": bytes_to_base64_str(b"0" * 64),
    })

    assert response.status_code == 401


def test_login_rejects_replayed_challenge(client, registered_user):
    challenge = client.get(f"/auth/challenge/{registered_user['username']}").json()["challenge"]
    signature = registered_user["signing_key"].sign(challenge.encode()).signature
    payload = {
        "username": registered_user["username"],
        "challenge": challenge,
        "signature": bytes_to_base64_str(signature),
    }

    assert client.post("/auth/login", json=payload).status_code == 200
    assert client.post("/auth/login", json=payload).status_code == 401


def test_protected_routes_reject_invalid_token(client, registered_user):
    response = client.get(
        f"/inbox/{registered_user['username']}",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_alice_token_cannot_send_as_bob(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")

    response = client.post("/send", json={
        "to": alice["username"],
        "frm": bob["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    }, headers={"Authorization": f"Bearer {alice['token']}"})

    assert response.status_code == 403


def test_alice_token_cannot_retrieve_bob_inbox_or_count(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")
    headers = {"Authorization": f"Bearer {alice['token']}"}

    assert client.get(f"/inbox/{bob['username']}", headers=headers).status_code == 403
    assert client.get(f"/inbox/{bob['username']}/count", headers=headers).status_code == 403


def test_alice_token_cannot_upload_bob_prekeys(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")

    response = client.post(f"/users/{bob['username']}/prekeys", json={
        "prekeys": [{
            "id": uuid4().hex,
            "key": bytes_to_base64_str(bytes(PrivateKey.generate().public_key)),
        }],
    }, headers={"Authorization": f"Bearer {alice['token']}"})

    assert response.status_code == 403


def test_create_challenge_purges_expired_entries(monkeypatch):
    auth._challenges.clear()
    auth._challenges[("expired", "challenge")] = datetime.now(UTC) - timedelta(seconds=1)
    monkeypatch.setattr(auth, "MAX_CHALLENGES", 1)

    auth.create_challenge("alice")

    assert len(auth._challenges) == 1
    assert all(expires_at >= datetime.now(UTC) for expires_at in auth._challenges.values())


def test_create_challenge_replaces_oldest_entry_when_store_is_full(monkeypatch):
    auth._challenges.clear()
    monkeypatch.setattr(auth, "MAX_CHALLENGES", 2)

    first = auth.create_challenge("alice")
    auth.create_challenge("bob")
    auth.create_challenge("charlie")

    assert len(auth._challenges) == 2
    assert ("alice", first) not in auth._challenges


def test_create_access_token_purges_expired_entries(monkeypatch):
    auth._tokens.clear()
    auth._tokens["expired"] = {
        "username": "alice",
        "expires_at": datetime.now(UTC) - timedelta(seconds=1),
    }
    monkeypatch.setattr(auth, "MAX_TOKENS", 1)

    auth.create_access_token("alice")

    assert len(auth._tokens) == 1
    assert all(data["expires_at"] >= datetime.now(UTC) for data in auth._tokens.values())


def test_create_access_token_replaces_oldest_entry_when_store_is_full(monkeypatch):
    auth._tokens.clear()
    monkeypatch.setattr(auth, "MAX_TOKENS", 2)

    first = auth.create_access_token("alice")
    auth.create_access_token("bob")
    auth.create_access_token("charlie")

    assert len(auth._tokens) == 2
    assert first not in auth._tokens
