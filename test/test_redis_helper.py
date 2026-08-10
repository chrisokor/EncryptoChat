import json

from utils import redis_helper


def test_pop_all_inbox_messages_uses_one_atomic_redis_script(monkeypatch):
    calls = []

    class FakeRedis:
        def eval(self, script, key_count, key):
            calls.append((script, key_count, key))
            return [json.dumps({"id": 1}), json.dumps({"id": 2})]

    monkeypatch.setattr(redis_helper, "redis_client", FakeRedis())

    result = redis_helper.pop_all_inbox_messages("alice")

    assert result == [{"id": 1}, {"id": 2}]
    assert len(calls) == 1
    assert calls[0][1:] == (1, "inbox:alice")
