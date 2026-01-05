import pytest
from nacl.public import PrivateKey, PublicKey, Box
from utils.base_64_utils import base64_str_to_bytes, bytes_to_base64_str


class TestCrypto:
    """Test cryptographic operations using PyNaCl"""

    def test_key_generation(self):
        """Test that key generation produces valid keys"""
        secret_key = PrivateKey.generate()
        public_key = secret_key.public_key

        assert len(bytes(secret_key)) == 32
        assert len(bytes(public_key)) == 32

    def test_base64_encoding_decoding(self):
        """Test base64 utilites work correctly"""
        secret_key = PrivateKey.generate()
        key_bytes = bytes(secret_key)

        encoded = bytes_to_base64_str(key_bytes)
        decoded = base64_str_to_bytes(encoded)

        assert key_bytes == decoded
        assert isinstance(encoded, str)

    def test_encryption_decryption_with_correct_keys_returns_success(self):
        """Test end-to-end encryption and decryption"""
        # generate keys for Alice and Bob
        alice_secret = PrivateKey.generate()
        alice_public = alice_secret.public_key

        bob_secret = PrivateKey.generate()
        bob_public = bob_secret.public_key

        # Alice encrypts message to send to Bob
        alice_box = Box(alice_secret, bob_public)
        message_plaintext = b"Hello Bob, this is encrypted!"
        ciphertext = alice_box.encrypt(message_plaintext)

        # Bob decrypts message
        bob_box = Box(bob_secret, alice_public)
        decrypted = bob_box.decrypt(ciphertext)

        assert decrypted == message_plaintext

    def test_encryption_with_different_keys_raises_exception(self):
        """Test that decryption with wrong key fails"""
        # arrange keys
        alice_secret = PrivateKey.generate()
        alice_public = alice_secret.public_key

        bob_secret = PrivateKey.generate()
        bob_public = bob_secret.public_key

        chris_secret = PrivateKey.generate()
        chris_public = chris_secret.public_key

        # act with message encryption to bob and chris attempting decrypt
        message_plaintext = b"Hello Bob!"
        alice_box = Box(alice_secret, bob_public)
        ciphertext = alice_box.encrypt(message_plaintext)

        chris_box = Box(chris_secret, alice_box)

        # assert Exception is raised
        with pytest.raises(Exception):
            chris_box.decrypt(ciphertext)

    
    def test_prekey_based_encryption(self):
        """Test prekey-based key exchange"""
        # arrange keys
        bob_prekey_secret = PrivateKey.generate()
        bob_prekey_public = bob_prekey_secret.public_key
        bob_identity_public = PrivateKey.generate().public_key

        alice_secret = PrivateKey.generate()

        # act using prekeys
        alice_box = Box(alice_secret, bob_prekey_public)
        ciphertext = alice_box.encrypt(b"Hello with prekey")

        bob_box = Box(bob_prekey_secret, alice_secret.public_key)
        plaintext = bob_box.decrypt(ciphertext)

        assert plaintext == b"Hello with prekey"
