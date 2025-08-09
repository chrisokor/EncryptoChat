from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict


app = FastAPI()

# storage
user_database: Dict[str, str] = {} # username -> public key
messages: Dict[str, List[dict]] = {} # username -> list of messages

class RegisterRequest(BaseModel):
    username: str
    public_key: str

class MessageRequest(BaseModel):
    to: str
    frm: str
    ciphertext: str

@app.post("/register")
def register_user(request: RegisterRequest):
    if request.username in user_database:
        raise HTTPException(400, "Username already exists.")

    user_database[request.username] = request.public_key
    messages[request.username] = []
    return {"status": "registered"}


@app.post("/send")
def send_message(message_request: MessageRequest):
    if not message_request.to in user_database:
        raise HTTPException(404, "Message recipient not found.")

    messages[message_request.to].append({
        "from": message_request.frm, "ciphertext": message_request.ciphertext
        })
    return {"status": "sent"}


@app.get("/inbox/{username}")
def get_inbox(username: str):
    if username not in user_database:
        raise HTTPException(404, "User not found.")
    
    inbox = messages[username]
    messages[username] = []
    return {"inbox": inbox}


@app.get("/users/{username}")
def get_user(username: str):
    if username not in user_database:
        raise HTTPException(404, "User not found.")
    return {"username": username, "public_key": user_database[username]}
