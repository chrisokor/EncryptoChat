from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4
from typing import List, Dict
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime, UTC

from database import init_database, get_database
from models.database_models import User, Message, Prekey
from auth import (
    create_access_token,
    create_challenge,
    get_current_username,
    require_same_user,
    verify_access_token,
    verify_challenge_signature,
)
from utils.redis_helper import push_message_to_inbox, pop_all_inbox_messages, get_inbox_count
from utils.validation import normalize_username, validate_base64_key, validate_ciphertext, validate_prekey_id

# initialize database upon server start
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_database()
    yield
    # Shutdown (if needed)

app = FastAPI(lifespan=lifespan)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(username, []).append(websocket)

    def disconnect(self, username: str, websocket: WebSocket):
        connections = self.active_connections.get(username, [])
        if websocket in connections:
            connections.remove(websocket)

    async def send_to_user(self, username: str, payload: dict):
        for websocket in list(self.active_connections.get(username, [])):
            await websocket.send_json(payload)


manager = ConnectionManager()

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    public_key: str
    signing_public_key: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        return normalize_username(value)

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, value):
        return validate_base64_key(value, 32)

    @field_validator("signing_public_key")
    @classmethod
    def validate_signing_public_key(cls, value):
        return validate_base64_key(value, 32)


class LoginRequest(BaseModel):
    username: str
    challenge: str
    signature: str

class MessageRequest(BaseModel):
    to: str
    frm: str
    ciphertext: str
    prekey_id: str

    @field_validator("to", "frm")
    @classmethod
    def validate_username(cls, value):
        return normalize_username(value)

    @field_validator("ciphertext")
    @classmethod
    def validate_message_ciphertext(cls, value):
        return validate_ciphertext(value)

    @field_validator("prekey_id")
    @classmethod
    def validate_message_prekey_id(cls, value):
        return validate_prekey_id(value)

class PrekeyRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    key: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value):
        return validate_prekey_id(value)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value):
        return validate_base64_key(value, 32)

class PrekeyUpload(BaseModel):
    prekeys: List[PrekeyRequest]


# storage
user_database: Dict[str, str] = {} # username -> public key
messages: Dict[str, List[dict]] = {} # username -> list of messages
prekeys_store: Dict[str, List[Prekey]] = {} # username -> queued public prekeys


def _normalize_path_username(username: str) -> str:
    try:
        return normalize_username(username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_database)):
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(400, "Username already exists.")
    
    if not request.username:
        raise HTTPException(422, "Missing username.")

    if not request.public_key:
        raise HTTPException(422, "Missing public key.")

    user = User(
        username=request.username,
        public_key=request.public_key,
        signing_public_key=request.signing_public_key,
    )
    db.add(user)
    db.commit()
    return {"status": "registered"}


@app.get("/auth/challenge/{username}")
def get_auth_challenge(username: str, db: Session = Depends(get_database)):
    username = _normalize_path_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    return {"username": username, "challenge": create_challenge(username)}


@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_database)):
    username = _normalize_path_username(request.username)
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.signing_public_key:
        raise HTTPException(404, "User not found.")
    verify_challenge_signature(username, request.challenge, request.signature, user.signing_public_key)
    return {"access_token": create_access_token(username), "token_type": "bearer"}


@app.post("/send")
async def send_message(
    message_request: MessageRequest,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    require_same_user(message_request.frm, current_username)
    recipient = db.query(User).filter(User.username == message_request.to).first()
    if not recipient:
        raise HTTPException(404, "Message recipient not found.")
    
    # store message in PostgreSQL for history
    message = Message(
        to_user=message_request.to,
        from_user=message_request.frm,
        ciphertext=message_request.ciphertext,
        prekey_id=message_request.prekey_id
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # push message to Redis inbox queue for fast retrieval for recipient
    payload = {
        "id": message.id,
        "from": message_request.frm,
        "ciphertext": message_request.ciphertext,
        "prekey_id": message_request.prekey_id,
        "status": message.status,
    }
    push_message_to_inbox(message_request.to, payload)
    await manager.send_to_user(message_request.to, payload)
    
    return {"status": "sent", "message_id": message.id}


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str, token: str):
    username = normalize_username(username)
    current_username = verify_access_token(token)
    require_same_user(username, current_username)
    await manager.connect(username, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(username, websocket)


@app.get("/inbox/{username}")
def get_inbox(
    username: str,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    username = _normalize_path_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    require_same_user(username, current_username)
    
    # get messages from Redis queue (fast)
    inbox = pop_all_inbox_messages(username)
    message_ids = [item["id"] for item in inbox if "id" in item]
    if message_ids:
        now = datetime.now(UTC)
        db.query(Message).filter(Message.id.in_(message_ids), Message.to_user == username).update(
            {"status": "delivered", "delivered_at": now},
            synchronize_session=False,
        )
        db.commit()

    return {"inbox": inbox}


@app.get("/inbox/{username}/count")
def get_inbox_count_endpoint(
    username: str,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    """Check how many pending messages without retrieving them"""
    username = _normalize_path_username(username)
    require_same_user(username, current_username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    
    count = get_inbox_count(username)
    return {"username": username, "count": count}


@app.post("/messages/{message_id}/read")
def mark_message_read(
    message_id: int,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(404, "Message not found.")
    require_same_user(message.to_user, current_username)
    message.status = "read"
    message.read_at = datetime.now(UTC)
    if not message.delivered_at:
        message.delivered_at = message.read_at
    db.commit()
    return {"id": message.id, "status": message.status}


@app.get("/messages/sent/{username}")
def get_sent_messages(
    username: str,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    username = _normalize_path_username(username)
    require_same_user(username, current_username)
    rows = db.query(Message).filter(Message.from_user == username).order_by(Message.created_at.desc()).all()
    return {"messages": [{
        "id": row.id,
        "to": row.to_user,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]}


@app.get("/users/{username}")
def get_user(username: str, db: Session = Depends(get_database)):
    username = _normalize_path_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    return {"username": user.username, "public_key": user.public_key}


@app.post("/users/{username}/prekeys")
def upload_prekeys(
    username: str,
    body: PrekeyUpload,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    username = _normalize_path_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    require_same_user(username, current_username)
    
    if not body.prekeys:
        raise HTTPException(422, "Prekeys list cannot be empty.")

    for pk in body.prekeys:
        prekey = Prekey(id=pk.id, username=username, key=pk.key)
        db.add(prekey)
    db.commit()

    count = db.query(Prekey).filter(Prekey.username == username, Prekey.used == False).count()
    return {"ok": True, "count": count}


@app.get("/users/{username}/prekeys/count")
def get_prekey_count(
    username: str,
    db: Session = Depends(get_database),
    current_username: str = Depends(get_current_username),
):
    username = _normalize_path_username(username)
    require_same_user(username, current_username)
    count = db.query(Prekey).filter(Prekey.username == username, Prekey.used == False).count()
    return {"username": username, "count": count, "low": count < 3}

def _consume_prekey_for_user(username: str, db: Session):
    username = _normalize_path_username(username)
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")

    prekey = (
        db.query(Prekey)
        .filter(Prekey.username == username, Prekey.used == False)
        .order_by(Prekey.created_at)
        .first()
    )
    if not prekey:
        raise HTTPException(410, "No prekeys available.")

    prekey.used = True
    prekey.used_at = datetime.now(UTC)
    db.commit()
    return {
        "username": user.username,
        "public_key": user.public_key,
        "prekey": {"id": prekey.id, "key": prekey.key},
    }


@app.get("/users/{username}/prekeys")
def get_prekey(username: str, db: Session = Depends(get_database)):
    return _consume_prekey_for_user(username, db)


@app.get("/users/{username}/keys")
def get_user_keys(username: str, db: Session = Depends(get_database)):
    return _consume_prekey_for_user(username, db)
