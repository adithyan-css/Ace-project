import asyncio
import json
import logging
import math
import os
import random
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, Index, Integer, String, Text, create_engine, desc, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

try:
    load_dotenv = __import__("dotenv").load_dotenv
except Exception:
    load_dotenv = None

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

try:
    from ai_ml.module2 import strategy_optimizer
except Exception:
    strategy_optimizer = None

try:
    from ai_ml.module1 import vision_monitor
except Exception:
    vision_monitor = None

try:
    from backend.ai.inference import risk_label as ai_risk_label
    from backend.ai.inference import severity_from_risk, summarize_vision
    from backend.services.alert_rules import evaluate_telemetry_alerts
    from backend.websocket.streaming import build_telemetry_tick
except Exception:
    from ai.inference import risk_label as ai_risk_label
    from ai.inference import severity_from_risk, summarize_vision
    from services.alert_rules import evaluate_telemetry_alerts
    from websocket.streaming import build_telemetry_tick


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/telemetry.db")
if load_dotenv:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env", override=False)
    load_dotenv(base_dir.parent / ".env", override=False)
    DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

if DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

VALID_ROBOT_CREDENTIALS = {
    "rover-cam-01": "ace-secret-key-123",
    "rover-arm-02": "ace-secret-key-456",
}

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ace.backend")

def _make_engine(db_url: str):
    return create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    )


def _fallback_sqlite_url() -> str:
    return "sqlite:///./data/telemetry_fallback.db"


def _activate_sqlite_fallback(reason: str, exc: Optional[Exception] = None) -> None:
    global engine, SessionLocal, DATABASE_URL
    fallback_url = _fallback_sqlite_url()
    os.makedirs("data", exist_ok=True)
    if exc is not None:
        logger.error("Primary database initialization failed (%s): %s", reason, exc)
    logger.warning("Falling back to SQLite runtime DB: %s", fallback_url)
    DATABASE_URL = fallback_url
    engine = _make_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


try:
    engine = _make_engine(DATABASE_URL)
except ModuleNotFoundError as exc:
    if "psycopg" in str(exc).lower():
        logger.error("PostgreSQL driver missing. Install with: pip install psycopg[binary]")
        _activate_sqlite_fallback("missing_psycopg_driver", exc)
    else:
        raise
except Exception as exc:
    _activate_sqlite_fallback("engine_creation_error", exc)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        Index("ix_telemetry_robot_ts", "robot_id", "timestamp"),
    )

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telemetry_stream_task, demo_task

    logger.info("Backend startup: initializing with database %s", DATABASE_URL)
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        if DATABASE_URL.startswith("sqlite"):
            raise
        _activate_sqlite_fallback("database_connectivity_error", exc)
        Base.metadata.create_all(bind=engine)

    if telemetry_stream_task is None or telemetry_stream_task.done():
        telemetry_stream_task = asyncio.create_task(telemetry_stream_loop())

    artifacts_dir = Path(__file__).resolve().parent.parent / "ai_ml" / "module2"
    model_file = artifacts_dir / "motor_lstm.pt"
    if not model_file.exists():
        print("\n" + "=" * 72)
        print("⚠️  WARNING: motor_lstm.pt not found.")
        print("Motor predictions will use heuristic fallback.")
        print("Run: python ai_ml/module2/train_and_save.py")
        print("Then restart the backend.")
        print("=" * 72 + "\n")
    elif motor_service.model is not None:
        print("✅ Motor LSTM model loaded successfully")
    else:
        print("\n" + "=" * 72)
        print("⚠️  WARNING: motor_lstm.pt exists but could not be loaded.")
        print("Motor predictions will use heuristic fallback.")
        print("Run: python ai_ml/module2/train_and_save.py")
        print("Then restart the backend.")
        print("=" * 72 + "\n")

    try:
        yield
    finally:
        for task in [demo_task, telemetry_stream_task]:
            if task is not None and not task.done():
                task.cancel()

        for task in [demo_task, telemetry_stream_task]:
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.warning("Background task shutdown error: %s", exc)

        demo_task = None
        telemetry_stream_task = None
        engine.dispose()


app = FastAPI(title="ACE Recruitment Fleet API", version="1.0.0", lifespan=lifespan)

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
telemetry_stream_task: Optional[asyncio.Task] = None
active_alerts: List[Dict[str, Any]] = []
ai_insights: List[Dict[str, Any]] = []


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


class VisionObjectIn(BaseModel):
    id: Optional[str] = None
    x: float
    y: float


class VisionAnalyzeIn(BaseModel):
    robot_id: str
    secret_key: str
    objects: List[VisionObjectIn] = Field(default_factory=list)
    roi_polygon: List[List[float]] = Field(default_factory=list)


class StrategyOptimizeIn(BaseModel):
    tire_age: float
    track_temp: float
    fuel_load: float
    safety_car_probability: float = Field(default=0.1, ge=0.0, le=1.0)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def validate_handshake(robot_id: str, secret_key: str) -> None:
    expected_key = VALID_ROBOT_CREDENTIALS.get(robot_id)
    if expected_key is None or expected_key != secret_key:
        raise HTTPException(status_code=401, detail="Unauthorized robot credentials")


def validate_request_auth(
    robot_id: str,
    payload_secret_key: Optional[str],
    header_api_key: Optional[str],
    header_robot_id: Optional[str],
) -> None:
    normalized_header_robot_id = header_robot_id.strip() if isinstance(header_robot_id, str) else ""
    normalized_header_api_key = header_api_key.strip() if isinstance(header_api_key, str) else ""

    if normalized_header_robot_id and normalized_header_robot_id != robot_id:
        raise HTTPException(status_code=401, detail="Header robot id does not match payload robot id")

    effective_secret = normalized_header_api_key if normalized_header_api_key else payload_secret_key
    if not effective_secret:
        raise HTTPException(status_code=401, detail="Missing robot secret key")

    validate_handshake(robot_id, effective_secret)


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
    def __init__(self, manager_name: str) -> None:
        self.manager_name = manager_name
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            logger.warning("%s duplicate websocket connect ignored", self.manager_name)
            return
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("%s client connected. active=%d", self.manager_name, len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("%s client disconnected. active=%d", self.manager_name, len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        disconnected: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager("event_ws")
telemetry_manager = ConnectionManager("telemetry_ws")


async def telemetry_stream_loop() -> None:
    while True:
        message = build_telemetry_tick(latest_by_robot, active_alerts, ai_insights, recent_commands)
        await telemetry_manager.broadcast(message)
        await asyncio.sleep(0.1)


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
async def post_telemetry(
    payload: TelemetryIn,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    validate_request_auth(payload.robot_id, payload.secret_key, x_api_key, x_robot_id)

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
        "extra": safe_loads(row.extra),
    }
    latest_by_robot[row.robot_id] = latest_payload
    logger.debug("Telemetry stored id=%s robot=%s", row.id, row.robot_id)
    generated_alerts = evaluate_telemetry_alerts(row.robot_id, latest_payload)
    if generated_alerts:
        active_alerts.extend(generated_alerts)
        if len(active_alerts) > 500:
            del active_alerts[:-500]

    vision_objects = payload.extra.get("vision_objects") if isinstance(payload.extra, dict) else None
    if isinstance(vision_objects, list):
        polygon = payload.extra.get("roi_polygon") if isinstance(payload.extra.get("roi_polygon"), list) else [[120, 120], [560, 120], [620, 420], [140, 420]]
        inside_count = 0
        normalized_objects: List[Dict[str, float]] = []
        for item in vision_objects:
            if not isinstance(item, dict):
                continue
            if "x" not in item or "y" not in item:
                continue
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            normalized_objects.append({"x": x, "y": y})
            if vision_monitor:
                try:
                    if vision_monitor.point_inside_polygon(x, y, polygon):
                        inside_count += 1
                except Exception:
                    pass
        if normalized_objects:
            vision_summary = summarize_vision(normalized_objects, inside_count)
            vision_severity = "danger" if vision_summary["status"] == "critical" else "warning" if vision_summary["status"] == "warning" else "info"
            vision_insight = {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "type": "ai_insight",
                "timestamp": now_iso(),
                "robot_id": row.robot_id,
                "insight": {
                    "source": "vision_monitor",
                    "severity": vision_severity,
                    "message": f"Telemetry vision score {vision_summary['anomaly_score']} ({vision_summary['status']}).",
                },
            }
            ai_insights.append(vision_insight)
            if len(ai_insights) > 500:
                del ai_insights[:-500]
            await manager.broadcast(vision_insight)

    vision_boxes = payload.extra.get("vision_boxes") if isinstance(payload.extra, dict) else None
    if isinstance(vision_boxes, list):
        breach_count = sum(1 for item in vision_boxes if isinstance(item, dict) and bool(item.get("inside")))
        await manager.broadcast(
            {
                "type": "vision_detection",
                "timestamp": now_iso(),
                "robot_id": row.robot_id,
                "fps": payload.extra.get("fps") if isinstance(payload.extra, dict) else None,
                "breach": breach_count > 0,
                "breach_count": breach_count,
                "polygon": payload.extra.get("roi_polygon") if isinstance(payload.extra, dict) else None,
                "detections": vision_boxes,
            }
        )

    await manager.broadcast(
        {
            "type": "telemetry",
            "timestamp": now_iso(),
            "telemetry": latest_payload,
            "robots": latest_by_robot,
        }
    )

    for alert in generated_alerts:
        logger.info("Alert emitted robot=%s code=%s severity=%s", row.robot_id, alert.get("code"), alert.get("severity"))
        await manager.broadcast(alert)

    return {"status": "ok", "telemetry_id": row.id, "robot_id": row.robot_id}


@app.post("/api/telemetry")
async def api_post_telemetry(
    payload: TelemetryIn,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    return await post_telemetry(payload, db, x_api_key, x_robot_id)


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


@app.get("/api/telemetry/latest/{robot_id}")
async def get_latest_telemetry(robot_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    row = (
        db.query(Telemetry)
        .filter(Telemetry.robot_id == robot_id)
        .order_by(desc(Telemetry.timestamp))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No telemetry found for robot")

    return {
        "status": "ok",
        "telemetry": {
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
        },
    }


@app.get("/api/telemetry/latest")
async def get_latest_telemetry_all(
    robot_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if robot_id:
        return await get_latest_telemetry(robot_id, db)

    latest_ts_subquery = (
        db.query(Telemetry.robot_id, func.max(Telemetry.timestamp).label("max_ts"))
        .group_by(Telemetry.robot_id)
        .subquery()
    )
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

    latest = [
        {
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
        for row in rows
    ]
    return {"status": "ok", "count": len(latest), "telemetry": latest}


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


@app.get("/api/telemetry/distance")
async def api_get_distance(
    robot_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return await get_distance(robot_id, db)


@app.post("/command")
async def post_command(
    payload: CommandIn,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    validate_request_auth(payload.robot_id, payload.secret_key, x_api_key, x_robot_id)

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
        "execution": {
            "status": "accepted",
            "action": parsed.get("action", ""),
            "confidence": 0.9 if nlp_result.get("mode") == "openai" else 0.75,
        },
    }
    logger.info("Command received robot=%s cmd=%s", payload.robot_id, payload.command)
    recent_commands.append(command_event)
    if len(recent_commands) > 500:
        del recent_commands[:-500]

    if nlp_result:
        insight = {
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "type": "ai_insight",
            "timestamp": now_iso(),
            "robot_id": payload.robot_id,
            "insight": {
                "source": "nlp_parser",
                "severity": severity_from_risk(nlp_result.get("overall_status", "low")),
                "message": f"NLP overall status: {nlp_result.get('overall_status', 'SAFE')}",
            },
        }
        ai_insights.append(insight)
        if len(ai_insights) > 500:
            del ai_insights[:-500]
        await manager.broadcast(insight)

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
    return ai_risk_label(prob)


@app.post("/ai/predict/motor")
async def ai_predict_motor(
    payload: MotorPredictIn,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    validate_request_auth(payload.robot_id, payload.secret_key, x_api_key, x_robot_id)

    rows = _rows_from_payload(payload.history) if payload.history else _rows_from_db(db, payload.robot_id)
    if not rows:
        raise HTTPException(status_code=400, detail="No telemetry available for motor prediction")

    probability = motor_service.predict(rows)
    risk = _risk_label(probability)
    logger.info("Motor prediction robot=%s risk=%s prob=%.4f", payload.robot_id, risk, probability)
    response = {
        "status": "ok",
        "robot_id": payload.robot_id,
        "failure_probability": round(probability, 4),
        "risk_level": risk,
        "classification": "impending_failure" if probability >= 0.5 else "normal",
        "warning": "Impending failure predicted within horizon" if probability >= 0.5 else "No immediate failure predicted",
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
    ai_insights.append(insight_event)
    if len(ai_insights) > 500:
        del ai_insights[:-500]
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

    logger.info("NLP parse triggered text_len=%d status=%s", len(payload.text), parsed.get("overall_status", "SAFE"))

    return {
        "status": "ok",
        "text": payload.text,
        "parsed": parsed,
    }


@app.post("/api/ai/motor-predict")
async def api_motor_predict(
    payload: MotorPredictIn,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    return await ai_predict_motor(payload, db, x_api_key, x_robot_id)


@app.post("/api/ai/nlp-parse")
async def api_nlp_parse(payload: NLPParseIn) -> Dict[str, Any]:
    return await ai_parse_command(payload)


@app.post("/api/command")
async def api_command(
    payload: CommandIn,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    return await post_command(payload, x_api_key, x_robot_id)


@app.post("/api/ai/vision-analyze")
async def api_vision_analyze(
    payload: VisionAnalyzeIn,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_robot_id: Optional[str] = Header(default=None, alias="X-Robot-Id"),
) -> Dict[str, Any]:
    validate_request_auth(payload.robot_id, payload.secret_key, x_api_key, x_robot_id)

    polygon = payload.roi_polygon
    if not polygon:
        polygon = [[120, 120], [560, 120], [620, 420], [140, 420]]

    inside_count = 0
    for obj in payload.objects:
        if vision_monitor:
            try:
                if vision_monitor.point_inside_polygon(obj.x, obj.y, polygon):
                    inside_count += 1
            except Exception:
                pass
        else:
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            if min(xs) <= obj.x <= max(xs) and min(ys) <= obj.y <= max(ys):
                inside_count += 1

    summary = summarize_vision([o.model_dump() for o in payload.objects], inside_count)
    logger.info(
        "Vision analyze robot=%s objects=%d inside=%d status=%s",
        payload.robot_id,
        len(payload.objects),
        inside_count,
        summary["status"],
    )
    severity = "danger" if summary["status"] == "critical" else "warning" if summary["status"] == "warning" else "info"
    insight = {
        "id": int(datetime.now(timezone.utc).timestamp() * 1000),
        "type": "ai_insight",
        "timestamp": now_iso(),
        "robot_id": payload.robot_id,
        "insight": {
            "source": "vision_monitor",
            "severity": severity,
            "message": f"Vision anomaly score {summary['anomaly_score']} ({summary['status']}).",
        },
    }
    ai_insights.append(insight)
    if len(ai_insights) > 500:
        del ai_insights[:-500]
    await manager.broadcast(insight)

    return {
        "status": "ok",
        "robot_id": payload.robot_id,
        **summary,
    }


@app.post("/api/ai/strategy-optimize")
async def api_strategy_optimize(payload: StrategyOptimizeIn) -> Dict[str, Any]:
    if strategy_optimizer is None:
        raise HTTPException(status_code=503, detail="Strategy optimizer module unavailable")

    result = strategy_optimizer.optimize_strategy(payload.model_dump())
    logger.info(
        "Strategy optimize triggered tire_age=%.2f temp=%.2f fuel=%.2f pit_lap=%s",
        payload.tire_age,
        payload.track_temp,
        payload.fuel_load,
        result.get("best_strategy", {}).get("pit_lap"),
    )
    insight = {
        "id": int(datetime.now(timezone.utc).timestamp() * 1000),
        "type": "ai_insight",
        "timestamp": now_iso(),
        "robot_id": "fleet-strategy",
        "insight": {
            "source": "strategy_optimizer",
            "severity": "info",
            "message": f"Best pit lap {result['best_strategy']['pit_lap']} with expected time {result['best_strategy']['expected_race_time']}s",
        },
    }
    ai_insights.append(insight)
    if len(ai_insights) > 500:
        del ai_insights[:-500]
    await manager.broadcast(insight)
    return result


@app.post("/api/strategy/optimize")
async def api_strategy_optimize_alias(payload: StrategyOptimizeIn) -> Dict[str, Any]:
    return await api_strategy_optimize(payload)


@app.get("/health")
async def health() -> Dict[str, Any]:
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "timestamp": now_iso(),
        "database": db_status,
        "motor_model_loaded": motor_service.model is not None,
        "nlp_parser_available": nlp_parser is not None,
        "active_websocket_connections": len(manager.active_connections) + len(telemetry_manager.active_connections),
        "demo_running": bool(demo_task is not None and not demo_task.done()),
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
        except Exception as exc:
            print(f"Demo loop stopped due to error: {exc}")
            break
        finally:
            db.close()

        await asyncio.sleep(0.1)


@app.get("/demo/start")
async def demo_start() -> Dict[str, str]:
    global demo_task
    Base.metadata.create_all(bind=engine)
    if demo_task is None or demo_task.done():
        demo_task = asyncio.create_task(demo_loop())
        logger.info("Demo loop started")
        return {"status": "started"}
    return {"status": "already_running"}


@app.get("/demo/stop")
async def demo_stop() -> Dict[str, str]:
    global demo_task
    if demo_task is not None and not demo_task.done():
        demo_task.cancel()
        demo_task = None
        logger.info("Demo loop stopped")
        return {"status": "stopped"}
    demo_task = None
    return {"status": "not_running"}


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


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket) -> None:
    await telemetry_manager.connect(websocket)
    await websocket.send_json(build_telemetry_tick(latest_by_robot, active_alerts, ai_insights, recent_commands))
    try:
        while True:
            raw = await websocket.receive_text()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
                continue

            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": now_iso()})
    except WebSocketDisconnect:
        telemetry_manager.disconnect(websocket)
    except Exception:
        telemetry_manager.disconnect(websocket)


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
