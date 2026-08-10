# EncryptoChat

A secure end-to-end encrypted messaging system built with FastAPI, PostgreSQL, Redis, and NaCl cryptography.

## Features

- 🔐 **End-to-End Encryption**: Messages encrypted with NaCl Box (Curve25519 + XSalsa20 + Poly1305)
- 🔑 **Prekey Exchange**: X3DH-style forward secrecy with one-time prekeys
- 🗄️ **PostgreSQL**: Durable storage for users, prekeys, and message audit logs
- ⚡ **Redis**: Fast message queues for real-time inbox delivery
- 🐳 **Docker**: One-command deployment with docker-compose
- 🔒 **Zero-Knowledge**: Server cannot decrypt messages (private keys never leave client)

## What This Demonstrates

- FastAPI API design with PostgreSQL and Redis.
- End-to-end encrypted message envelopes using PyNaCl.
- Signed challenge authentication with Ed25519.
- Real-time delivery over WebSockets.
- CI/CD with integration tests and Docker image publishing.

## Architecture

```
Client (Alice)                    Server (FastAPI)                   Client (Bob)
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
| POST | `/send` | Send encrypted message |
| GET | `/inbox/{username}` | Retrieve and clear inbox |
| GET | `/inbox/{username}/count` | Get pending message count |
| POST | `/messages/{message_id}/read` | Mark a delivered message as read |
| GET | `/messages/sent/{username}` | List messages sent by a user |
| GET | `/users/{username}` | Get user's public key |
| GET | `/users/{username}/keys` | Get user's public key + prekey |
| POST | `/users/{username}/prekeys` | Upload prekeys |
| GET | `/users/{username}/prekeys/count` | Get available one-time prekey count |
| WebSocket | `/ws/{username}?token={token}` | Receive real-time encrypted message envelopes |
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
- Private keys stored locally in `.keys/` (never sent to server)
- The demo browser client stores private keys in `localStorage`; this is a demo-only limitation and not suitable for production key storage.
- The browser demo is a REST/WebSocket shell using valid demo ciphertext; it does not implement PyNaCl `Box`-compatible browser encryption, so its messages cannot be decrypted by the CLI client.
- Prekey-based forward secrecy (one prekey per conversation)
- Messages deleted from inbox after retrieval (ephemeral delivery)
- PostgreSQL audit log for message history (encrypted ciphertext only)
- Authentication challenges and bearer tokens are in-memory and process-local, so they do not survive an API restart or work across multiple API instances.

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

Built as a demonstration of end-to-end encrypted messaging with modern web technologies.
