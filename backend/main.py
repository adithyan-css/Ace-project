import asyncio
import json
import math
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, desc, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

try:
    from ai_ml.module2 import nlp_parser
except Exception:
    nlp_parser = None

try:
    import numpy as np
except Exception:
    np = None

try:
    import torch
except Exception:
    torch = None

try:
    from ai_ml.module2 import motor_predictor
except Exception:
    motor_predictor = None


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/telemetry.db")

VALID_ROBOT_CREDENTIALS = {
    "rover-cam-01": "ace-secret-key-123",
    "rover-arm-02": "ace-secret-key-456",
}

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    robot_id: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    speed: Mapped[float] = mapped_column(Float)
    battery: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    motor_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pitch: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roll: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yaw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TelemetryIn(BaseModel):
    robot_id: str
    secret_key: str
    speed: float
    battery: float
    latitude: float
    longitude: float
    motor_temp: Optional[float] = None
    current: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    yaw: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class CommandIn(BaseModel):
    robot_id: str
    secret_key: str
    command: str


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    robot_id: str
    timestamp: datetime
    speed: float
    battery: float
    latitude: float
    longitude: float
    motor_temp: Optional[float]
    current: Optional[float]
    pitch: Optional[float]
    roll: Optional[float]
    yaw: Optional[float]
    extra: Optional[str]


app = FastAPI(title="ACE Recruitment Fleet API", version="1.0.0")

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_by_robot: Dict[str, Dict[str, Any]] = {}
recent_commands: List[Dict[str, Any]] = []
demo_task: Optional[asyncio.Task] = None


class MotorReading(BaseModel):
    current: float
    rpm: Optional[float] = None
    temperature: float
    vibration: Optional[float] = None


class MotorPredictIn(BaseModel):
    robot_id: str
    secret_key: str
    history: List[MotorReading] = Field(default_factory=list)


class NLPParseIn(BaseModel):
    text: str


class AICommandIn(BaseModel):
    robot_id: str
    secret_key: str
    command: str


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def validate_handshake(robot_id: str, secret_key: str) -> None:
    expected_key = VALID_ROBOT_CREDENTIALS.get(robot_id)
    if expected_key is None or expected_key != secret_key:
        raise HTTPException(status_code=401, detail="Unauthorized robot credentials")


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def parse_command(command_text: str) -> Dict[str, Any]:
    parts = command_text.strip().split()
    if not parts:
        return {"raw": command_text, "action": "", "args": []}
    return {
        "raw": command_text,
        "action": parts[0],
        "args": parts[1:],
    }


def safe_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return json.dumps({"raw": str(value)})


def safe_loads(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {"value": loaded}
    except (TypeError, ValueError):
        return {}


class MotorInferenceService:
    def __init__(self) -> None:
        self.enabled = bool(motor_predictor and np is not None and torch is not None)
        self.model = None
        self.scaler_mean = None
        self.scaler_scale = None
        self.seq_len = 30
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        if not self.enabled:
            return
        try:
            base_dir = os.path.join("ai_ml", "module2")
            model_path = os.path.join(base_dir, "motor_lstm.pt")
            mean_path = os.path.join(base_dir, "scaler_mean.npy")
            scale_path = os.path.join(base_dir, "scaler_scale.npy")
            if not (os.path.exists(model_path) and os.path.exists(mean_path) and os.path.exists(scale_path)):
                return

            self.model = motor_predictor.LSTMRegressor()
            state = torch.load(model_path, map_location="cpu")
            self.model.load_state_dict(state)
            self.model.eval()

            self.scaler_mean = np.load(mean_path)
            self.scaler_scale = np.load(scale_path)
        except Exception:
            self.model = None
            self.scaler_mean = None
            self.scaler_scale = None

    def _heuristic(self, row: List[float]) -> float:
        current, rpm, temp, vibration = row
        current_risk = min(1.0, max(0.0, (current - 18.0) / 10.0))
        temp_risk = min(1.0, max(0.0, (temp - 70.0) / 25.0))
        vibration_risk = min(1.0, max(0.0, (vibration - 0.18) / 0.25))
        rpm_drop_risk = min(1.0, max(0.0, (2800.0 - rpm) / 1200.0))
        score = 0.3 * current_risk + 0.35 * temp_risk + 0.25 * vibration_risk + 0.1 * rpm_drop_risk
        return float(min(1.0, max(0.0, score)))

    def predict(self, rows: List[List[float]]) -> float:
        if not rows:
            return 0.0
        rows = rows[-self.seq_len :]
        while len(rows) < self.seq_len:
            rows.insert(0, rows[0])

        if self.model is not None and self.scaler_mean is not None and self.scaler_scale is not None:
            try:
                arr = np.array(rows, dtype=np.float32)
                denom = np.where(self.scaler_scale == 0, 1.0, self.scaler_scale)
                arr = (arr - self.scaler_mean) / denom
                x = torch.tensor(arr[None, :, :], dtype=torch.float32)
                with torch.no_grad():
                    return float(self.model(x).item())
            except Exception:
                pass

        return self._heuristic(rows[-1])


motor_service = MotorInferenceService()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        disconnected: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


async def broadcast_snapshot() -> None:
    await manager.broadcast(
        {
            "type": "snapshot",
            "timestamp": now_iso(),
            "robots": latest_by_robot,
            "commands": recent_commands[-50:],
        }
    )


@app.post("/telemetry")
async def post_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    validate_handshake(payload.robot_id, payload.secret_key)

    row = Telemetry(
        robot_id=payload.robot_id,
        timestamp=now_utc(),
        speed=payload.speed,
        battery=payload.battery,
        latitude=payload.latitude,
        longitude=payload.longitude,
        motor_temp=payload.motor_temp,
        current=payload.current,
        pitch=payload.pitch,
        roll=payload.roll,
        yaw=payload.yaw,
        extra=safe_json(payload.extra) if payload.extra else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    latest_payload = {
        "id": row.id,
        "robot_id": row.robot_id,
        "timestamp": row.timestamp.isoformat(),
        "speed": row.speed,
        "battery": row.battery,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "motor_temp": row.motor_temp,
        "current": row.current,
        "pitch": row.pitch,
        "roll": row.roll,
        "yaw": row.yaw,
    }
    latest_by_robot[row.robot_id] = latest_payload

    await manager.broadcast(
        {
            "type": "telemetry",
            "timestamp": now_iso(),
            "telemetry": latest_payload,
            "robots": latest_by_robot,
        }
    )

    return {"status": "ok", "telemetry_id": row.id, "robot_id": row.robot_id}


@app.get("/telemetry/{robot_id}", response_model=List[TelemetryOut])
async def get_telemetry(
    robot_id: str,
    limit: int = Query(default=100, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> List[TelemetryOut]:
    rows = (
        db.query(Telemetry)
        .filter(Telemetry.robot_id == robot_id)
        .order_by(desc(Telemetry.timestamp))
        .limit(limit)
        .all()
    )
    return rows


@app.get("/distance/{robot_id}")
async def get_distance(robot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    cutoff = now_utc() - timedelta(hours=24)
    points = (
        db.query(Telemetry)
        .filter(Telemetry.robot_id == robot_id, Telemetry.timestamp >= cutoff)
        .order_by(Telemetry.timestamp.asc())
        .all()
    )

    total_meters = 0.0
    for i in range(1, len(points)):
        p1 = points[i - 1]
        p2 = points[i]
        total_meters += haversine_meters(p1.latitude, p1.longitude, p2.latitude, p2.longitude)

    return {
        "status": "ok",
        "robot_id": robot_id,
        "distance_meters": round(total_meters, 3),
        "distance_km": round(total_meters / 1000.0, 6),
        "gps_points_used": len(points),
        "period_hours": 24,
    }


@app.post("/command")
async def post_command(payload: CommandIn) -> Dict[str, Any]:
    validate_handshake(payload.robot_id, payload.secret_key)

    parsed = parse_command(payload.command)
    nlp_result = nlp_parser.parse_transcript(payload.command) if nlp_parser else {
        "issues": [],
        "directives": [],
        "overall_status": "SAFE",
        "mode": "disabled",
    }
    command_event = {
        "type": "command",
        "timestamp": now_iso(),
        "robot_id": payload.robot_id,
        "command": payload.command,
        "parsed": parsed,
        "nlp": nlp_result,
    }
    recent_commands.append(command_event)
    if len(recent_commands) > 500:
        del recent_commands[:-500]

    await manager.broadcast(command_event)
    await broadcast_snapshot()
    return {"status": "queued", **command_event}


def _rows_from_db(db: Session, robot_id: str, limit: int = 60) -> List[List[float]]:
    rows = (
        db.query(Telemetry)
        .filter(Telemetry.robot_id == robot_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()

    out: List[List[float]] = []
    for r in rows:
        extra = safe_loads(r.extra)
        rpm = extra.get("rpm", max(900.0, float(r.speed) * 220.0))
        vibration = extra.get("vibration", (abs(r.pitch or 0.0) + abs(r.roll or 0.0)) / 100.0)
        out.append([
            float(r.current or 0.0),
            float(rpm),
            float(r.motor_temp or 0.0),
            float(vibration),
        ])
    return out


def _rows_from_payload(history: List[MotorReading]) -> List[List[float]]:
    out: List[List[float]] = []
    for row in history:
        rpm = row.rpm if row.rpm is not None else 2400.0
        vibration = row.vibration if row.vibration is not None else 0.12
        out.append([float(row.current), float(rpm), float(row.temperature), float(vibration)])
    return out


def _risk_label(prob: float) -> str:
    if prob >= 0.8:
        return "critical"
    if prob >= 0.6:
        return "high"
    if prob >= 0.35:
        return "medium"
    return "low"


@app.post("/ai/predict/motor")
async def ai_predict_motor(payload: MotorPredictIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    validate_handshake(payload.robot_id, payload.secret_key)

    rows = _rows_from_payload(payload.history) if payload.history else _rows_from_db(db, payload.robot_id)
    if not rows:
        raise HTTPException(status_code=400, detail="No telemetry available for motor prediction")

    probability = motor_service.predict(rows)
    risk = _risk_label(probability)
    response = {
        "status": "ok",
        "robot_id": payload.robot_id,
        "failure_probability": round(probability, 4),
        "risk_level": risk,
        "samples_used": len(rows),
    }

    insight_event = {
        "type": "ai_insight",
        "timestamp": now_iso(),
        "robot_id": payload.robot_id,
        "insight": {
            "source": "motor_predictor",
            "severity": "danger" if probability >= 0.8 else "warning" if probability >= 0.35 else "info",
            "message": f"Predicted failure probability {probability * 100:.1f}% ({risk}).",
        },
    }
    await manager.broadcast(insight_event)
    return response


@app.post("/ai/parse-command")
async def ai_parse_command(payload: NLPParseIn) -> Dict[str, Any]:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Command text cannot be empty")

    if nlp_parser:
        parsed = nlp_parser.parse_transcript(payload.text)
    else:
        parsed = {
            "issues": [],
            "directives": [],
            "overall_status": "SAFE",
            "mode": "disabled",
        }

    return {
        "status": "ok",
        "text": payload.text,
        "parsed": parsed,
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "ace-backend",
        "timestamp": now_iso(),
        "modules": {
            "nlp": nlp_parser is not None,
            "motor_predictor": motor_service.enabled,
            "motor_model_loaded": motor_service.model is not None,
        },
    }


@app.get("/robots")
async def get_robots(db: Session = Depends(get_db)) -> Dict[str, Any]:
    latest_ts_subquery = db.query(Telemetry.robot_id, func.max(Telemetry.timestamp).label("max_ts")).group_by(Telemetry.robot_id).subquery()
    rows = (
        db.query(Telemetry)
        .join(
            latest_ts_subquery,
            (Telemetry.robot_id == latest_ts_subquery.c.robot_id)
            & (Telemetry.timestamp == latest_ts_subquery.c.max_ts),
        )
        .order_by(Telemetry.robot_id.asc())
        .all()
    )

    robots = [
        {
            "robot_id": r.robot_id,
            "timestamp": r.timestamp.isoformat(),
            "battery": r.battery,
            "speed": r.speed,
        }
        for r in rows
    ]
    return {"status": "ok", "count": len(robots), "robots": robots}


async def demo_loop() -> None:
    robot_id = "rover-cam-01"
    secret_key = VALID_ROBOT_CREDENTIALS[robot_id]
    lat = 12.9716
    lon = 77.5946
    t = 0

    while True:
        t += 1
        speed = 14 + 8 * math.sin(t / 9.0)
        battery = max(12.0, 100 - t * 0.025)
        motor_temp = 44 + 6 * math.sin(t / 17.0) + random.uniform(-0.5, 0.5)
        current = 8 + 2 * abs(math.sin(t / 8.0))
        pitch = 4 * math.sin(t / 13.0)
        roll = 5 * math.sin(t / 15.0)
        yaw = (t * 2.4) % 360
        lat += random.uniform(-0.00005, 0.00005)
        lon += random.uniform(-0.00005, 0.00005)

        payload = TelemetryIn(
            robot_id=robot_id,
            secret_key=secret_key,
            speed=round(speed, 2),
            battery=round(battery, 2),
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            motor_temp=round(motor_temp, 2),
            current=round(current, 2),
            pitch=round(pitch, 2),
            roll=round(roll, 2),
            yaw=round(yaw, 2),
            extra={"source": "demo"},
        )

        db = SessionLocal()
        try:
            await post_telemetry(payload, db)
        finally:
            db.close()

        await asyncio.sleep(0.1)


@app.get("/demo/start")
async def demo_start() -> Dict[str, str]:
    global demo_task
    if demo_task is None or demo_task.done():
        demo_task = asyncio.create_task(demo_loop())
        return {"status": "started"}
    return {"status": "already_running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await broadcast_snapshot()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
                continue

            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": now_iso()})
                continue

            if payload.get("type") == "command":
                robot_id = str(payload.get("robot_id", "")).strip()
                secret_key = str(payload.get("secret_key", "")).strip()
                command = str(payload.get("command", "")).strip()
                if not robot_id or not secret_key or not command:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Command requires robot_id, secret_key, and command",
                        }
                    )
                    continue

                try:
                    validate_handshake(robot_id, secret_key)
                    command_result = await post_command(
                        CommandIn(robot_id=robot_id, secret_key=secret_key, command=command)
                    )
                    await websocket.send_json({"type": "ack", "event": command_result})
                except HTTPException:
                    await websocket.send_json({"type": "error", "message": "Unauthorized command"})
                continue

            await websocket.send_json({"type": "error", "message": "Unsupported websocket message type"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


"""
Docker deployment strategy for edge server or local ground station:

1) Build once:
   docker build -t ace-fleet-backend .

2) Run with persistent DB volume and port mapping:
   docker run -d \
     -p 8000:8000 \
     -v ace_data:/app/data \
     --name ace-fleet-backend \
     ace-fleet-backend

3) Why this works for edge deployments:
   - The backend and all dependencies are packaged into one image.
   - SQLite database persists in /app/data through the named volume.
   - Updating is simple: rebuild or pull image, then restart container.
   - For PostgreSQL in production, set DATABASE_URL to a Postgres URI.

4) Recommended production hardening:
   - Use a reverse proxy (nginx/traefik) and HTTPS.
   - Restrict CORS to known frontend origins.
   - Move robot credentials to env vars or secret manager.
"""
