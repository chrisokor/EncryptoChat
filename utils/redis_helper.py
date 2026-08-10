import json
import redis
from typing import List, Dict, Optional
from settings import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

def _inbox_key(username: str) -> str:
    """Generate Redis key for user's inbox queue"""
    return f"inbox:{username}"

def push_message_to_inbox(username: str, message: Dict) -> int:
    """Push message to user's Redis inbox queue"""
    key = _inbox_key(username)
    return redis_client.rpush(key, json.dumps(message))


def pop_all_inbox_messages(username: str) -> List[Dict]:
    """Pop all messages from user's inbox and return them"""
    key = _inbox_key(username)
    messages = []

    # get all messages
    raw_messages = redis_client.lrange(key, 0, -1)

    # delete list
    if raw_messages:
        redis_client.delete(key)
        messages = [json.loads(message) for message in raw_messages]
    
    return messages

def get_inbox_count(username: str) -> int:
    """Get count of pending messages in inbox"""
    return redis_client.llen(_inbox_key(username))


def clear_inbox(username: str) -> bool:
    """Clear all messages from inbox"""
    return redis_client.delete(_inbox_key(username)) > 0
