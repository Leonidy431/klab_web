# K-Laboratory Backend Platform

Full-stack backend for K-Laboratory underwater robotics platform with BlueOS integration, e-commerce shop, community forum, and FinTech integrations.

## Features

| Module | Description |
|--------|-------------|
| **BlueOS** | ROV control, telemetry, video streaming via MAVLink |
| **Shop** | E-commerce with Stripe payments |
| **Forum** | Community discussions |
| **FinTech** | Revolut webhooks + Telegram notifications |

## Tech Stack

- **Framework:** FastAPI 0.109+
- **Database:** PostgreSQL 16 + SQLAlchemy 2.0 (async)
- **Cache:** Redis 7
- **Tasks:** Celery
- **ROV:** PyMAVLink + BlueOS API
- **Payments:** Stripe
- **Notifications:** Telegram Bot API

---

## Quick Start

### 1. Clone and Setup

```bash
cd klab_web/backend
cp .env.example .env
# Edit .env with your credentials
```

### 2. Docker Deployment (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Check status
docker-compose ps
```

### 3. Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Configuration

### Environment Variables

Create `.env` file from `.env.example`:

```bash
# Core
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://klab:password@localhost:5432/klab
REDIS_URL=redis://localhost:6379/0

# BlueOS (ROV)
BLUEOS_HOST=192.168.2.2

# Stripe (Shop)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Revolut (FinTech)
REVOLUT_SIGNING_SECRET=your_secret

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=-100123456789
```

---

## BlueOS Integration

### Network Setup

BlueOS runs on ROV's Raspberry Pi at `192.168.2.2`:

```
┌─────────────────────────────────────────────────┐
│              Your Computer                       │
│  ┌─────────────────────────────────────────┐    │
│  │  K-Laboratory Backend (this)            │    │
│  │  - FastAPI: port 8000                   │    │
│  │  - WebSocket: /ws/telemetry             │    │
│  └─────────────────────────────────────────┘    │
│                    │                             │
│              Ethernet/Tether                     │
│                    │                             │
└────────────────────┼────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────┐
│                    ▼                             │
│  ┌─────────────────────────────────────────┐    │
│  │  BlueOS (192.168.2.2)                   │    │
│  │  - REST API: port 80                    │    │
│  │  - MAVLink: port 14550                  │    │
│  │  - Video: port 5600                     │    │
│  └─────────────────────────────────────────┘    │
│              ROV Raspberry Pi                    │
└─────────────────────────────────────────────────┘
```

### API Endpoints

```
GET  /api/v1/rov/status      - ROV system status
GET  /api/v1/rov/telemetry   - Current telemetry
POST /api/v1/rov/lights      - Set lights level
GET  /api/v1/rov/streams     - Video stream URLs
WS   /api/v1/rov/telemetry/ws - Real-time telemetry
```

---

## Revolut Webhook Setup

### 1. Configure Webhook in Revolut Business

1. Go to [Revolut Business Settings](https://business.revolut.com/settings/api)
2. Create new webhook
3. Set URL: `https://your-domain.com/api/v1/webhooks/revolut`
4. Select events: `TransactionCreated`, `TransactionStateChanged`
5. Copy signing secret to `.env`

### 2. Expose for Testing (Ngrok)

```bash
# Install ngrok
brew install ngrok  # or download from ngrok.com

# Expose local server
ngrok http 8000

# Use the HTTPS URL for Revolut webhook
# https://abc123.ngrok.io/api/v1/webhooks/revolut
```

### 3. BlueOS Extension Deployment

To run as BlueOS extension:

```dockerfile
# Dockerfile.blueos
FROM python:3.12-slim

# BlueOS extension metadata
LABEL permissions='{"NetworkMode": "host"}'
LABEL authors='["Leonidy431"]'
LABEL company='K-Laboratory'
LABEL version='1.0.0'
LABEL website='https://k-laboratory.com'
LABEL readme='https://github.com/Leonidy431/klab_web'

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Register in BlueOS:
1. Go to BlueOS → Extensions
2. Click "+" to add custom extension
3. Enter Docker image URL or build locally

---

## Telegram Bot Setup

### 1. Create Bot

1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions, get token
4. Add token to `.env`

### 2. Get Chat ID

```bash
# Start bot, send message, then:
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
# Find chat.id in response
```

### 3. Message Format

Income notification:
```
🟢 Incoming Payment

From: Client X
Amount: +€1,500.00
📋 Ref: INV-001
💼 Balance: €10,500.00

📅 2026-02-07 12:30 UTC
```

---

## API Documentation

Once running, visit:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/api/v1/openapi.json

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── blueos.py    # ROV control
│   │       │   ├── shop.py      # E-commerce
│   │       │   ├── forum.py     # Community
│   │       │   └── webhooks.py  # Revolut/Stripe
│   │       └── __init__.py
│   ├── core/
│   │   ├── config.py            # Settings
│   │   └── database.py          # PostgreSQL
│   ├── models/
│   │   ├── user.py
│   │   ├── shop.py
│   │   └── forum.py
│   ├── modules/
│   │   ├── blueos/              # ROV integration
│   │   │   ├── client.py        # BlueOS HTTP API
│   │   │   ├── mavlink.py       # MAVLink control
│   │   │   ├── telemetry.py     # Real-time data
│   │   │   └── video.py         # Video streams
│   │   ├── shop/                # E-commerce
│   │   │   ├── service.py
│   │   │   ├── cart.py
│   │   │   └── payment.py       # Stripe
│   │   ├── forum/               # Community
│   │   │   └── service.py
│   │   └── fintech/             # Financial
│   │       ├── revolut.py       # Webhook handler
│   │       └── telegram.py      # Notifications
│   └── main.py                  # FastAPI app
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Security Notes

1. **Never commit `.env`** - Contains secrets
2. **Validate all webhooks** - Check signatures
3. **Use HTTPS in production** - Required for webhooks
4. **Rotate secrets regularly** - JWT, Stripe, Revolut keys

---

## License

Proprietary - K-Laboratory, Inc. © 2026

See [patent.md](../patent.md) for intellectual property declaration.
