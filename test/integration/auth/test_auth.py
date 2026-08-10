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
    challenge = client.get(f"/auth/challenge/{registered_user['username']}").json()["challenge"]

    response = client.post("/auth/login", json={
        "username": registered_user["username"],
        "challenge": challenge,
        "signature": bytes_to_base64_str(b"0" * 64),
    })

    assert response.status_code == 401
