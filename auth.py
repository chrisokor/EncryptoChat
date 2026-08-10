import base64
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Header, HTTPException
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from settings import settings


_challenges = {}
_tokens = {}


def create_challenge(username: str) -> str:
    challenge = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.challenge_ttl_seconds)
    _challenges[(username, challenge)] = expires_at
    return challenge


def verify_challenge_signature(
    username: str,
    challenge: str,
    signature: str,
    signing_public_key: str,
) -> None:
    expires_at = _challenges.pop((username, challenge), None)
    if expires_at is None or expires_at < datetime.now(UTC):
        raise HTTPException(401, "Invalid or expired challenge.")
    try:
        VerifyKey(base64.b64decode(signing_public_key.encode(), validate=True)).verify(
            challenge.encode(),
            base64.b64decode(signature.encode(), validate=True),
        )
    except (BadSignatureError, ValueError):
        raise HTTPException(401, "Invalid signature.")


def create_access_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.token_ttl_seconds)
    _tokens[token] = {"username": username, "expires_at": expires_at}
    return token


def verify_access_token(token: str) -> str:
    data = _tokens.get(token)
    if not data or data["expires_at"] < datetime.now(UTC):
        raise HTTPException(401, "Invalid or expired token.")
    return data["username"]


def get_current_username(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token.")
    return verify_access_token(authorization.removeprefix("Bearer ").strip())


def require_same_user(expected_username: str, current_username: str) -> None:
    if expected_username != current_username:
        raise HTTPException(403, "Token does not match requested user.")
