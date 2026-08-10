import hashlib

from nacl.public import PrivateKey
from nacl.signing import SigningKey
from utils.base_64_utils import bytes_to_base64_str


def test_homepage_serves_browser_demo(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "EncryptoChat" in response.text


def test_browser_demo_uses_server_statuses_and_plaintext_envelope_copy(client):
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/messages/sent/" in response.text
    assert "Encrypted envelope" not in response.text
    assert "base64-encoded plaintext" in response.text


class TestGetUser:

    def test_get_existing_user_returns_user_data(self, client):
        # create and register a user
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        username = "Alice"
        signing_public_key = bytes(SigningKey.generate().verify_key)

        client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key)),
            "signing_public_key": bytes_to_base64_str(signing_public_key),
        })

        # retrieve user via GET request
        response = client.get(f"/users/{username}")


        # assert proper user data is returned in response
        assert response.status_code == 200
        assert response.json()["username"] == username.lower()
        assert response.json()["public_key"] == bytes_to_base64_str(bytes(user_public_key))
        assert response.json()["signing_public_key"] == bytes_to_base64_str(signing_public_key)
        identity_material = (
            b"encryptochat-safety-fingerprint-v1\0"
            + bytes(user_public_key)
            + signing_public_key
        )
        expected = hashlib.sha256(identity_material).hexdigest().upper()
        expected = " ".join(expected[index:index + 4] for index in range(0, len(expected), 4))
        assert response.json()["fingerprint"] == expected


    def test_get_nonexistent_user_returns_404(self, client):
        # attempt to retrieve nonexistent user via GET request
        nonexisting_username = "Bob"

        response = client.get(f"/users/{nonexisting_username}")

        # assert response status code is 404 and returns "User not found."
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."

    def test_get_user_with_invalid_username_returns_422(self, client):
        response = client.get("/users/1bad")

        assert response.status_code == 422
        assert response.json()["detail"] == (
            "Username must start with a letter and contain 3-32 letters, numbers, or underscores."
        )
