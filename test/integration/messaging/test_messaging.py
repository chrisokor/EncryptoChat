from nacl.public import PrivateKey
from nacl.signing import SigningKey

from utils.base_64_utils import bytes_to_base64_str


def test_send_message_rejects_missing_token(client, registered_user):
    sender = registered_user
    recipient_key = PrivateKey.generate().public_key
    recipient = "bob"
    client.post("/register", json={
        "username": recipient,
        "public_key": bytes_to_base64_str(bytes(recipient_key)),
        "signing_public_key": bytes_to_base64_str(bytes(SigningKey.generate().verify_key)),
    })

    response = client.post("/send", json={
        "to": recipient,
        "frm": sender["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    })

    assert response.status_code == 401


def test_send_message_rejects_invalid_ciphertext(client, registered_user):
    sender = registered_user
    recipient_key = PrivateKey.generate().public_key
    recipient = "Bob"
    client.post("/register", json={
        "username": recipient,
        "public_key": bytes_to_base64_str(bytes(recipient_key)),
        "signing_public_key": bytes_to_base64_str(bytes(SigningKey.generate().verify_key)),
    })

    response = client.post("/send", json={
        "to": recipient,
        "frm": sender["username"],
        "ciphertext": "not-base64",
        "prekey_id": "prekey_01",
    }, headers={"Authorization": f"Bearer {sender['token']}"})

    assert response.status_code == 422
