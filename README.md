# EncryptoChat

[![CI](https://github.com/chrisokor/EncryptoChat/actions/workflows/pipeline.yml/badge.svg)](https://github.com/chrisokor/EncryptoChat/actions/workflows/pipeline.yml)

EncryptoChat is a Dockerized secure messaging platform built with FastAPI, PostgreSQL, Redis, WebSockets, and PyNaCl.

The **Python CLI** is the true client-side encrypted path: private keys stay local, messages are encrypted with PyNaCl before reaching the server, and the server stores/transports ciphertext. The **browser UI** is a separate transport demo that exercises authentication, prekeys, WebSocket delivery, and message status using server-readable demo envelopes.

## What This Demonstrates

- Backend API design with FastAPI, Pydantic validation, PostgreSQL, SQLAlchemy, and Redis
- Applied cryptography with X25519 key exchange, PyNaCl authenticated encryption, and Ed25519 signed challenge authentication
- Real-time message delivery with WebSockets plus Redis-backed inbox fallback
- User-scoped authorization, public-key identity lookup, safety fingerprints, and prekey-based offline setup
- CI/CD with PostgreSQL and Redis integration tests, Docker build validation, coverage reporting, and GitHub Container Registry publishing

## Engineering Highlights

- **Encrypted CLI Messaging** - Python CLI messages use PyNaCl `Box` with Curve25519/X25519, XSalsa20, and Poly1305
- **Signed Authentication** - Ed25519 challenge-response login verifies client identity without sending private keys or passwords
- **Offline Prekey Setup** - Recipients upload public prekeys so senders can establish conversations while recipients are offline
- **Real-Time Delivery** - WebSocket delivery for online users with Redis inbox fallback for offline users
- **Persistent State** - PostgreSQL stores users, public identity keys, prekeys, encrypted CLI payloads, metadata, and message status
- **Delivery Status** - Messages move through queued, delivered, and read states
- **Containerized Runtime** - Docker Compose starts the API, PostgreSQL, and Redis together
- **Automated Verification** - 64 unit/integration tests with 90% coverage

## Architecture

```text
PyNaCl CLI (Alice)               Server (FastAPI)               PyNaCl CLI (Bob)
    |                                  |                                  |
    |-- Register public keys --------->|                                  |
    |<-------- OK ---------------------|                                  |
    |                                  |<------- Register public keys ----|
    |                                  |------------ OK ------------------>|
    |                                  |                                  |
    |-- Auth challenge/login --------->|                                  |
    |<-- Bearer token -----------------|                                  |
    |                                  |                                  |
    |-- Get Bob's prekey ------------->|                                  |
    |<-- Bob identity + prekey --------|                                  |
    |                                  |                                  |
    | (Encrypt locally with PyNaCl)    |                                  |
    |                                  |                                  |
    |-- Send ciphertext -------------->|-- Store metadata in Postgres --->|
    |                                  |-- Queue envelope in Redis ------>|
    |                                  |-- WebSocket live delivery ------>|
    |                                  |                                  |
    |                                  |<------- Fetch inbox -------------|
    |                                  |-- Pop queued envelope ---------->|
    |                                  |                                  |
    |                                  |        (Decrypt locally)         |
```

For CLI messages, encryption and decryption happen on the clients. The server handles identity lookup, signed authentication, prekey distribution, message transport, real-time delivery, persistence, and status tracking.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.13, FastAPI |
| Validation | Pydantic |
| Database | PostgreSQL 15, SQLAlchemy |
| Queue / Cache | Redis 7 |
| Real-Time Transport | WebSockets |
| Cryptography | PyNaCl / libsodium |
| Authentication | Ed25519 signed challenges, bearer tokens |
| Runtime | Docker, Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry |

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/chrisokor/EncryptoChat.git
cd EncryptoChat
```

### 2. Start the services

If you previously ran an older version of the project, reset the existing Docker volumes first. This deletes local demo data.

```bash
docker compose down -v
```

Start the application:

```bash
docker compose up --build
```

This starts:

- FastAPI on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

## Browser Demo

Open:

```text
http://localhost:8000
```

Use the browser demo to test:

- user registration and signed login flow
- contact lookup
- safety fingerprint display
- prekey count and refill flow
- WebSocket message delivery
- inbox fallback
- sender-visible message status

Important: browser messages are **base64-encoded plaintext demo envelopes**. They are server-readable and are not the end-to-end encrypted PyNaCl path. Use the CLI demo below to test true client-side encryption.

## Encrypted CLI Demo

With Docker running, open two terminals and run the CLI inside the running `api` container.

Terminal 1:

```bash
docker compose exec api python chat_script.py alice
```

Terminal 2:

```bash
docker compose exec api python chat_script.py bob
```

From Alice:

```text
alice> hi bob
alice> msg bob Hello, this is encrypted!
```

From Bob:

```text
bob> inbox
[bob] <- [alice]: [hello from alice]
[bob] <- [alice]: [Hello, this is encrypted!]
```

Useful CLI commands:

```text
inbox                 # retrieve pending messages
hi <peer>             # establish a conversation and send an initial message
msg <peer> <text>     # send another message
prekeys               # show available prekeys
refill 5              # upload more prekeys
quit                  # exit
```

## Security Model

### CLI Encryption Path

- Private encryption keys are generated and stored locally in `.keys/`
- Private keys are never sent to the server
- CLI message bodies are encrypted client-side with PyNaCl `Box`
- The server stores and forwards CLI ciphertext without access to plaintext
- Public prekeys allow senders to start conversations with offline recipients

### Authentication

EncryptoChat uses signed authentication challenges:

1. The client requests a one-time challenge from the server.
2. The client signs the challenge with its Ed25519 private signing key.
3. The server verifies the signature with the registered public signing key.
4. The server returns a bearer token for protected routes.

### Safety Fingerprints

User profiles expose a stable public identity fingerprint derived from registered public key material. The browser demo displays contact fingerprints so users can compare public identities out of band.

## Important Limitations

EncryptoChat is an educational secure messaging project, not a production replacement for Signal.

- The CLI uses prekey-based session setup, but it does **not** implement a double ratchet or full forward secrecy
- The browser demo is **not end-to-end encrypted** and sends server-readable demo envelopes
- Browser identity material is stored in `localStorage`, which is not production-grade key storage
- Authentication challenges, bearer tokens, and WebSocket connections are process-local and do not scale across multiple API instances
- Authenticated users can request another user's public prekeys; there is no per-user rate limit against prekey exhaustion
- Database schemas are created with SQLAlchemy `create_all()`; older Docker volumes should be reset with `docker compose down -v`
- WebSocket bearer tokens are passed in the query string for local demo simplicity

## API Documentation

Once the server is running:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Core Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/register` | Register a user and public identity keys |
| `GET` | `/auth/challenge/{username}` | Generate a one-time authentication challenge |
| `POST` | `/auth/login` | Verify a signed challenge and issue a bearer token |
| `POST` | `/send` | Send a CLI ciphertext or browser-demo envelope |
| `GET` | `/inbox/{username}` | Retrieve queued messages |
| `GET` | `/inbox/{username}/count` | Return pending message count |
| `POST` | `/messages/{message_id}/read` | Mark a delivered message as read |
| `GET` | `/messages/sent/{username}` | List sent-message status records |
| `GET` | `/users/{username}` | Retrieve public identity information and fingerprint |
| `GET` | `/users/{username}/keys` | Retrieve a public identity key and consume a prekey |
| `POST` | `/users/{username}/prekeys` | Upload one-time prekeys |
| `GET` | `/users/{username}/prekeys/count` | Return available prekey count |
| `WebSocket` | `/ws/{username}?token={token}` | Receive real-time message envelopes |
| `GET` | `/` | Open the browser transport demo |

## Testing

The test suite runs on the host and connects to PostgreSQL and Redis on `127.0.0.1`. Docker Compose can provide those services, but the Python test command should run from a local virtual environment.

Start the Docker services:

```bash
docker compose up --build
```

Create the test database once:

```bash
docker compose exec postgres createdb -U encryptochat encryptochat_test
```

Install test dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the test suite:

```bash
pytest -q
```

Expected result:

```text
64 passed
```

Run coverage:

```bash
pytest --cov=. --cov-report=term
```

Current coverage:

```text
90%
```

## CI/CD

GitHub Actions runs unit and integration tests with PostgreSQL and Redis service containers on pushes and pull requests.

The pipeline also:

- validates Docker image builds
- reports coverage
- publishes a commit-SHA image tag on pushes to `main`
- publishes a `latest` image tag to GitHub Container Registry
- scopes package-write permission to the main-branch publish job

## Local Development

### Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start PostgreSQL

```bash
brew services start postgresql@15
createdb encryptochat
```

### Start Redis

```bash
brew services start redis
```

### Configure environment

```bash
export DATABASE_URL="postgresql://localhost/encryptochat"
export REDIS_URL="redis://127.0.0.1:6379/0"
export API_URL="http://127.0.0.1:8000"
```

### Run the API

```bash
uvicorn server:app --reload
```

### Run CLI clients locally

With the local API running, open two terminals:

```bash
python chat_script.py alice
python chat_script.py bob
```

## Project Structure

```text
EncryptoChat/
├── server.py              # FastAPI application, routes, WebSocket endpoint
├── auth.py                # Challenge-response auth and bearer-token helpers
├── chat_client.py         # Encrypted CLI client implementation
├── chat_script.py         # CLI interface
├── database.py            # SQLAlchemy connection/session setup
├── models/
│   └── database_models.py # SQLAlchemy models
├── static/
│   ├── index.html         # Browser demo
│   ├── styles.css
│   └── app.js
├── utils/
│   ├── constants.py
│   ├── base_64_utils.py
│   ├── redis_helper.py
│   └── validation.py
├── test/                  # Unit and integration tests
├── docs/
│   └── LEARNING_GUIDE.md  # Architecture and interview guide
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Recruiter / Interview Notes

This project is strongest as a backend/security systems project. The most important talking points are:

- how the server can route encrypted CLI messages without holding private keys
- why Redis and WebSockets are both used for delivery
- how Ed25519 challenge-response authentication proves client identity
- how PostgreSQL and Redis divide durable state from fast delivery queues
- what the security limitations are and how the design would evolve toward production

For a deeper walkthrough, read [docs/LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md).

## Future Improvements

- Double-ratchet session key evolution
- Stronger forward-secrecy guarantees
- Automatic prekey replenishment and rotation
- Per-user prekey rate limiting
- Production-grade browser key storage
- End-to-end encrypted browser client
- Persistent/distributed authentication sessions
- Database migrations with Alembic
- HTTPS/TLS deployment
- Group messaging

## License

MIT License.

## Author

Built by Chris Okorochukwu as a hands-on exploration of encrypted messaging protocols, distributed backend systems, authentication, real-time delivery, and production-style testing.
