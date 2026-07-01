# Smart Home for Elderly Care — IoT System

A full-stack IoT platform for monitoring and assisting elderly people living at home. The system combines environmental and physiological sensing, machine-learning anomaly detection, an AI conversational assistant, and caregiver-facing web and mobile apps into a single open-source platform.

Built as an undergraduate thesis project at HCMC International University (IU), 2025–2026.

---

## What It Does

- **Real-time monitoring** — ESP32 nodes collect temperature, humidity, light (LDR), and motion (PIR) from each room. A Coospo H6 BLE chest strap streams heart-rate data via a Python bridge.
- **Health anomaly detection** — An Isolation Forest model trained on the UCI Heart Disease dataset flags abnormal heart-rate readings and classifies them into four risk levels (Normal / Caution / Warning / Critical). Alerts are pushed instantly to the caregiver.
- **Alfred AI assistant** — A three-layer inference pipeline: keyword rule engine → local Ollama LLM (Qwen2.5:3b) → Google Gemini fallback. Alfred understands voice and text commands in Vietnamese and English, controls devices, and answers health-related questions using live sensor context.
- **Medicine reminders** — Scheduled notifications sent to the mobile app with configurable repeat intervals.
- **Interactive floor plan** — Web dashboard lets caregivers draw room zones on an HTML Canvas floor plan and control devices room by room.
- **Mobile app** — Flutter app for iOS and Android with live sensor feed, alert history, Alfred chat, and reminder management.

---

## System Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Clients                           │
│   Web Dashboard (Vite + Vanilla JS)                    │
│   Mobile App (Flutter / Dart)                          │
└────────────┬───────────────────────────────────────────┘
             │  REST API  +  Socket.IO (real-time)
┌────────────▼───────────────────────────────────────────┐
│               Flask Backend  (Batman OS)               │
│  Clean architecture · APScheduler · SQLAlchemy         │
│  Alfred AI · Isolation Forest · Rate limiting          │
└────────────┬───────────────────────────────────────────┘
             │  MQTT over TLS (EMQX Cloud, port 8883)
┌────────────▼───────────────────────────────────────────┐
│               Edge / Sensor Layer                      │
│  ESP32 (DHT11, LDR, PIR, relay control)                │
│  Coospo H6 BLE → coospo_reader.py → MQTT              │
└────────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
├── Arduino/          ESP32 firmware (C++ / Arduino)
├── backend/          Flask API server
│   ├── app/          Application code (domain / usecases / infra / presentation)
│   ├── tools/        Utility scripts (grid search, anomaly retraining)
│   └── tests/        Pytest suite (448 tests, ~53% coverage)
├── frontend/         Vite web dashboard (Vanilla JS)
├── MOBILE/           Flutter mobile app
├── TLPB/             PCB schematic and layout files
└── File-report/      LaTeX thesis source (Overleaf-compatible)
```

---

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # fill in SECRET_KEY, DB_*, MQTT_*, GEMINI_API_KEY
python init_db.py             # create MySQL schema
python run.py                 # http://localhost:5000
```

API docs available at `http://localhost:5000/api/docs` (Swagger UI).

### 2. Web Dashboard

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### 3. Mobile App

```bash
cd MOBILE
flutter pub get
flutter run
```

### 4. ESP32 Firmware

Open `Arduino/` in Arduino IDE. Set your Wi-Fi credentials, MQTT broker address, and room ID in the config section, then flash to your ESP32 board.

### 5. Heart-Rate Bridge (optional)

```bash
cd backend
python tools/coospo_reader.py   # pairs with Coospo H6 over BLE and publishes to MQTT
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Firmware | ESP32 · Arduino C++ · MQTT TLS |
| Backend | Python 3.12 · Flask 3 · Flask-SocketIO · SQLAlchemy |
| ML | scikit-learn Isolation Forest · UCI Heart Disease dataset |
| AI assistant | Google Gemini 2.5 Flash · Ollama Qwen2.5:3b (local) |
| Web frontend | Vite · Vanilla JS · HTML Canvas |
| Mobile | Flutter 3 · Dart |
| Database | MySQL (production) · SQLite (development / CI) |
| Broker | EMQX Cloud (MQTT over TLS, port 8883) |
| Auth | HttpOnly cookie (web) · Bearer token (mobile) · `itsdangerous` |
| Email alerts | SMTP / Brevo transactional API |
| PCB | KiCad |

---

## Hardware

- ESP32 DevKit (×2, one per room in the demo)
- DHT11 temperature and humidity sensor
- LDR (photoresistor) with 10 kΩ voltage divider
- HC-SR501 PIR motion sensor
- 4-channel 5 V relay module
- Coospo H6 BLE heart-rate chest strap
- Custom PCB (see `TLPB/`)

---

## Key Design Decisions

**Single heart-rate feature for anomaly detection.** Adding the seven available contextual features (temperature, humidity, light, time-of-day, etc.) reduced Isolation Forest recall on the anomaly class. Heart rate alone gave the best trade-off.

**BPM approximation caveat.** The UCI Heart Disease dataset records peak exercise heart rate (`thalach`), not resting BPM. Training data uses `thalach × U(0.55, 0.65)` as a resting approximation — this is a prototype-grade workaround, not a clinically validated method.

**Local LLM first.** Alfred tries the Ollama local model before falling back to Gemini, keeping the system usable without an internet connection and avoiding sending user health data to a cloud API unnecessarily.

---

## Running Tests

```bash
cd backend
python -m pytest              # 448 tests
python -m pytest --no-cov     # faster, no coverage report
```

---

## Thesis

The full thesis report (LaTeX source) is in `File-report/Overleaf_Project/`. The compiled PDF covers system design, ML methodology, evaluation results, and limitations.

---

## Author

**Dinh Huy** — ITITIU21213  
Ho Chi Minh City International University, School of Computer Science and Engineering  
Thesis supervisor: [supervisor name]  

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
