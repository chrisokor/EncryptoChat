from nacl.public import PrivateKey, Box, PublicKey
import requests
from utils.constants import API
from utils.base_64_utils import bytes_to_base64_str, base64_str_to_bytes
from nacl.utils import random as nacl_random


class ChatClient:

    def __init__(self, username: str):
        self.username = username
        self.secret_key = PrivateKey.generate()
        self.public_key = self.secret_key.public_key
        self.shared_boxes = {}

    # register a user - generate their public key
    def register(self):
        r = requests.post(f"{API}/register", json={
            "username": self.username,
            "public_key": bytes_to_base64_str(bytes(self.public_key))
        })
        r.raise_for_status()
        print(f"[{self.username}] registered")

    # retrieve a peer's public key and create a Box (runs D-H inside)
    def handshake_with(self, peer: str):
        r = requests.get(f"{API}/users/{peer}")
        r.raise_for_status()
        peer_public_key = PublicKey(base64_str_to_bytes(r.json()["public_key"]))
        self.shared_boxes[peer] = Box(self.secret_key, peer_public_key)
        print(f"[{self.username}] session ready with [{peer}].")

    # encrypt and send messages
    def send_message(self, to: str, plaintext: str):
        box = self.shared_boxes[to]
        nonce = nacl_random(Box.NONCE_SIZE)
        ciphertext = box.encrypt(plaintext.encode(), nonce)
        request = requests.post(f"{API}/send", json={
            "to": to,
            "frm": self.username,
            "ciphertext": bytes_to_base64_str(ciphertext)
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
            box = self.shared_boxes.get(frm)

            if not box:
                self.handshake_with(frm)
                box = self.shared_boxes[frm]
            plaintext = box.decrypt(base64_str_to_bytes(message["ciphertext"])).decode()
            print(f"[{self.username}] <- [{frm}]: [{plaintext}]")


