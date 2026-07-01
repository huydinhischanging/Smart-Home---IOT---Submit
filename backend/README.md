# Batman OS — Smart Elderly Care Backend

Flask-based IoT backend for the Smart Home Elderly Care system.  
Real-time device control, AI health assistant, medicine reminders, and alert management.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY, INTERNAL_TOKEN, DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME

# 3. Initialize database
python init_db.py        # tạo schema MySQL

# 4. Run development server
python run.py            # http://localhost:5000
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3 + Flask-SocketIO |
| Architecture | Clean / Hexagonal (Domain → UseCase → Infra → Presentation) |
| Dependency injection | `dependency-injector` container (`app/wiring.py`) |
| Database ORM | SQLAlchemy + Flask-Migrate |
| Real-time | Socket.IO (WebSocket) |
| IoT protocol | MQTT over TLS (HiveMQ / Mosquitto) |
| AI assistant | Google Gemini 2.5 Flash (cloud) + Ollama/Qwen2.5:3b (local fallback) |
| Authentication | HttpOnly cookie (`batman_os_auth`) + `itsdangerous` signed token |
| Rate limiting | Flask-Limiter (Redis if `REDIS_URL` set, memory fallback) |
| Task scheduler | APScheduler — medicine reminders, device automations |
| Email alerts | SMTP / Brevo transactional API |
| API docs | Swagger UI at `/api/docs` (OpenAPI 3.0 spec) |

---

## Project Structure

```
app/
├── config/          # Settings loader
├── domain/          # Pure domain entities & interfaces
├── usecases/        # Business logic (framework-free)
├── infrastructure/  # DB models, repositories, file config
├── presentation/    # Flask blueprints (API routes)
├── gateways/        # MQTT publisher, Socket.IO emitter, email notifier
├── ai/              # Gemini + Ollama inference
├── extensions/      # db, mqtt, socketio, limiter singletons
├── scheduler.py     # APScheduler jobs
└── wiring.py        # DI container
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns auth cookie + token |
| POST | `/api/auth/logout` | Clear auth cookie |
| GET | `/api/auth/me` | Current user profile |
| POST | `/api/auth/forgot-password` | Request password reset code |
| POST | `/api/auth/reset-password` | Reset with token |
| GET | `/api/devices` | List user's devices |
| POST | `/api/devices` | Create device |
| POST | `/api/devices/control` | Send ON/OFF/value command via MQTT |
| DELETE | `/api/devices/<name>` | Delete device |
| GET | `/api/rooms` | List rooms |
| POST | `/api/rooms` | Create room |
| GET | `/api/alerts` | List alerts with filters |
| POST | `/api/reminders` | Create medicine reminder |
| GET | `/api/reminders` | List reminders |
| DELETE | `/api/reminders/<id>` | Delete reminder |
| POST | `/api/ai/ask` | Alfred AI assistant query |
| GET | `/api/patient/profile` | Patient health profile |
| GET | `/api/health` | Health check (DB status) |
| GET | `/api/docs` | Swagger UI |

Full spec: `/api/docs/openapi.yaml`

---

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Token signing key (`secrets.token_urlsafe(32)`) |
| `INTERNAL_TOKEN` | Yes | GUI ↔ API internal auth |
| `MQTT_ENABLED` | No | `false` to run without broker |
| `DB_USER/PASS/HOST/NAME` | Prod | MySQL connection |
| `GEMINI_API_KEY` | No | Google Gemini AI |
| `SMTP_HOST/USERNAME/PASSWORD` | No | Email alert delivery |
| `REDIS_URL` | No | Redis for rate limiter (falls back to memory) |

---

## Running Tests

```bash
python -m pytest          # runs all 120 tests with coverage report
python -m pytest --no-cov # skip coverage (faster)
```

Current coverage: **~53%** across usecases, API, and integration flows.

---

## Docker

```bash
docker build -t batman-os-backend .
docker run -p 5000:5000 --env-file .env batman-os-backend
```

---

## Database Setup (Production — MySQL)

```bash
# Create DB and user
python init_db.py

# Apply migrations
flask db upgrade
```

Điền đầy đủ `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME` trong `.env` để sử dụng MySQL.
