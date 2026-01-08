


class TestSendMessage:

    def test_send_message_returns_success(self, client):
        pass

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