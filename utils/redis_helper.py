import json
import redis
from typing import List, Dict
from settings import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

_DRAIN_INBOX_SCRIPT = """
local messages = redis.call('LRANGE', KEYS[1], 0, -1)
if #messages > 0 then
    redis.call('DEL', KEYS[1])
end
return messages
"""

_REMOVE_MESSAGE_SCRIPT = """
local messages = redis.call('LRANGE', KEYS[1], 0, -1)
if #messages == 0 then
    return 0
end

redis.call('DEL', KEYS[1])
local removed = 0
for _, message in ipairs(messages) do
    local ok, envelope = pcall(cjson.decode, message)
    if ok and tostring(envelope.id) == ARGV[1] then
        removed = removed + 1
    else
        redis.call('RPUSH', KEYS[1], message)
    end
end
return removed
"""

def _inbox_key(username: str) -> str:
    """Generate Redis key for user's inbox queue"""
    return f"inbox:{username}"

def push_message_to_inbox(username: str, message: Dict) -> int:
    """Push message to user's Redis inbox queue"""
    key = _inbox_key(username)
    return redis_client.rpush(key, json.dumps(message))


def pop_all_inbox_messages(username: str) -> List[Dict]:
    """Atomically drain all messages from a user's inbox."""
    key = _inbox_key(username)
    raw_messages = redis_client.eval(_DRAIN_INBOX_SCRIPT, 1, key)
    return [json.loads(message) for message in raw_messages]


def restore_inbox_messages(username: str, messages: List[Dict]) -> int:
    """Restore a failed drain ahead of messages queued after it."""
    if not messages:
        return 0
    serialized = [json.dumps(message) for message in reversed(messages)]
    return redis_client.lpush(_inbox_key(username), *serialized)


def remove_message_from_inbox(username: str, message_id: int) -> int:
    """Atomically remove every queued copy of a message."""
    return redis_client.eval(
        _REMOVE_MESSAGE_SCRIPT,
        1,
        _inbox_key(username),
        str(message_id),
    )

def get_inbox_count(username: str) -> int:
    """Get count of pending messages in inbox"""
    return redis_client.llen(_inbox_key(username))


def clear_inbox(username: str) -> bool:
    """Clear all messages from inbox"""
    return redis_client.delete(_inbox_key(username)) > 0
