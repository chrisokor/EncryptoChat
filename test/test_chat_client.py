import json

from nacl.public import PrivateKey
import requests

from chat_client import ChatClient
from utils.base_64_utils import bytes_to_base64_str


def test_client_migrates_legacy_key_file_with_signing_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    key_directory = tmp_path / ".keys"
    key_directory.mkdir()
    private_key = PrivateKey.generate()
    legacy_data = {
        "secret_key": bytes_to_base64_str(bytes(private_key)),
        "public_key": bytes_to_base64_str(bytes(private_key.public_key)),
        "prekeys": {},
    }
    (key_directory / "alice.json").write_text(json.dumps(legacy_data))

    ChatClient("alice")

    migrated_data = json.loads((key_directory / "alice.json").read_text())
    assert migrated_data["signing_key"]
    assert "generated a new signing key" in capsys.readouterr().out


def test_prekey_health_reauthenticates_after_restored_token_returns_401(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    client = ChatClient("alice", prekey_count=0)
    client.token = "stale-token"
    client._save_keys()

    restored_client = ChatClient("alice", prekey_count=0)
    health_request_headers = []

    class Response:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self.data = data

        def json(self):
            return self.data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError()

    def fake_get(url, headers=None):
        if url.endswith("/auth/challenge/alice"):
            return Response(200, {"challenge": "challenge"})
        health_request_headers.append(headers)
        if len(health_request_headers) == 1:
            return Response(401, {})
        return Response(200, {"count": 4})

    def fake_post(url, json):
        assert url.endswith("/auth/login")
        return Response(200, {"access_token": "fresh-token"})

    monkeypatch.setattr("chat_client.requests.get", fake_get)
    monkeypatch.setattr("chat_client.requests.post", fake_post)

    restored_client.show_prekey_health()

    assert health_request_headers == [
        {"Authorization": "Bearer stale-token"},
        {"Authorization": "Bearer fresh-token"},
    ]
    assert restored_client.token == "fresh-token"
    assert json.loads((tmp_path / ".keys" / "alice.json").read_text())["token"] == "fresh-token"
    assert "unused prekeys: 4" in capsys.readouterr().out
