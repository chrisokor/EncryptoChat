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
    return {"username": username.lower(), "token": login.json()["access_token"]}


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


def test_inbox_marks_message_delivered(client, registered_user):
    sender = registered_user
    recipient = register_and_login(client, "Bob")

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
    sender = registered_user
    recipient = register_and_login(client, "Bob")

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
