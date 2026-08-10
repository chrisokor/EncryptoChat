# EncryptoChat

A messaging capstone built with FastAPI, PostgreSQL, Redis, WebSockets, and NaCl cryptography. The Python CLI provides the end-to-end encrypted PyNaCl client path; the browser is a separate, server-readable transport demo.

## Features

- 🔐 **CLI End-to-End Encryption**: Python CLI messages use NaCl Box (Curve25519 + XSalsa20 + Poly1305)
- 🔑 **Prekey Exchange**: One-time prekeys establish Python CLI conversations
- 🗄️ **PostgreSQL**: Durable storage for users, prekeys, and message audit logs
- ⚡ **Redis**: Fast message queues for real-time inbox delivery
- 🐳 **Docker**: One-command deployment with docker-compose
- 🔒 **CLI Server Opacity**: The server receives ciphertext from PyNaCl CLI clients and does not receive their private keys

## What This Demonstrates

- FastAPI API design with PostgreSQL and Redis.
- End-to-end encrypted Python CLI message envelopes using PyNaCl.
- A dependency-free browser transport demo using explicitly server-readable plaintext envelopes.
- Signed challenge authentication with Ed25519.
- Real-time delivery over WebSockets.
- CI/CD with integration tests and Docker image publishing.

## Architecture

```
PyNaCl CLI (Alice)               Server (FastAPI)               PyNaCl CLI (Bob)
    |                                  |                                  |
    |-- Register (public key) -------->|                                  |
    |<-------- OK ---------------------|                                  |
    |                                  |<------- Register (public key) ---|
    |                                  |------------ OK ------------------>|
    |                                  |                                  |
    |-- Get Bob's prekey ------------->|                                  |
    |<-- Bob's public key + prekey ----|                                  |
    |                                  |                                  |
    | (Encrypt with Bob's prekey)      |                                  |
    |                                  |                                  |
    |-- Send encrypted message ------->|-- Push to Redis queue ---------->|
    |                                  |   (also log to PostgreSQL)       |
    |                                  |                                  |
    |                                  |<------- Get inbox ---------------|
    |                                  |-- Pop from Redis queue --------->|
    |                                  |                                  |
    |                                  |        (Decrypt with prekey      |
    |                                  |         private key)             |
```

## Tech Stack

- **Backend**: FastAPI, Python 3.13
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7
- **Crypto**: PyNaCl (libsodium)
- **Deployment**: Docker, docker-compose

## Prerequisites

- Python 3.13+
- Docker Desktop (for containerized deployment)
- OR: PostgreSQL 15 + Redis 7 (for local development)

## Quick Start (Docker)

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd EncryptoChat
```

### 2. Start all services

This version adds database columns through SQLAlchemy `create_all()` and does not include Alembic migrations. If Docker volumes were created by a pre-capstone version, reset them before startup. This permanently deletes the existing demo database and Redis data:

```bash
docker compose down -v
```

Then start the current version:

```bash
docker compose up --build
```

This will start:
- **API server** on `http://localhost:8000`
- **PostgreSQL** on `localhost:5432`
- **Redis** on `localhost:6379`

### 3. Run clients in separate terminals

**Terminal 1 (Alice):**
```bash
python chat_script.py alice
```

**Terminal 2 (Bob):**
```bash
python chat_script.py bob
```

### 4. Send messages

In Alice's terminal:
```
alice> hi bob
alice> msg bob Hello, this is encrypted!
```

In Bob's terminal:
```
bob> inbox
[bob] <- [alice]: [hello from alice]
[bob] <- [alice]: [Hello, this is encrypted!]
```

### 5. Stop services
```bash
docker compose down
```

To completely reset (delete data):
```bash
docker compose down -v
```

## Local Development (Without Docker)

### 1. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL
```bash
brew services start postgresql@15
createdb encryptochat
```

### 3. Start Redis
```bash
brew services start redis
```

### 4. Set environment variables
```bash
export DATABASE_URL="postgresql://localhost/encryptochat"
export REDIS_URL="redis://127.0.0.1:6379/0"
```

### 5. Run the server
```bash
uvicorn server:app --reload
```

### 6. Run clients (in separate terminals)
```bash
python chat_script.py alice
python chat_script.py bob
```

## API Documentation

Once the server is running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register a new user with public key |
| GET | `/auth/challenge/{username}` | Issue a one-time signing challenge |
| POST | `/auth/login` | Exchange a signed challenge for a bearer token |
| POST | `/send` | Send a message envelope (CLI ciphertext or browser demo plaintext) |
| GET | `/inbox/{username}` | Retrieve and clear inbox |
| GET | `/inbox/{username}/count` | Get pending message count |
| POST | `/messages/{message_id}/read` | Mark a delivered message as read |
| GET | `/messages/sent/{username}` | List messages sent by a user |
| GET | `/users/{username}` | Get public identity keys and safety fingerprint |
| GET | `/users/{username}/keys` | Authenticated consumption of a user's public key + prekey |
| POST | `/users/{username}/prekeys` | Upload prekeys |
| GET | `/users/{username}/prekeys/count` | Get available one-time prekey count |
| WebSocket | `/ws/{username}?token={token}` | Receive real-time message envelopes |
| GET | `/` | Open the browser demo shell |

## Client Commands

```bash
# Check inbox
inbox

# Start conversation (handshake + send)
hi <peer>

# Send message
msg <peer> <text>

# Exit
quit
```

## Project Structure

```
EncryptoChat/
├── server.py              # FastAPI application
├── chat_client.py         # Client implementation
├── chat_script.py         # CLI interface
├── database.py            # SQLAlchemy connection
├── redis_client.py        # Redis helper functions
├── models/
│   └── database_models.py # SQLAlchemy models
├── utils/
│   ├── constants.py       # Configuration
│   └── base_64_utils.py   # Encoding helpers
├── docker-compose.yml     # Docker orchestration
├── Dockerfile             # API container
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Security Features

### Cryptographic Primitives
- **Key Exchange**: Elliptic Curve Diffie-Hellman (X25519)
- **Encryption**: XSalsa20 stream cipher
- **Authentication**: Poly1305 MAC
- **Key Derivation**: HSalsa20

### Implementation Details
- PyNaCl CLI private keys are stored locally in `.keys/` and are never sent to the server.
- Python CLI message bodies are end-to-end encrypted with PyNaCl `Box`; the server stores ciphertext and cannot decrypt that path without client private keys.
- The browser demo stores its local identity material in `localStorage`, which is not suitable for production key storage.
- Browser message bodies are base64-encoded plaintext demo envelopes. Base64 is reversible encoding, the server can read these bodies, and the browser path is not end-to-end encrypted or zero-knowledge.
- The CLI uses one-time prekeys for conversation setup, but it retains prekey private keys and can reuse a session prekey for later messages. This design does not provide forward secrecy or a double ratchet.
- Messages deleted from inbox after retrieval (ephemeral delivery)
- PostgreSQL audit log containing CLI ciphertext or server-readable browser demo envelopes, depending on the client path.
- Authentication challenges and bearer tokens are in-memory and process-local, so they do not survive an API restart or work across multiple API instances.
- Prekey consumption requires authentication, but this demo has no per-user rate limiting; an authenticated account can still exhaust another user's published prekeys.
- Schema changes are applied with `create_all()` only. Existing pre-capstone Docker volumes require the destructive `docker compose down -v` reset before this version starts.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://localhost/encryptochat` | PostgreSQL connection string |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection string |
| `API_URL` | `http://127.0.0.1:8000` | API server URL (client-side) |

## Docker Services

### API Server
- **Image**: Custom (built from Dockerfile)
- **Port**: 8000
- **Environment**: DATABASE_URL, REDIS_URL
- **Auto-reload**: Enabled in development

### PostgreSQL
- **Image**: postgres:15-alpine
- **Port**: 5432
- **Database**: encryptochat
- **User**: encryptochat
- **Password**: encryptochat_password

### Redis
- **Image**: redis:7-alpine
- **Port**: 6379
- **Persistence**: Enabled (redis_data volume)

## Development

### View Logs
```bash
docker compose logs -f api
docker compose logs -f postgres
docker compose logs -f redis
```

### Database Access
```bash
docker compose exec postgres psql -U encryptochat -d encryptochat
```

### Redis CLI
```bash
docker compose exec redis redis-cli
```

### Rebuild After Code Changes
```bash
docker compose up --build
```

## CI/CD

GitHub Actions runs the test suite against PostgreSQL and Redis service containers on pushes and pull requests. The pipeline also validates the Docker image build. Pushes to `main` publish a versioned image and `latest` tag to GitHub Container Registry.

## Future Enhancements

- [ ] Group chat support
- [ ] Prekey rotation and replenishment
- [ ] HTTPS/TLS support
- [ ] Production-grade browser key storage and PyNaCl-compatible browser encryption

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## License

MIT License - see LICENSE file for details

## Author

Built as a demonstration of a PyNaCl end-to-end encrypted CLI path plus a dependency-free browser transport demo.
