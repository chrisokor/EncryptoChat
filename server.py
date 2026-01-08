from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from uuid import uuid4
from typing import List, Dict
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime, UTC

from database import init_database, get_database
from models.database_models import User, Message, Prekey
from utils.redis_helper import push_message_to_inbox, pop_all_inbox_messages, get_inbox_count

# initialize database upon server start
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_database()
    yield
    # Shutdown (if needed)

app = FastAPI(lifespan=lifespan)

class RegisterRequest(BaseModel):
    username: str
    public_key: str

class MessageRequest(BaseModel):
    to: str
    frm: str
    ciphertext: str
    prekey_id: str

class PrekeyRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    key: str

class PrekeyUpload(BaseModel):
    prekeys: List[PrekeyRequest]


# storage
user_database: Dict[str, str] = {} # username -> public key
messages: Dict[str, List[dict]] = {} # username -> list of messages
prekeys_store: Dict[str, List[Prekey]] = {} # username -> queued public prekeys

@app.post("/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_database)):
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(400, "Username already exists.")
    
    if not request.username:
        raise HTTPException(422, "Missing username.")

    if not request.public_key:
        raise HTTPException(422, "Missing public key.")

    user = User(username=request.username, public_key=request.public_key)
    db.add(user)
    db.commit()
    return {"status": "registered"}


@app.post("/send")
def send_message(message_request: MessageRequest, db: Session = Depends(get_database)):
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

    # push message to Redis inbox queue for fast retrieval for recipient
    push_message_to_inbox(message_request.to, {
        "from": message_request.frm,
        "ciphertext": message_request.ciphertext,
        "prekey_id": message_request.prekey_id
    })
    
    return {"status": "sent"}


@app.get("/inbox/{username}")
def get_inbox(username: str, db: Session = Depends(get_database)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    
    # get messages from Redis queue (fast)
    inbox = pop_all_inbox_messages(username)

    return {"inbox": inbox}


@app.get("/inbox/{username}/count")
def get_inbox_count_endpoint(username: str, db: Session = Depends(get_database)):
    """Check how many pending messages without retrieving them"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    
    count = get_inbox_count(username)
    return {"username": username, "count": count}


@app.get("/users/{username}")
def get_user(username: str, db: Session = Depends(get_database)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    return {"username": user.username, "public_key": user.public_key}


@app.post("/users/{username}/prekeys")
def upload_prekeys(username: str, body: PrekeyUpload, db: Session = Depends(get_database)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    
    if not body.prekeys:
        raise HTTPException(422, "Prekeys list cannot be empty.")

    for pk in body.prekeys:
        prekey = Prekey(id=pk.id, username=username, key=pk.key)
        db.add(prekey)
    db.commit()

    count = db.query(Prekey).filter(Prekey.username == username, Prekey.used == False).count()
    return {"ok": True, "count": count}


@app.get("/users/{username}/prekeys")
def get_prekey(username: str, db: Session = Depends(get_database)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found.")
    
    prekey = db.query(Prekey).filter(Prekey.username == username, Prekey.used == False).first()

    if prekey:
        prekey.used = True
        prekey.used_at = datetime.now(UTC)
        db.commit()
        prekey_data = {"id": prekey.id, "key": prekey.key}
    else:
        prekey_data = None

    return {"username": user.username, "public_key": user.public_key, "prekey": prekey_data}
