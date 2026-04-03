# ACE Mission Control

ACE Mission Control is a real-time robotics command and telemetry platform with a FastAPI backend, React dashboard, and AI/ML modules for vision monitoring, motor risk prediction, transcript parsing, and strategy optimization.

## Features

- Real-time telemetry ingestion with persistent storage
- WebSocket event bus and 10 Hz telemetry tick stream
- AI APIs for motor risk, vision zone analysis, NLP parsing, and Monte Carlo strategy optimization
- Dashboard with telemetry cards, charts, map tracking, alerts, command terminal, and live HUD overlay
- Built-in demo simulator for local testing and presentations

## Project Structure

```text
backend/                    FastAPI service
frontend/                   React + Vite dashboard
ai_ml/module1/              Vision monitor (YOLO + polygon ROI)
ai_ml/module2/              Motor predictor, NLP parser, strategy optimizer
tests/                      Backend and AI test suite
requirements_backend.txt    Backend Python dependencies
requirements_ai.txt         AI/ML Python dependencies
```

## Prerequisites

- Python 3.11+ (virtual environment recommended)
- Node.js 18+
- npm 9+

## Quick Start

1. Install backend dependencies.

```bash
pip install -r requirements_backend.txt
```

2. Install AI dependencies.

```bash
pip install -r requirements_ai.txt
```

3. Install frontend dependencies.

```bash
cd frontend
npm install
cd ..
```

4. Train and save motor model artifacts (recommended).

```bash
python ai_ml/module2/train_and_save.py
```

5. Start backend.

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

6. Start frontend.

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

7. Start demo telemetry stream.

```bash
curl http://localhost:8000/demo/start
```

## URLs

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Authentication

Supported authentication modes:

- Payload mode: `robot_id` + `secret_key`
- Header mode: `X-API-Key` and optional `X-Robot-Id`

Default credentials:

- rover-cam-01 / ace-secret-key-123
- rover-arm-02 / ace-secret-key-456

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | /health | Service health and runtime status |
| POST | /telemetry | Ingest robot telemetry |
| POST | /api/telemetry | Alias telemetry ingest endpoint |
| GET | /telemetry/{robot_id} | Telemetry history for one robot |
| GET | /api/telemetry/latest/{robot_id} | Latest telemetry sample for one robot |
| GET | /api/telemetry/latest | Latest telemetry for all robots |
| GET | /distance/{robot_id} | 24-hour distance using Haversine |
| GET | /api/telemetry/distance?robot_id=... | Alias distance endpoint |
| GET | /robots | Fleet summary |
| POST | /command | Command ingest and parse |
| POST | /api/command | Alias command endpoint |
| POST | /ai/predict/motor | Motor risk prediction |
| POST | /api/ai/motor-predict | Alias motor endpoint |
| POST | /ai/parse-command | NLP parser endpoint |
| POST | /api/ai/nlp-parse | Alias NLP endpoint |
| POST | /api/ai/vision-analyze | Vision anomaly and zone analysis |
| POST | /api/ai/strategy-optimize | Monte Carlo strategy optimizer |
| POST | /api/strategy/optimize | Alias strategy endpoint |
| GET | /demo/start | Start simulator |
| GET | /demo/stop | Stop simulator |
| WS | /ws | Event WebSocket |
| WS | /ws/telemetry | 10 Hz telemetry WebSocket |

## AI Modules

### Vision Monitor

File: `ai_ml/module1/vision_monitor.py`

```bash
python ai_ml/module1/vision_monitor.py --source 0
```

Capabilities:

- YOLOv8 person and vehicle detection
- Editable polygon restricted zone
- Entry and exit logging with occupancy duration
- Live FPS and optional callback payloads for integration

### Motor Predictor

Files:

- `ai_ml/module2/motor_predictor.py`
- `ai_ml/module2/train_and_save.py`

Artifacts:

- `ai_ml/module2/motor_lstm.pt`
- `ai_ml/module2/scaler_mean.npy`
- `ai_ml/module2/scaler_scale.npy`
- `ai_ml/module2/training_curve.png`

### NLP Parser

File: `ai_ml/module2/nlp_parser.py`

Supports:

- Gemini API mode (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)
- OpenAI API mode (`OPENAI_API_KEY`)
- Rule-based fallback mode

### Strategy Optimizer

File: `ai_ml/module2/strategy_optimizer.py`

Inputs:

- Tire age
- Track temperature
- Fuel load
- Safety car probability

Output:

- Best pit lap
- Expected race time
- Candidate strategy set

## Environment Variables

### Root `.env` and `backend/.env`

| Variable | Description |
|---|---|
| DATABASE_URL | Database connection string |
| HOST | Backend host |
| PORT | Backend port |
| ALLOWED_ORIGINS | CORS allowed origins |
| GOOGLE_API_KEY | Optional Gemini key alias |
| GEMINI_API_KEY | Optional Gemini API key |
| OPENAI_API_KEY | Optional OpenAI API key |

### `frontend/.env`

| Variable | Description |
|---|---|
| VITE_API_URL | Backend HTTP base URL |
| VITE_WS_URL | Backend WebSocket URL |

## Testing

Run the full suite:

```bash
pytest tests/ -v
```

Run non-slow tests:

```bash
pytest tests/ -v -m "not slow"
```

## Troubleshooting

- If PostgreSQL driver is unavailable, backend automatically falls back to SQLite.
- If `motor_lstm.pt` cannot be loaded, backend uses heuristic motor prediction fallback.
- If camera permission is denied, the dashboard HUD shows simulated vision mode and uses telemetry boxes.
- If map tiles appear too dark, verify Leaflet tile filters in `frontend/src/index.css`.

## License

Internal project for ACE mission control development and evaluation.
