# ACE Mission Control

ACE Mission Control is a beginner-friendly robotics monitoring system with four connected parts:
- FastAPI backend (REST + WebSocket)
- React dashboard frontend
- YOLOv8 restricted-zone vision monitor
- LSTM + NLP predictive intelligence modules

## Project Structure

```text
ace project/
├── backend/
│   └── main.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       └── pages/
│           └── MissionControl.jsx
├── ai_ml/
│   ├── module1/
│   │   └── vision_monitor.py
│   └── module2/
│       ├── motor_predictor.py
│       └── nlp_parser.py
├── tests/
├── requirements.txt
├── requirements_backend.txt
├── Dockerfile
└── README.md
```

## 1) Local Setup

### Python dependencies

```bash
pip install -r requirements.txt
```

### Frontend dependencies

```bash
cd frontend
npm install
```

## 2) Run Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend docs:
- http://localhost:8000/docs

Core endpoints:
- `POST /telemetry`
- `GET /telemetry/{robot_id}`
- `GET /distance/{robot_id}`
- `POST /command`
- `GET /robots`
- `GET /demo/start`
- `WS /ws`

Authentication handshake:
- `rover-cam-01 -> ace-secret-key-123`
- `rover-arm-02 -> ace-secret-key-456`

## 3) Run Frontend Dashboard

```bash
cd frontend
npm run dev
```

Frontend URL:
- http://localhost:3000

Features implemented:
- Live WebSocket telemetry updates (~10 Hz with demo stream)
- Disconnected banner with last-known values retained
- Battery, temperature, current gauges
- IMU bars
- Motor current chart
- GPS path canvas
- Manual/Autonomous toggle
- Command terminal (`/move_forward 50`, `/stop`, etc.)
- Command logs updated dynamically from backend WS broadcasts

## 4) AI/ML Module 1: Vision Monitor

```bash
cd ai_ml/module1
python vision_monitor.py --source 0
```

You can also run with a video file:

```bash
python vision_monitor.py --source path/to/video.mp4
```

What it does:
- Loads YOLOv8n (`yolov8n.pt`)
- Detects `person`, `bottle`, `backpack`
- Uses `.track(..., persist=True)` for stable object IDs
- Uses a 4-point draggable polygon ROI
- Uses point-in-polygon test on detection center
- ROI turns green (safe) or red (breach)
- Logs ENTRY / EXIT / duration to `breach_log.jsonl`
- Displays rolling FPS
- Uses frame skipping (`frame_skip=2`) for lower latency

## 5) AI/ML Module 2: Motor Predictor

```bash
cd ai_ml/module2
python motor_predictor.py
```

What it does:
- Generates synthetic telemetry (`current`, `rpm`, `temperature`, `vibration`)
- Trains LSTM to predict failure probability
- Prints validation RMSE
- Saves `training_curve.png`
- Saves `motor_lstm.pt`, `scaler_mean.npy`, `scaler_scale.npy`
- Runs live inference demo that differentiates:
  - high-performance operation (no false alert)
  - true failure build-up (failure alert)

## 6) AI/ML Module 2: NLP Parser

```bash
cd ai_ml/module2
python nlp_parser.py
```

Optional OpenAI path:

```bash
set OPENAI_API_KEY=sk-xxx
python nlp_parser.py
```

What it does:
- Extracts structured `issues` and `directives`
- Classifies severity and urgency
- Returns overall status (`SAFE`, `CAUTION`, `ALERT`, `EMERGENCY`)
- Saves `nlp_parse_log.json`
- Includes Jetson deployment strategy output (GGUF, RAG, BERT)

## 7) Performance Notes

Typical local behavior:
- Vision loop with frame skipping: usually in ~25–35 FPS range on standard laptop webcams
- Backend demo stream: 10 updates/sec (`/demo/start` loop sleeps 0.1s)
- WebSocket updates are broadcast on telemetry ingestion and command events

## 8) Integration Summary

How data flows through the system:
1. Robot (or demo) sends telemetry to backend `/telemetry`
2. Backend validates secret key and stores telemetry in SQLAlchemy DB
3. Backend broadcasts telemetry to all frontend WS clients
4. Frontend updates gauges/chart/map/last-known state in real time
5. Operator sends commands from frontend terminal to `/command`
6. Backend parses command and broadcasts it via WS
7. Vision and predictive modules run independently and can be integrated into telemetry pipelines

## 9) Docker Deployment (Backend)

Build:

```bash
docker build -t ace-backend .
```

Run:

```bash
docker run -d -p 8000:8000 --name ace-backend ace-backend
```

Notes:
- Dockerfile uses `uvicorn main:app --host 0.0.0.0 --port $PORT`
- `PORT` defaults to `8000` in Dockerfile via `ENV PORT=8000`
- For cloud deployment, set `DATABASE_URL` and `PORT` from environment variables

## 10) Run Tests

```bash
pytest tests/ -v
```

Fast run excluding slow tests:

```bash
pytest tests/ -v -m "not slow"
```
