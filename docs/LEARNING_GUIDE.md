# EncryptoChat Learning Guide

## Browser Demo Limitations

The browser page at `/` is an API and WebSocket demonstration shell. It uses the Web Crypto API to generate X25519 and Ed25519 account and prekey material, then stores the browser private keys in `localStorage`. This is convenient for a local demo but is not secure key storage and must not be used for production secrets.

The browser does not implement PyNaCl `Box` encryption. PyNaCl-compatible encryption would require the XSalsa20-Poly1305 construction used by `nacl.public.Box`, which is not supplied by Web Crypto and is intentionally not added as a browser dependency. The shell sends valid base64 demo ciphertext envelopes so the REST and WebSocket message flow can be observed; these envelopes cannot be decrypted by the CLI client.

This project demonstrates educational X3DH-style prekey messaging. It is not a complete Signal Protocol implementation.
