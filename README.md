# ACE Mission Control

ACE Mission Control is a local, real-time robotics operations stack with integrated AI inference.

## Stack

- Frontend: React + Vite + Zustand + Recharts + Leaflet
- Backend: FastAPI + SQLAlchemy + WebSocket broadcast
- AI Modules:
  - Motor failure prediction (LSTM + heuristic fallback)
  - NLP command parsing
  - Vision anomaly monitor (standalone runtime)

## Project Layout

```text
ace project/
├── backend/
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   └── store/useRobotStore.js
│   └── package.json
├── ai_ml/
│   ├── module1/vision_monitor.py
│   └── module2/
│       ├── motor_predictor.py
│       └── nlp_parser.py
├── tests/
├── requirements.txt
├── requirements_backend.txt
├── Dockerfile
└── .env
```

## End-to-End Data Flow

1. Robot telemetry is sent to `POST /telemetry`.
2. Backend validates robot handshake credentials, stores telemetry, and broadcasts to WebSocket clients.
3. Frontend consumes WebSocket events to update cards, charts, map, alerts, and terminal in real time.
4. Operator commands are sent from frontend terminal to `POST /command`.
5. Backend parses commands (basic parser + NLP parser output) and broadcasts command events.
6. Frontend calls AI APIs (`/ai/parse-command`, `/ai/predict/motor`) to display AI insights and risk alerts.

## API Contract

Base URL: `http://localhost:8000`

### Health

- `GET /health`
- Response:

```json
{
  "status": "ok",
  "service": "ace-backend",
  "timestamp": "2026-04-03T13:45:10.123456+00:00",
  "modules": {
    "nlp": true,
    "motor_predictor": true,
    "motor_model_loaded": false
  }
}
```

### Telemetry

- `POST /telemetry`
- Request:

```json
{
  "robot_id": "rover-cam-01",
  "secret_key": "ace-secret-key-123",
  "speed": 10.2,
  "battery": 82.3,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "motor_temp": 56.0,
  "current": 9.2,
  "pitch": 1.2,
  "roll": -0.8,
  "yaw": 102.0,
  "extra": {"rpm": 2400, "vibration": 0.14}
}
```

- Response:

```json
{
  "status": "ok",
  "telemetry_id": 101,
  "robot_id": "rover-cam-01"
}
```

- `GET /telemetry/{robot_id}?limit=100`
- Response: list of telemetry rows ordered newest first.

### Distance

- `GET /distance/{robot_id}`
- Response:

```json
{
  "status": "ok",
  "robot_id": "rover-cam-01",
  "distance_meters": 1265.133,
  "distance_km": 1.265133,
  "gps_points_used": 87,
  "period_hours": 24
}
```

### Fleet Summary

- `GET /robots`
- Response:

```json
{
  "status": "ok",
  "count": 2,
  "robots": [
    {
      "robot_id": "rover-arm-02",
      "timestamp": "2026-04-03T13:44:59.222222+00:00",
      "battery": 72.1,
      "speed": 8.4
    }
  ]
}
```

### Commands

- `POST /command`
- Request:

```json
{
  "robot_id": "rover-cam-01",
  "secret_key": "ace-secret-key-123",
  "command": "return to base immediately"
}
```

- Response:

```json
{
  "status": "queued",
  "type": "command",
  "timestamp": "2026-04-03T13:45:41.101010+00:00",
  "robot_id": "rover-cam-01",
  "command": "return to base immediately",
  "parsed": {"raw": "return to base immediately", "action": "return", "args": ["to", "base", "immediately"]},
  "nlp": {
    "issues": [{"component": "Battery", "description": "...", "severity": "high"}],
    "directives": [{"action": "Return to base immediately", "target": "Navigation", "urgency": "high"}],
    "overall_status": "EMERGENCY",
    "mode": "rule-based"
  }
}
```

### AI APIs

- `POST /ai/parse-command`
- Request:

```json
{"text": "switch to safe mode immediately"}
```

- Response:

```json
{
  "status": "ok",
  "text": "switch to safe mode immediately",
  "parsed": {
    "issues": [],
    "directives": [{"action": "Engage autonomous safe mode", "target": "Control System", "urgency": "high"}],
    "overall_status": "SAFE",
    "mode": "rule-based"
  }
}
```

- `POST /ai/predict/motor`
- Request:

```json
{
  "robot_id": "rover-cam-01",
  "secret_key": "ace-secret-key-123",
  "history": [
    {"current": 19.8, "rpm": 1850, "temperature": 81.3, "vibration": 0.26}
  ]
}
```

- Response:

```json
{
  "status": "ok",
  "robot_id": "rover-cam-01",
  "failure_probability": 0.379,
  "risk_level": "medium",
  "samples_used": 1
}
```

### WebSocket

- `WS /ws`
- Server pushes:
  - `snapshot`
  - `telemetry`
  - `command`
  - `ai_insight`
- Client may send:

```json
{"type": "ping"}
```

```json
{
  "type": "command",
  "robot_id": "rover-cam-01",
  "secret_key": "ace-secret-key-123",
  "command": "stop"
}
```

## Local Run Guide

### 1) Backend

From project root:

```bash
pip install -r requirements_backend.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Optional environment variables:

- `DATABASE_URL` (default `sqlite:///./data/telemetry.db`)
- `ALLOWED_ORIGINS` (comma-separated, default `*`)

### 2) Frontend

From project root:

```bash
cd frontend
npm install
npm run dev
```

Optional frontend env:

- `VITE_API_URL` (default `http://localhost:8000`)
- `VITE_WS_URL` (default `ws://localhost:8000/ws`)

### 3) Demo Telemetry

Start simulation stream:

```bash
curl http://localhost:8000/demo/start
```

The frontend dashboard will auto-connect and update in real time.

### 4) AI Modules (Standalone)

Motor model training/artifacts:

```bash
cd ai_ml/module2
python motor_predictor.py
```

NLP parser local run:

```bash
cd ai_ml/module2
python nlp_parser.py
```

Vision restricted-zone monitor:

```bash
cd ai_ml/module1
python vision_monitor.py --source 0
```

## Quality Notes

- No frontend mock telemetry is used after initialization.
- Live state is derived from backend REST + WebSocket messages.
- Backend handles malformed WebSocket payloads and invalid command inputs safely.
- Fast path tests: `pytest tests -m "not slow" -q`.
