# ACE Mission Control

Full-stack mission dashboard with AI/ML modules:
- FastAPI backend with REST + WebSocket telemetry
- React/Vite frontend mission control dashboard
- YOLOv8 restricted-zone vision monitor
- LSTM motor failure predictor
- NLP transcript parser with optional OpenAI path

## Project Structure

```text
ace-mission-control/
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
├── requirements.txt
├── Dockerfile
└── README.md
```

## Quick Start

### 1) Install Python Dependencies

```bash
cd ace-mission-control
pip install -r requirements.txt
```

### 2) Start Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 3) Start Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Dashboard: http://localhost:3000

Optional frontend env configuration:

```bash
cp .env.example .env
```

Variables:
- VITE_API_URL
- VITE_WS_URL

### 4) Start Demo Stream

Open dashboard and click Start Demo.

## Backend Endpoints

- POST /telemetry
- GET /telemetry/{robot_id}
- GET /distance/{robot_id}
- POST /command
- GET /robots
- WS /ws
- GET /demo/start

## Robot Handshake

Use secret key in POST requests:

```json
{
  "robot_id": "rover-cam-01",
  "secret_key": "ace-secret-key-123"
}
```

## AI/ML Module 1

```bash
cd ai_ml/module1
python vision_monitor.py
python vision_monitor.py --source path/to/video.mp4
```

Features:
- Detect person, bottle, backpack
- Editable 4-point polygon ROI
- ROI breach color change
- Entry/exit and occupancy logs to breach_log.jsonl
- FPS counter and frame-skip optimization

## AI/ML Module 2

### LSTM Motor Predictor

```bash
cd ai_ml/module2
python motor_predictor.py
```

Saves training_curve.png and prints RMSE.

### NLP Transcript Parser

```bash
python nlp_parser.py
OPENAI_API_KEY=sk-xxx python nlp_parser.py
```

## Docker

```bash
docker build -t ace-backend .
docker run -d -p 8000:8000 --name ace-backend ace-backend
```
