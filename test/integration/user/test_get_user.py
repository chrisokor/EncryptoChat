from nacl.public import PrivateKey
from utils.base_64_utils import bytes_to_base64_str


class TestGetUser:

    def test_get_existing_user_returns_user_data(self, client):
        # create and register a user
        user_secret_key = PrivateKey.generate()
        user_public_key = user_secret_key.public_key
        username = "Alice"

        client.post("/register", json={
            "username": username,
            "public_key": bytes_to_base64_str(bytes(user_public_key))
        })

        # retrieve user via GET request
        response = client.get(f"/users/{username}")


        # assert proper user data is returned in response
        assert response.status_code == 200
        assert response.json()["username"] == username.lower()
        assert response.json()["public_key"] == bytes_to_base64_str(bytes(user_public_key))


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
