from uuid import uuid4
from nacl.public import PrivateKey
from utils.base_64_utils import bytes_to_base64_str
from models.database_models import Prekey

class TestPrekeyUpload:

    def test_upload_prekeys_returns_success(self, client, registered_user):
        # register user 
        username = registered_user["username"]

        # create list of prekeys
        prekeys = []
        for _ in range(5):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4().hex,
                "key": bytes_to_base64_str(bytes(prekey))
            })
            

        # upload prekeys
        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        })

        # assert successful response
        assert response.status_code == 200
        assert response.json()["ok"] == True


    def test_upload_prekeys_persists_to_database(self, client, db_session, registered_user):
        # register user
        username = registered_user["username"]

        # create prekey list and upload
        prekeys = []
        for _ in range(5):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4().hex,
                "key": bytes_to_base64_str(bytes(prekey))
            })

        client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        })

        # assert prekey data in database
        num_prekeys_in_database = db_session.query(Prekey).filter(Prekey.username == username, Prekey.used == False).count()
        assert num_prekeys_in_database == 5 

    def test_upload_prekeys_for_nonexistent_user_returns_404(self, client):
        # create nonexisting username
        username = "Bob" 

        # create prekey list and attempt upload
        prekeys = []
        for _ in range(5):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4().hex,
                "key": bytes_to_base64_str(bytes(prekey))
            })

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        })

        # assert response status code is 404 and returns "User not found."
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found." 

    def test_upload_multiple_batches_accumulates_count(self, client, registered_user):
        # register user
        username = registered_user["username"]

        # create 15 prekeys among 3 lists (5 each)
        prekeys_batch1, prekeys_batch2, prekeys_batch3 = [], [], []
        for num in range(15):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            if num < 5:
                prekeys_batch1.append({
                    "id": uuid4().hex,
                    "key": bytes_to_base64_str(bytes(prekey))
                })
            elif num >= 5 and num < 10:
                prekeys_batch2.append({
                    "id": uuid4().hex,
                    "key": bytes_to_base64_str(bytes(prekey))
                })
            else:
                prekeys_batch3.append({
                    "id": uuid4().hex,
                    "key": bytes_to_base64_str(bytes(prekey))
                })

        # upload each list separately and assert counts are 5, 10, and 15
        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys_batch1
        })
        assert response.json()["count"] == 5

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys_batch2
        })
        assert response.json()["count"] == 10

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys_batch3
        })
        assert response.json()["count"] == 15



    def test_upload_prekeys_with_empty_prekeys_list_returns_422(self, client, registered_user):
        # register user
        username = registered_user["username"]

        # attempt prekey upload with empty list
        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": []
        })

        # assert status code is 422 and returns "Prekey list cannot be empty."
        assert response.status_code == 422
        assert response.json()["detail"] == "Prekeys list cannot be empty."

    def test_upload_invalid_prekey_returns_422(self, client, registered_user):
        username = registered_user["username"]

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": [{"id": "bad id", "key": "not-base64"}]
        })

        assert response.status_code == 422
