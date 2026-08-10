# EncryptoChat Learning Guide

## Elevator Pitch

EncryptoChat is a Dockerized end-to-end encrypted chat demo built with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl. It demonstrates encrypted message envelopes, signed challenge authentication, one-time prekey exchange, real-time delivery, integration testing, and CI/CD container publishing.

## Architecture

The FastAPI server stores public identity material, one-time prekeys, encrypted message metadata, and message status. Redis acts as a fast inbox queue. Clients hold private keys locally and send only public keys, signatures, and ciphertext to the server.

## Message Lifecycle

1. Bob registers and uploads prekeys.
2. Alice retrieves Bob's public identity and one unused prekey.
3. Alice encrypts plaintext locally using PyNaCl.
4. Alice sends ciphertext to the server.
5. The server stores ciphertext and queues an envelope in Redis.
6. Bob receives the envelope through WebSocket or inbox polling.
7. Bob decrypts locally with the matching private prekey.
8. Status moves from queued to delivered to read.

## Security Model

The server cannot decrypt message bodies because private encryption keys stay on the client. Authentication uses a separate signing key so the server can verify user ownership without receiving a password or private key.

## Limitations

This is an educational secure messaging project. It does not implement the full Signal protocol, does not include a double ratchet, and does not hide metadata such as sender, recipient, or timestamps.

The browser demo is a REST/WebSocket demonstration shell, not a PyNaCl `Box`-compatible browser encryption client. It sends valid base64 demo ciphertext envelopes to show message flow, and those envelopes cannot be decrypted by the CLI client. Browser private keys are stored in `localStorage` for the local demo, which is not suitable for production key storage.

Authentication challenges and bearer tokens are stored in memory and are process-local. They are lost when the API restarts and are not shared across API instances.

## Resume Bullets

- Built a Dockerized encrypted messaging platform with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl.
- Implemented signed challenge authentication using Ed25519 and protected user-scoped API routes with bearer tokens.
- Designed one-time prekey exchange for forward-secrecy-style message setup and tracked encrypted message delivery state.
- Built GitHub Actions CI/CD with PostgreSQL and Redis integration tests, coverage reporting, Docker build validation, and GHCR image publishing.

## Interview Talking Points

Explain why private keys stay on the client, why the server stores ciphertext only, why Redis is used for fast inbox delivery, and why WebSockets improve real-time behavior while polling remains a fallback.

## Demo Script

Run `docker compose up --build`, open `http://localhost:8000`, register Alice and Bob, exchange messages, show the database stores ciphertext, show prekey count changes, and point to GitHub Actions for CI/CD.
