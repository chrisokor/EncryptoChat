import asyncio

import pytest
from nacl.public import PrivateKey
from nacl.signing import SigningKey

from server import ConnectionManager, manager, websocket_endpoint
from utils.base_64_utils import bytes_to_base64_str
from utils.redis_helper import push_message_to_inbox


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


def test_inbox_marks_message_delivered(client, registered_user, redis_client):
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


def test_mark_message_read_updates_status(client, registered_user, redis_client):
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


class TestSendMessage:
    def test_websocket_receives_sent_message(self, client, registered_user, redis_client):
        sender = registered_user
        recipient = register_and_login(client, "Bob")

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

    def test_live_message_marked_read_is_not_polled_or_regressed(self, client, registered_user, redis_client):
        sender = registered_user
        recipient = register_and_login(client, "Bob")

        with client.websocket_connect(f"/ws/{recipient['username']}?token={recipient['token']}") as websocket:
            send = client.post("/send", headers={"Authorization": f"Bearer {sender['token']}"}, json={
                "to": recipient["username"],
                "frm": sender["username"],
                "ciphertext": "YWJj",
                "prekey_id": "prekey123",
            })
            envelope = websocket.receive_json()
            read = client.post(
                f"/messages/{envelope['id']}/read",
                headers={"Authorization": f"Bearer {recipient['token']}"},
            )

        inbox = client.get(
            f"/inbox/{recipient['username']}",
            headers={"Authorization": f"Bearer {recipient['token']}"},
        )
        statuses = client.get(
            f"/messages/sent/{sender['username']}",
            headers={"Authorization": f"Bearer {sender['token']}"},
        )

        assert send.status_code == 200
        assert read.status_code == 200
        assert inbox.json()["inbox"] == []
        assert statuses.json()["messages"][0]["status"] == "read"


def test_inbox_poll_does_not_regress_read_status(client, registered_user, redis_client):
    sender = registered_user
    recipient = register_and_login(client, "Bob")
    payload = {
        "to": recipient["username"],
        "frm": sender["username"],
        "ciphertext": "YWJj",
        "prekey_id": "prekey123",
    }
    send = client.post(
        "/send",
        headers={"Authorization": f"Bearer {sender['token']}"},
        json=payload,
    )
    message_id = send.json()["message_id"]
    client.post(
        f"/messages/{message_id}/read",
        headers={"Authorization": f"Bearer {recipient['token']}"},
    )
    push_message_to_inbox(recipient["username"], {
        "id": message_id,
        "from": sender["username"],
        "ciphertext": payload["ciphertext"],
        "prekey_id": payload["prekey_id"],
        "status": "queued",
    })

    client.get(
        f"/inbox/{recipient['username']}",
        headers={"Authorization": f"Bearer {recipient['token']}"},
    )
    statuses = client.get(
        f"/messages/sent/{sender['username']}",
        headers={"Authorization": f"Bearer {sender['token']}"},
    )

    assert statuses.json()["messages"][0]["status"] == "read"


class FailingWebSocket:
    async def send_json(self, payload):
        raise RuntimeError("socket closed")


class RecordingWebSocket:
    def __init__(self):
        self.payloads = []

    async def send_json(self, payload):
        self.payloads.append(payload)


class ReceiveFailureWebSocket:
    async def accept(self):
        pass

    async def receive_text(self):
        raise RuntimeError("receive failed")


def test_connection_manager_removes_failed_socket_and_continues_broadcasting():
    connection_manager = ConnectionManager()
    failed_socket = FailingWebSocket()
    active_socket = RecordingWebSocket()
    payload = {"ciphertext": "YWJj"}
    connection_manager.active_connections["bob"] = [failed_socket, active_socket]

    asyncio.run(connection_manager.send_to_user("bob", payload))

    assert connection_manager.active_connections["bob"] == [active_socket]
    assert active_socket.payloads == [payload]


def test_websocket_endpoint_removes_connection_after_receive_error(client, registered_user):
    username = registered_user["username"]
    websocket = ReceiveFailureWebSocket()
    manager.active_connections.clear()

    with pytest.raises(RuntimeError, match="receive failed"):
        asyncio.run(websocket_endpoint(websocket, username, registered_user["token"]))

    assert username not in manager.active_connections
