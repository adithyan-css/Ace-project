import asyncio
import json
import math
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, desc, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_by_robot: Dict[str, Dict[str, Any]] = {}
recent_commands: List[Dict[str, Any]] = []
demo_task: Optional[asyncio.Task] = None


def get_db() -> Session:
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
        extra=json.dumps(payload.extra) if payload.extra else None,
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
    command_event = {
        "type": "command",
        "timestamp": now_iso(),
        "robot_id": payload.robot_id,
        "command": payload.command,
        "parsed": parsed,
    }
    recent_commands.append(command_event)
    if len(recent_commands) > 500:
        del recent_commands[:-500]

    await manager.broadcast(command_event)
    await broadcast_snapshot()
    return {"status": "queued", **command_event}


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
    return {"count": len(robots), "robots": robots}


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
            await websocket.receive_text()
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
