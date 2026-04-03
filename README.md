# ACE Recruitment Mission Control

## Project Overview

ACE Recruitment Mission Control is a real-time robotics telemetry platform with a FastAPI backend, React mission dashboard, and AI/ML modules for motor failure prediction, vision zone analysis, and command-language parsing.

Core capabilities:
- Live telemetry ingestion and persistence
- Real-time WebSocket streaming to dashboard clients
- AI endpoints for motor, vision, and NLP analysis
- Command terminal integration with structured parsing
- Demo simulator for interview and offline verification

## Architecture Diagram

```text
+----------------------+        +--------------------------+
|  AI/ML Modules       |        |  Robot / Demo Telemetry  |
|  - motor_predictor   |        |  POST /telemetry         |
|  - vision_monitor    |        +-------------+------------+
|  - nlp_parser        |                      |
+----------+-----------+                      v
           |                         +-----------------------+
           | API calls               | FastAPI Backend       |
           +-----------------------> | - REST endpoints      |
                                     | - SQLAlchemy + DB     |
                                     | - WebSocket broadcast |
                                     +----------+------------+
                                                |
                                  WS /ws, WS /ws/telemetry
                                                |
                                                v
                                     +-----------------------+
                                     | React Frontend        |
                                     | - Zustand store       |
                                     | - Telemetry cards     |
                                     | - Charts + Map + AI   |
                                     | - Command terminal    |
                                     +-----------------------+
```

## Quick Start (4 Steps)

1. Install dependencies

```bash
pip install -r requirements_backend.txt
cd frontend
npm install
cd ..
```

2. Train and save motor model artifacts

```bash
python ai_ml/module2/train_and_save.py
```

3. Start backend

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

4. Start frontend

```bash
cd frontend
npm run dev
```

After startup:
- Backend docs: http://localhost:8000/docs
- Frontend app: http://localhost:5173

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Service health, DB status, model availability, websocket counts |
| POST | /telemetry | Ingest robot telemetry with handshake auth |
| GET | /telemetry/{robot_id} | Get recent telemetry history |
| GET | /api/telemetry/latest/{robot_id} | Get latest telemetry sample |
| GET | /distance/{robot_id} | Compute 24h traveled distance |
| GET | /api/telemetry/distance?robot_id=... | Alias 24h traveled distance endpoint |
| GET | /robots | Latest summary per robot |
| POST | /command | Command ingest + parse + broadcast |
| POST | /api/command | Alias command endpoint |
| POST | /ai/predict/motor | Motor failure prediction |
| POST | /api/ai/motor-predict | Alias motor prediction endpoint |
| POST | /ai/parse-command | NLP command parsing |
| POST | /api/ai/nlp-parse | Alias NLP parsing endpoint |
| POST | /api/ai/vision-analyze | Vision zone/anomaly API |
| POST | /api/ai/strategy-optimize | Monte Carlo strategy optimization |
| POST | /api/strategy/optimize | Alias strategy optimization endpoint |
| GET | /demo/start | Start telemetry simulator |
| GET | /demo/stop | Stop telemetry simulator |
| WS | /ws | Event bus (snapshot, telemetry, command, ai_insight) |
| WS | /ws/telemetry | 10Hz telemetry tick stream |

Auth notes:
- Payload-based handshake remains supported: `robot_id` + `secret_key` fields.
- Header-based handshake is also supported for robot clients: `X-API-Key` and optional `X-Robot-Id`.

## AI/ML Modules

### 1) Vision Monitor
File: ai_ml/module1/vision_monitor.py

Run:
```bash
python ai_ml/module1/vision_monitor.py --source 0
```

What it does:
- YOLOv8 object tracking
- Polygon ROI breach detection
- ENTRY/EXIT duration logging to JSONL
- Optional callback payload emission for frontend/websocket integration (`fps`, `zone_breach`, `detections`)

### 2) Motor Predictor
File: ai_ml/module2/motor_predictor.py

Run training + save artifacts:
```bash
python ai_ml/module2/train_and_save.py
```

Artifacts produced:
- ai_ml/module2/motor_lstm.pt
- ai_ml/module2/scaler_mean.npy
- ai_ml/module2/scaler_scale.npy
- ai_ml/module2/training_curve.png

### 3) NLP Parser
File: ai_ml/module2/nlp_parser.py

Run:
```bash
python ai_ml/module2/nlp_parser.py
```

What it does:
- Extracts issues/directives from command text
- Produces overall status (SAFE/CAUTION/ALERT/EMERGENCY)

## Frontend Features

- Componentized dashboard layout with shared Zustand state
- Live telemetry cards (speed, battery, motor temp, current, IMU)
- Real-time chart updates and GPS map path
- AI insights panel fed from backend events
- Alerts panel with live threshold-triggered backend alerts
- Command terminal connected to backend command/NLP/motor APIs
- WebSocket reconnect handling and graceful failure display

## Environment Variables

### Backend (backend/.env)

| Variable | Description | Example |
|---|---|---|
| DATABASE_URL | SQLAlchemy DB URL | postgresql://... |
| HOST | Backend host | 127.0.0.1 |
| PORT | Backend port | 8000 |
| ALLOWED_ORIGINS | CORS origins | http://localhost:5173 |

### Frontend (frontend/.env)

| Variable | Description | Example |
|---|---|---|
| VITE_API_URL | REST API base URL | http://localhost:8000 |
| VITE_WS_URL | WebSocket URL | ws://localhost:8000/ws |

## Docker Deployment

Build image:
```bash
docker build -t ace-backend .
```

Run container:
```bash
docker run -d -p 8000:8000 --name ace-backend \
  -e DATABASE_URL="postgresql://..." \
  -e PORT=8000 \
  ace-backend
```

Health check:
- http://localhost:8000/health

## Interview Talking Points

- Designed dual websocket strategy: event bus on /ws and fixed-rate telemetry stream on /ws/telemetry.
- Implemented fallback-safe motor prediction so service stays available even when model artifacts are missing.
- Added explicit startup warnings and training bootstrap to guarantee deterministic interview setup.
- Kept backend deploy-light by splitting AI dependencies into requirements_ai.txt.
- Built frontend as a state-driven architecture (Zustand) to isolate transport, state, and presentation concerns.
- Enforced additive backend evolution with alias routes for backward compatibility during refactor.

## Verification Commands

```bash
python ai_ml/module2/train_and_save.py
pytest tests/ -v
pytest tests/ -v -m "not slow"
```

```bash
make help
```
