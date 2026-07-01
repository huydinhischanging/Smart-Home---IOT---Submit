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

### Option A — One-click launcher (Windows, recommended)

The fastest way to run the full system locally on Windows:

```
double-click: start_dev.bat
```

This script:
1. Checks that `backend\.env` exists (exits with an error if missing — see step below)
2. Verifies Python and Node.js are on PATH
3. Runs `npm install` automatically if `frontend/node_modules` is absent
4. Opens two separate terminal windows: Flask backend on `:5000` and Vite frontend on `:5173`
5. Waits up to 60 seconds for the backend port to be ready before launching the frontend

**Before running for the first time:**
```bat
copy backend\.env.example backend\.env
REM Open backend\.env and fill in: SECRET_KEY, DB_USER, DB_PASS, DB_HOST, DB_NAME, GEMINI_API_KEY
```

---

### Option B — Manual setup (any OS)

#### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # fill in SECRET_KEY, DB_*, MQTT_*, GEMINI_API_KEY
python init_db.py             # create MySQL schema
python run.py                 # → http://localhost:5000
```

API docs: `http://localhost:5000/api/docs` (Swagger UI)

#### 2. Web Dashboard

```bash
cd frontend
npm install
npm run dev                   # → http://localhost:5173
```

#### 3. Mobile App (Flutter)

```bash
cd MOBILE
flutter pub get
flutter run                   # connects to an attached device or running emulator
```

**Android emulator one-click launcher (Windows):**
```
double-click: backend\start_mobile_simulator.bat
```
This script boots a Pixel 7 AVD (`Pixel_7_E36`), waits for ADB to come online, then runs `flutter run` automatically. Edit the top of the file to change `EMULATOR_ID`, `JAVA_HOME`, `PUB_CACHE`, or `FLUTTER_CMD` to match your local paths.

Paths configured inside the script (change if your setup differs):
| Variable | Default |
|---|---|
| `FLUTTER_CMD` | `E:\my-iot-project\Flutter\flutter\bin\flutter.bat` |
| `JAVA_HOME` | `C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot` |
| `ANDROID_AVD_HOME` | `E:\AndroidAVD` |
| `PUB_CACHE` | `E:\pub-cache` |
| `EMULATOR_ID` | `Pixel_7_E36` |

#### 4. ESP32 Firmware

Open `Arduino/` in Arduino IDE. Set your Wi-Fi credentials, MQTT broker address, and room ID in the config section, then flash to your ESP32 board.

#### 5. Heart-Rate Bridge (optional)

```bash
cd backend
python tools/coospo_reader.py   # pairs with Coospo H6 over BLE and re-publishes to MQTT
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
