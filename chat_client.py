from nacl.public import PrivateKey, Box, PublicKey
import requests
import base64
from utils.constants import API
from utils.base_64_utils import bytes_to_base64_str, base64_str_to_bytes
from nacl.utils import random as nacl_random
from typing import Dict


class ChatClient:

    def __init__(self, username: str, prekey_count: int = 5):
        self.username = username
        self.secret_key = PrivateKey.generate()
        self.public_key = self.secret_key.public_key
        self.shared_boxes = {}

        self.prekeys_to_privs: Dict[str, PrivateKey] = {}
        self.sessions: Dict[str, Box] = {}
        self._gen_prekeys(prekey_count)

    def _gen_prekeys(self, count: int):
        self.prekeys_upload = []
        for _ in range(count):
            secret_key = PrivateKey.generate()
            public_key = secret_key.public_key
            prekey_id = base64.urlsafe_b64encode(nacl_random(8)).decode()
            self.prekeys_to_privs[prekey_id] = secret_key
            self.prekeys_upload.append({
                "id": prekey_id,
                "key": bytes_to_base64_str(bytes(public_key))
            })


    # register a user - generate their public key
    def register(self):
        r = requests.post(f"{API}/register", json={
            "username": self.username,
            "public_key": bytes_to_base64_str(bytes(self.public_key))
        })
        if r.status_code == 400:
            print(f"[{self.username}] is already registered.")
            return
        r.raise_for_status()
        
        r = requests.post(f"{API}/users/{self.username}/prekeys", json={
            "prekeys": self.prekeys_upload
        })
        r.raise_for_status()
        print(f"[{self.username}] registered with [{len(self.prekeys_upload)}] prekeys")

    # retrieve a peer's public key and create a Box (runs D-H inside)
    def handshake_with(self, peer: str):
        r = requests.get(f"{API}/users/{peer}/keys")
        r.raise_for_status()
        response_data = r.json()

        # check if prekey is available
        if response_data["prekey"] is None:
            # fallback to main public key if no prekeys available
            peer_public_key = PublicKey(base64_str_to_bytes(response_data["public_key"]))
            self.sessions[peer] = {
                "box": Box(self.secret_key, peer_public_key),
                "prekey_id": None
            }
            print(f"[{self.username}] No prekeys available for [{peer}], using main key.")
        else:
            # use available prekey
            prekey_id = response_data["prekey"]["id"]
            peer_public_key = PublicKey(base64_str_to_bytes(response_data["prekey"]["key"]))  
            self.sessions[peer] = {
                "box": Box(self.secret_key, peer_public_key),
                "prekey_id": prekey_id
            }
            print(f"[{self.username}] Using prekey {prekey_id} for [{peer}].")                          
        print(f"[{self.username}] session ready with [{peer}].")

    # encrypt and send messages
    def send_message(self, to: str, plaintext: str):
        if to not in self.sessions:
            self.handshake_with(to)

        session = self.sessions[to]
        box = session["box"]
        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = box.encrypt(plaintext.encode(), nonce)

        request = requests.post(f"{API}/send", json={
            "to": to,
            "frm": self.username,
            "ciphertext": bytes_to_base64_str(ciphertext),
            "prekey_id": session["prekey_id"]
        })
        request.raise_for_status()
        print(f"[{self.username}] -> [{to}] sent.")


    # retrieve inbox and decrypt messages
    def receive_all(self):
        request = requests.get(f"{API}/inbox/{self.username}")
        request.raise_for_status()
        messages = request.json()["inbox"]

        for message in messages:
            frm = message["from"]
            prekey_id = message.get("prekey_id")

            # determine which key to use for encryption
            if prekey_id and prekey_id in self.prekeys_to_privs:
                # use the corresponding prekey private key
                prekey_secret = self.prekeys_to_privs[prekey_id]

                # get sender's public key
                r = requests.get(f"{API}/users/{frm}")
                r.raise_for_status()
                sender_public_key = PublicKey(base64_str_to_bytes(r.json()["public_key"]))

                box = Box(prekey_secret, sender_public_key)
                print(f"[{self.username}] Decrypting with prekey {prekey_id}")
            else:
                # use main key
                if frm in self.sessions:
                    box = self.sessions[frm]["box"]
                else:
                    # create box with main keys
                    r = requests.get(f"{API}/users/{frm}")
                    r.raise_for_status()
                    sender_public_key = PublicKey(base64_str_to_bytes(r.json()["public_key"]))
                    box = Box(self.secret_key, sender_public_key)
                print(f"[{self.username}] Decrypting with main key.")

            try:
                plaintext = box.decrypt(base64_str_to_bytes(message["ciphertext"])).decode()
                print(f"[{self.username}] <- [{frm}]: [{plaintext}]")
            except Exception as e:
                print(f"[{self.username}] Failed to decrypt message from [{frm}]: {e}")
               


