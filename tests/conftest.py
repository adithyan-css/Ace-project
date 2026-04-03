import os
from datetime import datetime, timedelta, timezone

import pytest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
except Exception:
    create_engine = None
    sessionmaker = None
    StaticPool = None


os.environ["DATABASE_URL"] = "sqlite://"


@pytest.fixture(scope="function")
def client(monkeypatch):
    if TestClient is None or create_engine is None:
        pytest.skip("Backend test dependencies are not available")

    import backend.main as backend_main

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    backend_main.engine = engine
    backend_main.SessionLocal = TestingSessionLocal
    backend_main.Base.metadata.drop_all(bind=engine)
    backend_main.Base.metadata.create_all(bind=engine)
    backend_main.latest_by_robot.clear()
    backend_main.recent_commands.clear()
    backend_main.demo_task = None

    with TestClient(backend_main.app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session():
    if create_engine is None:
        pytest.skip("SQLAlchemy is not available")

    import backend.main as backend_main

    session = backend_main.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def valid_telemetry_payload():
    return {
        "robot_id": "rover-cam-01",
        "secret_key": "ace-secret-key-123",
        "speed": 12.5,
        "battery": 85.0,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "motor_temp": 45.0,
        "current": 8.0,
        "pitch": 1.0,
        "roll": 0.5,
        "yaw": 15.0,
    }


@pytest.fixture(scope="function")
def tmp_log_path(tmp_path, monkeypatch):
    try:
        import ai_ml.module1.vision_monitor as vm
    except Exception:
        pytest.skip("Vision monitor module not available")

    temp_log = tmp_path / "breach_log.jsonl"
    monkeypatch.setattr(vm, "log_path", str(temp_log))
    return temp_log


@pytest.fixture(scope="function")
def post_telemetry(client, valid_telemetry_payload):
    def _post(lat, lon, **kwargs):
        payload = dict(valid_telemetry_payload)
        payload["latitude"] = float(lat)
        payload["longitude"] = float(lon)
        payload.update(kwargs)
        return client.post("/telemetry", json=payload)

    return _post
