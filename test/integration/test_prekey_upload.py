from uuid import uuid4
from nacl.public import PrivateKey
from utils.base_64_utils import bytes_to_base64_str
from models.database_models import Prekey

class TestPrekeyUpload:

    def test_upload_prekeys_returns_success(self, client):
        # register user 
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        username = "Alice"
        client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # create list of prekeys
        prekeys = []
        for _ in range(5):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4.hex(),
                "key": prekey
            })
            

        # upload prekeys
        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": bytes_to_base64_str(bytes(prekeys))
        })

        # assert successful response
        assert response.status_code == 200
        assert response.json()["ok"] == True


    def test_upload_prekeys_persists_to_database(self, client, db_session):
        # register user
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        username = "Alice"
        client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # create prekey list and upload
        prekeys = []
        for _ in range(5):
            secret_key = PrivateKey.generate()
            prekey = secret_key.public_key
            prekeys.append({
                "id": uuid4.hex(),
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
                "id": uuid4.hex(),
                "key": bytes_to_base64_str(bytes(prekey))
            })

        response = client.post(f"/users/{username}/prekeys", json={
            "prekeys": prekeys
        })

        # assert response status code is 404 and returns "User not found."
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found." 

    def test_upload_multiple_batches_accumulates_count(self, client):
        # register user

        # create 15 prekeys among 3 lists (5 each)

        # upload each list separately

        # assert 2nd response count is 10 and final count is 15

    def test_upload_prekeys_with_empty_prekeys_list_returns_422(self, client):
        # register user

        # attempt prekey upload with empty list

        # assert status code is 422 and returns "Prekey list cannot be empty."