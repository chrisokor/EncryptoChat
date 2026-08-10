from nacl.public import PrivateKey
from nacl.signing import SigningKey
from utils.base_64_utils import bytes_to_base64_str


class TestSendMessage:

    def test_send_message_returns_success(self, client):
        # register users
        from_secret_key = PrivateKey.generate()
        from_public_key = from_secret_key.public_key
        from_username = "Alice"
        client.post("/register", json={
            "username": from_username,
            "public_key": bytes_to_base64_str(bytes(from_public_key)),
            "signing_public_key": bytes_to_base64_str(bytes(SigningKey.generate().verify_key)),
        })

        to_secret_key = PrivateKey.generate()
        to_public_key = to_secret_key.public_key
        to_username = "Bob"
        client.post("/register", json={
            "username": to_username,
            "public_key": bytes_to_base64_str(bytes(to_public_key)),
            "signing_public_key": bytes_to_base64_str(bytes(SigningKey.generate().verify_key)),
        })

        # to_user uploads prekeys
        


        client.post("/send", json={

        })


    def test_send_message_persists_to_database(self, client):
        pass

    def test_send_message_pushes_to_redis_inbox(self, client):
        pass

    def test_send_message_to_nonexistent_user_returns_404(self, client):
        pass

    def test_send_multiple_messages_to_same_user(self, client):
        pass

    def test_send_message_missing_required_fields_returns_422(self, client):
        pass
