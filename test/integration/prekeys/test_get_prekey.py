from models.database_models import Prekey
from nacl.public import PrivateKey
from nacl.signing import SigningKey
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from server import _consume_prekey_for_user
from utils.base_64_utils import bytes_to_base64_str
from uuid import uuid4


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

class TestGetPrekey:

    def test_prekey_count_reports_unused_prekeys(self, client, registered_user, upload_prekeys):
        user = registered_user
        upload_prekeys(user, count=2)

        response = client.get(
            f"/users/{user['username']}/prekeys/count",
            headers={"Authorization": f"Bearer {user['token']}"},
        )

        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert response.json()["low"] is True

    def test_get_user_keys_alias_returns_and_consumes_prekey(self, client, registered_user, upload_prekeys):
        username = registered_user["username"]
        uploaded = upload_prekeys(registered_user)["prekeys"]
        headers = {"Authorization": f"Bearer {registered_user['token']}"}

        response = client.get(f"/users/{username}/keys", headers=headers)

        assert response.status_code == 200
        assert response.json()["username"] == username.lower()
        assert response.json()["prekey"]["id"] == uploaded[0]["id"]

        next_response = client.get(f"/users/{username}/keys", headers=headers)

        assert next_response.status_code == 200
        assert next_response.json()["prekey"]["id"] == uploaded[1]["id"]

    def test_get_prekey_returns_success(self, client, registered_user, upload_prekeys):
        # register user and upload prekeys
        username = registered_user["username"]
        prekey_upload = upload_prekeys(registered_user)

        # get prekey 
        response = client.get(
            f"/users/{username}/prekeys",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
        )
        retreived_prekey = response.json()["prekey"]

        uploaded_prekey_ids = [prekey["id"] for prekey in prekey_upload["prekeys"]]

        # assert successful prekey retrieval
        assert response.status_code == 200
        assert retreived_prekey["id"] in uploaded_prekey_ids

    def test_get_prekey_marks_prekey_as_used(self, client, db_session, registered_user, upload_prekeys):
        # register and upload keys
        username = registered_user["username"]
        prekey_upload = upload_prekeys(registered_user)

        # get prekey and id
        response = client.get(
            f"/users/{username}/prekeys",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
        )
        retrieved_prekey_id = response.json()["prekey"]["id"]

        # assert prekey is marked as used in the database
        prekey = db_session.query(Prekey).filter(Prekey.username == username, Prekey.id == retrieved_prekey_id).first()
        assert prekey.used == True

    def test_get_prekey_for_nonexisting_user_returns_404(self, client, registered_user):
        # set nonexisting user
        nonexisting_username = "Bob"

        # attempt to get prekeys
        response = client.get(
            f"/users/{nonexisting_username}/prekeys",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
        )

        # assert appropriate error response is returned
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."


    def test_get_prekey_with_no_available_prekeys_returns_410(self, client, registered_user):
        # register
        username = registered_user["username"]

        # attempt to get prekey
        response = client.get(
            f"/users/{username}/prekeys",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
        )

        # assert status code is 410 and returns "No prekeys available."
        assert response.status_code == 410
        assert response.json()["detail"] == "No prekeys available."


    def test_get_prekey_consumes_prekeys_first_in_first_out(self, client, db_session, registered_user, ):
        # register, manually create prekey list, and upload (3)
        username = registered_user["username"]

        prekeys = []
        for _ in range(3):
            secret_key = PrivateKey.generate()
            key = secret_key.public_key
            prekeys.append({
                "id": uuid4().hex,
                "key": bytes_to_base64_str(bytes(key))
            })

        client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        }, headers={"Authorization": f"Bearer {registered_user['token']}"})

        # mark prekeys 1, 2, and 3
        prekey1, prekey2, prekey3 = prekeys[0], prekeys[1], prekeys[2]


        # perform GET calls and assert appropriate prekey is consumed
        headers = {"Authorization": f"Bearer {registered_user['token']}"}
        response = client.get(f"/users/{username}/prekeys", headers=headers)
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey1["id"]

        response = client.get(f"/users/{username}/prekeys", headers=headers)
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey2["id"]

        response = client.get(f"/users/{username}/prekeys", headers=headers)
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey3["id"]

    def test_prekey_consumption_endpoints_require_authentication(
        self, client, registered_user, upload_prekeys
    ):
        upload_prekeys(registered_user)

        for endpoint in ("prekeys", "keys"):
            response = client.get(f"/users/{registered_user['username']}/{endpoint}")

            assert response.status_code == 401

    def test_authenticated_user_can_consume_another_users_prekey(
        self, client, registered_user, upload_prekeys
    ):
        recipient = registered_user
        uploaded = upload_prekeys(recipient)["prekeys"]

        requester = register_and_login(client, "Bob")
        response = client.get(
            f"/users/{recipient['username']}/keys",
            headers={"Authorization": f"Bearer {requester['token']}"},
        )

        assert response.status_code == 200
        assert response.json()["username"] == recipient["username"]
        assert response.json()["prekey"]["id"] == uploaded[0]["id"]

    def test_prekey_consumption_skips_a_locked_row(
        self, client, test_engine, registered_user, upload_prekeys
    ):
        upload_prekeys(registered_user, count=2)
        SessionLocal = sessionmaker(bind=test_engine)
        lock_session = SessionLocal()
        consume_session = SessionLocal()

        try:
            locked = (
                lock_session.query(Prekey)
                .filter(Prekey.username == registered_user["username"], Prekey.used == False)
                .order_by(Prekey.created_at)
                .with_for_update()
                .first()
            )
            consume_session.execute(text("SET LOCAL lock_timeout = '100ms'"))

            consumed = _consume_prekey_for_user(registered_user["username"], consume_session)

            assert consumed["prekey"]["id"] != locked.id
        finally:
            lock_session.rollback()
            consume_session.rollback()
            lock_session.close()
            consume_session.close()
