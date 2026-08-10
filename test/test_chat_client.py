import json

from nacl.public import PrivateKey

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
