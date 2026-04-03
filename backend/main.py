from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime, timedelta, timezone
import asyncio
import math
import random

app = FastAPI(title="ACE Mission Control", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "ace-secret-key-123"
telemetry_latest: Dict[str, dict] = {}
telemetry_history: Dict[str, List[dict]] = {}
commands: List[dict] = []
demo_task = None


class TelemetryIn(BaseModel):
    robot_id: str
    secret_key: str
    speed: float = 0.0
    battery: float = 100.0
    temperature: float = 25.0
    current: float = 5.0
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0
    latitude: float
    longitude: float


class CommandIn(BaseModel):
    robot_id: str
    secret_key: str
    command: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def validate_secret(secret_key: str) -> None:
    if secret_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid secret key")


@app.post("/telemetry")
async def post_telemetry(payload: TelemetryIn):
    validate_secret(payload.secret_key)
    item = payload.dict()
    item["timestamp"] = now_iso()
    telemetry_latest[payload.robot_id] = item
    telemetry_history.setdefault(payload.robot_id, []).append(item)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    telemetry_history[payload.robot_id] = [
        x for x in telemetry_history[payload.robot_id] if datetime.fromisoformat(x["timestamp"]) >= cutoff
    ]
    return {"status": "ok", "robot_id": payload.robot_id, "timestamp": item["timestamp"]}


@app.get("/telemetry/{robot_id}")
async def get_telemetry(robot_id: str):
    data = telemetry_latest.get(robot_id)
    if not data:
        raise HTTPException(status_code=404, detail="Robot not found")
    return data


@app.get("/distance/{robot_id}")
async def get_distance(robot_id: str):
    points = telemetry_history.get(robot_id, [])
    if len(points) < 2:
        return {"robot_id": robot_id, "distance_km_24h": 0.0}
    total = 0.0
    for i in range(1, len(points)):
        p1 = points[i - 1]
        p2 = points[i]
        total += haversine_km(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
    return {"robot_id": robot_id, "distance_km_24h": round(total, 4)}


@app.post("/command")
async def post_command(payload: CommandIn):
    validate_secret(payload.secret_key)
    item = {
        "robot_id": payload.robot_id,
        "command": payload.command,
        "timestamp": now_iso(),
    }
    commands.append(item)
    return {"status": "queued", **item}


@app.get("/robots")
async def get_robots():
    return {"robots": sorted(list(telemetry_latest.keys()))}


async def demo_stream_loop():
    robot_id = "rover-cam-01"
    lat = 12.9716
    lon = 77.5946
    t = 0
    while True:
        t += 1
        speed = 18 + 8 * math.sin(t / 10)
        battery = max(10, 100 - t * 0.03)
        temperature = 30 + 4 * math.sin(t / 15) + random.uniform(-0.5, 0.5)
        current = 6 + 2.5 * abs(math.sin(t / 7))
        pitch = 8 * math.sin(t / 18)
        roll = 10 * math.sin(t / 22)
        yaw = (t * 3) % 360
        lat += random.uniform(-0.00006, 0.00006)
        lon += random.uniform(-0.00006, 0.00006)
        data = {
            "robot_id": robot_id,
            "secret_key": SECRET_KEY,
            "speed": round(speed, 2),
            "battery": round(battery, 2),
            "temperature": round(temperature, 2),
            "current": round(current, 2),
            "pitch": round(pitch, 2),
            "roll": round(roll, 2),
            "yaw": round(yaw, 2),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        }
        await post_telemetry(TelemetryIn(**data))
        await asyncio.sleep(0.1)


@app.get("/demo/start")
async def start_demo():
    global demo_task
    if demo_task is None or demo_task.done():
        demo_task = asyncio.create_task(demo_stream_loop())
        return {"status": "started"}
    return {"status": "already_running"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(
                {
                    "timestamp": now_iso(),
                    "robots": telemetry_latest,
                    "commands": commands[-20:],
                }
            )
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
