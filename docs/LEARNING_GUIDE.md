# EncryptoChat Learning Guide

## Elevator Pitch

EncryptoChat is a Dockerized messaging capstone built with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl. Its Python CLI path demonstrates end-to-end encrypted message envelopes, while its dependency-free browser path demonstrates authenticated REST/WebSocket delivery with server-readable demo bodies. The project also covers signed challenge authentication, one-time prekey allocation, message status tracking, integration testing, and CI/CD container publishing.

## Architecture

The FastAPI server stores public identity material, one-time prekeys, message envelopes, metadata, and message status. Redis acts as a fast inbox queue. PyNaCl CLI clients hold private keys locally and send ciphertext to the server. Browser clients also hold identity material locally, but their message bodies are base64-encoded plaintext and remain readable by the server.

## Python CLI Message Lifecycle

1. Bob registers and uploads prekeys.
2. Alice retrieves Bob's public identity and one unused prekey.
3. Alice encrypts plaintext locally using PyNaCl.
4. Alice sends ciphertext to the server.
5. The server stores ciphertext and queues an envelope in Redis.
6. Bob receives the envelope through WebSocket or inbox polling.
7. Bob decrypts locally with the matching private prekey.
8. Status moves from queued to delivered to read.

## Security Model

For the Python CLI path, the server cannot decrypt message bodies because PyNaCl encryption private keys stay on the client. Authentication uses a separate signing key so the server can verify user ownership without receiving a password or private key. These end-to-end-encryption and server-opacity properties do not apply to browser demo message bodies.

## Limitations

This is an educational secure messaging project. It does not implement the full Signal protocol, does not include a double ratchet, and does not hide metadata such as sender, recipient, or timestamps. The CLI retains prekey private keys and may reuse a session prekey, so the current protocol does not claim forward secrecy.

The browser demo is a REST/WebSocket demonstration shell, not a PyNaCl `Box`-compatible encryption client. It sends base64-encoded plaintext demo envelopes to show message flow. Base64 is reversible encoding: the server and database operators can read browser message bodies, so the browser path is not end-to-end encrypted or zero-knowledge. Its envelopes are also incompatible with the CLI client. Browser identity keys are stored in `localStorage` for the local demo, which is not suitable for production key storage.

Authentication challenges and bearer tokens are stored in memory and are process-local. They are lost when the API restarts and are not shared across API instances.

Prekey consumption requires a valid bearer token, including when requesting another user's public conversation setup material. The demo does not implement per-user rate limiting, so an authenticated account can still exhaust a recipient's available prekeys.

The project uses SQLAlchemy `create_all()` without Alembic migrations. Existing Docker volumes created by a pre-capstone version do not receive the new columns automatically. Before running this version against those volumes, use `docker compose down -v`; this permanently deletes the existing demo database and Redis data.

## Resume Bullets

- Built a Dockerized messaging platform with a PyNaCl end-to-end encrypted Python CLI path and an authenticated REST/WebSocket browser demo.
- Implemented signed challenge authentication using Ed25519 and protected user-scoped API routes with bearer tokens.
- Designed transactional one-time prekey allocation for CLI conversation setup and tracked queued, delivered, and read message state.
- Built GitHub Actions CI/CD with PostgreSQL and Redis integration tests, coverage reporting, Docker build validation, and GHCR image publishing.

## Interview Talking Points

Explain why CLI private keys stay on the client, why the server stores CLI ciphertext but can read browser demo bodies, why Redis is used for fast inbox delivery, and why WebSockets improve real-time behavior while polling remains a fallback.

## Demo Script

For a pre-capstone Docker volume, run `docker compose down -v` first. Then run `docker compose up --build`, use the Python CLI to demonstrate ciphertext storage, open `http://localhost:8000` to demonstrate the explicitly plaintext browser transport flow, show prekey count and status changes, and point to GitHub Actions for CI/CD.
