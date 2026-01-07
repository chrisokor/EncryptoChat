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
        client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # assert database can return the user
        user = db_session.query(User).filter(User.username == username).first()
        
        assert user is not None
        assert user.username == username
        assert user.public_key == bytes_to_base64_str(bytes(user_public_key))



    def test_register_duplicate_username_returns_400(self, client):
        # create user 1 and user 2, each with separate keys and using same username
        user1_secret_key = PrivateKey.generate()
        user1_public_key = user1_secret_key.public_key

        user2_secret_key = PrivateKey.generate()
        user2_public_key = user2_secret_key.public_key
        shared_username = "Alice"
        
        # register user 1 
        client.post("/register", json={
            "username": shared_username,
            "public_key": bytes_to_base64_str(bytes(user1_public_key))
        })

        # retrieve response for registering user 2
        response = client.post("/register", json={
            "username": shared_username,
            "public_key": bytes_to_base64_str(bytes(user2_public_key))
        })
         
        # assert response status code is 400 and returns "Username already exists."   
        assert response.status_code == 400
        assert response.json()["detail"] == "Username already exists."


    def test_register_missing_username_returns_422(self, client):
        # create user with blank username
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        blank_username = ""

        # register user and get response
        response = client.post("/register", json={
            "username": blank_username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })
         
        # assert response status code returns 422 and returns "Missing username."   
        assert response.status_code == 422
        assert response.json()["detail"] == "Missing username."


    def test_register_missing_public_key_returns_422(self, client):
        # create user with no public key
        blank_public_key = ""
        username = "Alice"

        # register user and get response
        response = client.post("/register", json={
            "username": username,
            "public_key": blank_public_key
        })

        # assert response status is 422 and returns "Missing public key."
        assert response.status_code == 422
        assert response.json()["detail"] == "Missing public key."

    def test_register_empty_body_returns_422(self, client):
        response = client.post("/register", json={})
        assert response.status_code == 422