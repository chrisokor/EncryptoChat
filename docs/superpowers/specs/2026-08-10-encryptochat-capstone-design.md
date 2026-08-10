# EncryptoChat Capstone Design

## Goal

Turn EncryptoChat from a functional encrypted-chat MVP into a resume-ready capstone project that is easy to run, demo, test, and explain. The finished project should show backend engineering, applied cryptography, real-time systems, Dockerized infrastructure, and clear technical communication.

## Chosen Approach

Use an integrated FastAPI application. The backend will serve the REST API, WebSocket endpoint, and a small static browser demo. This keeps the project easy to run with `docker compose up --build` while still showing full-stack behavior.

This approach avoids a separate frontend build system. The browser demo will use plain HTML, CSS, and JavaScript served from FastAPI static files.

## Scope

The capstone version will include:

- Signed challenge login and bearer-token authorization.
- Stronger request validation.
- Consistent prekey API naming used by both client and server.
- Message status tracking: `queued`, `delivered`, and `read`.
- Redis-backed inbox delivery with WebSocket live delivery.
- Polling fallback for inbox retrieval.
- Prekey count endpoint and low-prekey warnings.
- Contact safety fingerprints.
- A browser demo with register/login, contacts, chat, message status, prekey health, and safety fingerprint views.
- A learning document that explains how the project works and how to discuss it on a resume or in interviews.

The project will remain an educational secure-messaging demo, not a production Signal replacement.

## Security Model

Messages remain end-to-end encrypted with PyNaCl `Box`, using X25519 key agreement and authenticated encryption.

Authentication will use a separate Ed25519 signing key. During registration, the client stores:

- X25519 private key for message encryption.
- X25519 public key stored on the server.
- Ed25519 signing private key for authentication.
- Ed25519 signing public key stored on the server.

Login flow:

1. Client requests a challenge for a username.
2. Server returns a short-lived random challenge.
3. Client signs the challenge with its Ed25519 signing private key.
4. Server verifies the signature using the stored signing public key.
5. Server returns a bearer token.

Protected routes will verify that the bearer token belongs to the user being acted on. For example, Alice cannot send a request with `frm = "bob"`, read Bob's inbox, or upload Bob's prekeys.

Limitations documented in the learning guide:

- Browser localStorage is acceptable for a demo but not ideal for production private-key storage.
- The protocol is X3DH-style because it uses one-time prekeys, but it is not a complete Signal protocol implementation.
- There is no double-ratchet session evolution.
- Server-side message metadata is not hidden.

## API Design

New or changed endpoints:

- `POST /register`
  Registers username, encryption public key, and signing public key.

- `GET /auth/challenge/{username}`
  Returns a short-lived login challenge.

- `POST /auth/login`
  Verifies the signed challenge and returns an access token.

- `GET /users/{username}`
  Returns public profile material: username, encryption public key, signing public key, and safety fingerprint.

- `GET /users/{username}/prekeys`
  Returns and consumes the next unused prekey.

- `POST /users/{username}/prekeys`
  Protected. Uploads prekeys for the authenticated user.

- `GET /users/{username}/prekeys/count`
  Returns unused prekey count.

- `POST /send`
  Protected. Stores encrypted message, pushes it to Redis, and broadcasts to the recipient WebSocket if connected.

- `GET /inbox/{username}`
  Protected. Retrieves queued messages and marks them delivered.

- `GET /inbox/{username}/count`
  Protected. Returns pending Redis inbox count.

- `POST /messages/{message_id}/read`
  Protected. Marks a received message as read.

- `GET /messages/sent/{username}`
  Protected. Returns message status records for messages sent by the authenticated user.

- `WebSocket /ws/{username}?token=...`
  Streams encrypted message envelopes to authenticated online users.

For backward compatibility during implementation, `/users/{username}/keys` may be retained as an alias for prekey retrieval if tests or clients still use it.

## Data Model

`users` table changes:

- `username`
- `public_key`
- `signing_public_key`
- `created_at`

`messages` table changes:

- `id`
- `to_user`
- `from_user`
- `ciphertext`
- `prekey_id`
- `status`
- `created_at`
- `delivered_at`
- `read_at`

`prekeys` table remains mostly unchanged:

- `id`
- `username`
- `key`
- `used`
- `used_at`
- `created_at`

New token/challenge storage can be in-memory for the capstone MVP. The README and learning document will explain that production tokens and challenges should be persisted or backed by Redis.

## Client Design

The Python CLI will be repaired and updated:

- Correctly default to `alice` when no argument is passed.
- Use the server's real prekey endpoint.
- Generate and save Ed25519 signing keys.
- Register with both encryption and signing public keys.
- Authenticate before protected operations.
- Warn when prekeys are low.
- Display contact safety fingerprints.

The browser demo will implement the same basic flow:

- Register or load a local identity.
- Login through challenge signing.
- Add/select a contact.
- Show contact fingerprint.
- Send encrypted messages.
- Receive live messages over WebSocket.
- Fetch inbox as fallback.
- Show prekey health and refill action.

## Frontend Design

The first screen will be the usable chat interface, not a landing page. It should feel like a practical developer demo:

- Left column: current identity, auth state, contacts, prekey health.
- Main area: conversation messages and composer.
- Right or collapsible panel: safety fingerprint and message status.

The UI should be restrained, readable, and responsive. It should not use oversized hero sections or decorative marketing layout.

## Testing Strategy

Development will use test-driven changes for backend behavior. Key tests:

- Registration requires valid username, encryption public key, and signing public key.
- Duplicate users are rejected.
- Login succeeds with a valid challenge signature.
- Login rejects invalid signatures and expired/used challenges.
- Protected endpoints reject missing or wrong-user tokens.
- Sending creates a queued message and Redis inbox entry.
- Inbox retrieval marks messages delivered.
- Read endpoint marks messages read.
- Sent-message status endpoint returns status records.
- Prekey count endpoint reports unused prekeys.
- Prekey retrieval is FIFO and consumes one prekey.
- `/users/{username}/keys` alias behaves consistently if retained.

Frontend behavior will be manually verified through the browser demo after backend tests pass.

## Documentation Deliverables

Update `README.md` with:

- One-command Docker start.
- CLI demo flow.
- Browser demo flow.
- API summary.
- Security model and limitations.
- Test command.

Create `docs/LEARNING_GUIDE.md` with:

- Project elevator pitch.
- Architecture walkthrough.
- Encryption and authentication explanation.
- Message lifecycle from send to read.
- WebSocket and Redis delivery explanation.
- Database schema explanation.
- Tradeoffs and limitations.
- Resume bullets.
- Interview questions and strong answers.
- Demo script.

## Implementation Order

1. Fix existing CLI/API mismatch and add compatibility tests.
2. Add settings and validation.
3. Add signing keys, challenge login, and route authorization.
4. Add message status fields and status endpoints.
5. Add prekey health endpoint and client warnings.
6. Add WebSocket delivery.
7. Add static browser demo.
8. Update README and create learning guide.
9. Run full test suite and manual demo verification.

## Success Criteria

- `pytest -q` passes.
- `docker compose up --build` starts API, Postgres, and Redis.
- CLI can register two users and exchange encrypted messages.
- Browser demo can register/login, send, receive, and show prekey/fingerprint/status information.
- Unauthorized users cannot send as or read another user.
- Documentation clearly explains what was built, how it works, and what its security limits are.
