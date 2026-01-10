from models.database_models import Prekey
from nacl.public import PrivateKey
from utils.base_64_utils import bytes_to_base64_str
from uuid import uuid4

class TestGetPrekey:

    def test_get_prekey_returns_success(self, client, registered_user, upload_prekeys):
        # register user and upload prekeys
        username = registered_user["username"]
        prekey_upload = upload_prekeys(username)

        # get prekey 
        response = client.get(f"/users/{username}/prekeys")
        retreived_prekey = response.json()["prekey"]

        uploaded_prekey_ids = [prekey["id"] for prekey in prekey_upload["prekeys"]]

        # assert successful prekey retrieval
        assert response.status_code == 200
        assert retreived_prekey["id"] in uploaded_prekey_ids

    def test_get_prekey_marks_prekey_as_used(self, client, db_session, registered_user, upload_prekeys):
        # register and upload keys
        username = registered_user["username"]
        prekey_upload = upload_prekeys(username)

        # get prekey and id
        response = client.get(f"/users/{username}/prekeys")
        retrieved_prekey_id = response.json()["prekey"]["id"]

        # assert prekey is marked as used in the database
        prekey = db_session.query(Prekey).filter(Prekey.username == username, Prekey.id == retrieved_prekey_id).first()
        assert prekey.used == True

    def test_get_prekey_for_nonexisting_user_returns_404(self, client):
        # set nonexisting user
        nonexisting_username = "Bob"

        # attempt to get prekeys
        response = client.get(f"/users/{nonexisting_username}/prekeys")

        # assert appropriate error response is returned
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."


    def test_get_prekey_with_no_available_prekeys_returns_410(self, client, registered_user):
        # register
        username = registered_user["username"]

        # attempt to get prekey
        response = client.get(f"/users/{username}/prekeys")

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
        })

        # mark prekeys 1, 2, and 3
        prekey1, prekey2, prekey3 = prekeys[0], prekeys[1], prekeys[2]


        # perform GET calls and assert appropriate prekey is consumed
        response = client.get(f"/users/{username}/prekeys")
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey1["id"]

        response = client.get(f"/users/{username}/prekeys")
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey2["id"]

        response = client.get(f"/users/{username}/prekeys")
        prekey_id = response.json()["prekey"]["id"]
        assert prekey_id == prekey3["id"]

