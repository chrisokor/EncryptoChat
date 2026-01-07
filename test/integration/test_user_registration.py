import pytest
import uuid
from nacl.public import PrivateKey
from utils.base_64_utils import bytes_to_base64_str
from models.database_models import User



class TestUserRegistration:

    def test_register_new_user_returns_success(self, client):
        # get keys
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key

        # make API request
        response = client.post("/register", json={
            "username": "Alice",
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # assert successful response
        assert response.status_code == 200
        assert response.json()["status"] == "registered"


    def test_register_user_persists_to_database(self, client, db_session):
        # create keys
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        username = "Alice"

        # register user
        response = client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # assert database can return the user
        user = db_session.query(User).filter(User.username == username).first() is not None
        
        assert user is not None
        assert user.username == username
        assert user.public_key == bytes_to_base64_str(bytes(user_public_key))



    def  test_register_duplicate_username_returns_400(self):
        pass 


    def test_register_missing_username_returns_422(self):
        pass


    def test_register_empty_body_returns_422(self):
        pass