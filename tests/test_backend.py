from datetime import datetime, timedelta, timezone

import pytest

try:
    import backend.main as backend_main
except Exception:
    backend_main = None


pytestmark = pytest.mark.skipif(backend_main is None, reason="Backend module not available")


class TestHandshakeAuth:
    def test_valid_credentials_accepted(self, client, valid_telemetry_payload):
        response = client.post("/telemetry", json=valid_telemetry_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_wrong_secret_key_rejected(self, client, valid_telemetry_payload):
        payload = dict(valid_telemetry_payload)
        payload["secret_key"] = "wrong-key"
        response = client.post("/telemetry", json=payload)
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]

    def test_unknown_robot_id_rejected(self, client, valid_telemetry_payload):
        payload = dict(valid_telemetry_payload)
        payload["robot_id"] = "ghost-rover"
        payload["secret_key"] = "anything"
        response = client.post("/telemetry", json=payload)
        assert response.status_code == 401

    def test_command_endpoint_also_requires_auth(self, client):
        response = client.post(
            "/command",
            json={"robot_id": "rover-cam-01", "secret_key": "wrong", "command": "/stop"},
        )
        assert response.status_code == 401

    def test_second_robot_credentials_valid(self, client, valid_telemetry_payload):
        payload = dict(valid_telemetry_payload)
        payload["robot_id"] = "rover-arm-02"
        payload["secret_key"] = "ace-secret-key-456"
        response = client.post("/telemetry", json=payload)
        assert response.status_code == 200


class TestTelemetryIngestion:
    def test_telemetry_stored_in_db(self, client, valid_telemetry_payload):
        post = client.post("/telemetry", json=valid_telemetry_payload)
        assert post.status_code == 200

        data = client.get("/telemetry/rover-cam-01").json()
        assert len(data) >= 1
        assert data[0]["speed"] == valid_telemetry_payload["speed"]
        assert data[0]["battery"] == valid_telemetry_payload["battery"]
        assert data[0]["latitude"] == valid_telemetry_payload["latitude"]
        assert data[0]["longitude"] == valid_telemetry_payload["longitude"]

    def test_telemetry_returns_latest_first(self, client, valid_telemetry_payload):
        for speed in [10.0, 20.0, 30.0]:
            payload = dict(valid_telemetry_payload)
            payload["speed"] = speed
            response = client.post("/telemetry", json=payload)
            assert response.status_code == 200

        data = client.get("/telemetry/rover-cam-01").json()
        assert data[0]["speed"] == 30.0

    def test_telemetry_limit_param_respected(self, client, valid_telemetry_payload):
        for i in range(10):
            payload = dict(valid_telemetry_payload)
            payload["speed"] = float(i)
            response = client.post("/telemetry", json=payload)
            assert response.status_code == 200

        data = client.get("/telemetry/rover-cam-01?limit=3").json()
        assert len(data) == 3

    def test_all_fields_persisted(self, client, valid_telemetry_payload):
        payload = dict(valid_telemetry_payload)
        payload.update({"motor_temp": 75.5, "current": 12.3, "pitch": 5.1, "roll": 3.2, "yaw": 180.0})
        response = client.post("/telemetry", json=payload)
        assert response.status_code == 200

        row = client.get("/telemetry/rover-cam-01?limit=1").json()[0]
        assert row["motor_temp"] == 75.5
        assert row["current"] == 12.3
        assert row["pitch"] == 5.1
        assert row["roll"] == 3.2
        assert row["yaw"] == 180.0

    def test_optional_fields_nullable(self, client, valid_telemetry_payload):
        payload = {
            "robot_id": valid_telemetry_payload["robot_id"],
            "secret_key": valid_telemetry_payload["secret_key"],
            "speed": valid_telemetry_payload["speed"],
            "battery": valid_telemetry_payload["battery"],
            "latitude": valid_telemetry_payload["latitude"],
            "longitude": valid_telemetry_payload["longitude"],
        }
        response = client.post("/telemetry", json=payload)
        assert response.status_code == 200

    def test_unknown_robot_returns_empty_list(self, client):
        response = client.get("/telemetry/nonexistent-robot")
        assert response.status_code == 200
        assert response.json() == []


class TestDistanceCalculation:
    def test_zero_distance_single_point(self, client, post_telemetry):
        response = post_telemetry(12.9716, 77.5946)
        assert response.status_code == 200

        data = client.get("/distance/rover-cam-01").json()
        assert data["distance_meters"] == 0.0
        assert data["gps_points_used"] == 1

    def test_known_distance_two_points(self, client, post_telemetry):
        assert post_telemetry(12.9716, 77.5946).status_code == 200
        assert post_telemetry(12.9806, 77.5946).status_code == 200

        data = client.get("/distance/rover-cam-01").json()
        assert abs(data["distance_meters"] - 1001) < 50

    def test_distance_is_cumulative(self, client, post_telemetry):
        assert post_telemetry(12.9716, 77.5946).status_code == 200
        assert post_telemetry(12.9806, 77.5946).status_code == 200
        assert post_telemetry(12.9806, 77.6036).status_code == 200

        data = client.get("/distance/rover-cam-01").json()
        leg1 = backend_main.haversine_meters(12.9716, 77.5946, 12.9806, 77.5946)
        leg2 = backend_main.haversine_meters(12.9806, 77.5946, 12.9806, 77.6036)
        assert abs(data["distance_meters"] - (leg1 + leg2)) < 80

    def test_distance_response_schema(self, client, post_telemetry):
        assert post_telemetry(12.9716, 77.5946).status_code == 200
        data = client.get("/distance/rover-cam-01").json()
        keys = {"robot_id", "distance_meters", "distance_km", "gps_points_used", "period_hours"}
        assert keys.issubset(data.keys())
        assert data["period_hours"] == 24

    def test_distance_only_counts_last_24h(self, client, db_session, post_telemetry):
        old = backend_main.Telemetry(
            robot_id="rover-cam-01",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=25),
            speed=5.0,
            battery=80.0,
            latitude=12.90,
            longitude=77.50,
            motor_temp=None,
            current=None,
            pitch=None,
            roll=None,
            yaw=None,
            extra=None,
        )
        db_session.add(old)
        db_session.commit()

        assert post_telemetry(12.9716, 77.5946).status_code == 200
        data = client.get("/distance/rover-cam-01").json()
        assert data["gps_points_used"] == 1

    def test_distance_km_equals_meters_divided_by_1000(self, client, post_telemetry):
        assert post_telemetry(12.9716, 77.5946).status_code == 200
        assert post_telemetry(12.9806, 77.5946).status_code == 200

        data = client.get("/distance/rover-cam-01").json()
        assert abs(data["distance_km"] - (data["distance_meters"] / 1000.0)) < 0.0001


class TestCommandEndpoint:
    def test_command_accepted_and_parsed(self, client):
        response = client.post(
            "/command",
            json={"robot_id": "rover-cam-01", "secret_key": "ace-secret-key-123", "command": "/move_forward 50"},
        )
        data = response.json()
        assert response.status_code == 200
        assert data["parsed"]["action"] == "/move_forward"
        assert data["parsed"]["args"] == ["50"]

    def test_stop_command(self, client):
        response = client.post(
            "/command",
            json={"robot_id": "rover-cam-01", "secret_key": "ace-secret-key-123", "command": "/stop"},
        )
        data = response.json()
        assert response.status_code == 200
        assert data["parsed"]["action"] == "/stop"
        assert data["parsed"]["args"] == []

    def test_command_response_contains_timestamp(self, client):
        response = client.post(
            "/command",
            json={"robot_id": "rover-cam-01", "secret_key": "ace-secret-key-123", "command": "/help"},
        )
        data = response.json()
        assert response.status_code == 200
        assert "timestamp" in data
        assert data["timestamp"] is not None

    def test_command_requires_auth(self, client):
        response = client.post(
            "/command",
            json={"robot_id": "rover-cam-01", "secret_key": "invalid", "command": "/help"},
        )
        assert response.status_code == 401


class TestRobotsEndpoint:
    def test_empty_fleet_returns_zero(self, client):
        response = client.get("/robots")
        data = response.json()
        assert data["count"] == 0
        assert data["robots"] == []

    def test_robot_appears_after_telemetry(self, client, valid_telemetry_payload):
        assert client.post("/telemetry", json=valid_telemetry_payload).status_code == 200
        data = client.get("/robots").json()
        assert data["count"] == 1
        assert data["robots"][0]["robot_id"] == "rover-cam-01"

    def test_two_robots_both_listed(self, client, valid_telemetry_payload):
        assert client.post("/telemetry", json=valid_telemetry_payload).status_code == 200

        payload2 = dict(valid_telemetry_payload)
        payload2["robot_id"] = "rover-arm-02"
        payload2["secret_key"] = "ace-secret-key-456"
        payload2["latitude"] = 12.98
        payload2["longitude"] = 77.60
        assert client.post("/telemetry", json=payload2).status_code == 200

        data = client.get("/robots").json()
        assert data["count"] == 2

    def test_robots_endpoint_returns_latest_battery(self, client, valid_telemetry_payload):
        payload1 = dict(valid_telemetry_payload)
        payload1["battery"] = 90.0
        payload2 = dict(valid_telemetry_payload)
        payload2["battery"] = 40.0

        assert client.post("/telemetry", json=payload1).status_code == 200
        assert client.post("/telemetry", json=payload2).status_code == 200

        data = client.get("/robots").json()
        assert data["robots"][0]["battery"] == 40.0


class TestWebSocket:
    def test_websocket_connects_successfully(self, client):
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"

    def test_websocket_receives_snapshot_on_connect(self, client):
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert "robots" in msg
            assert "commands" in msg

    def test_websocket_receives_telemetry_broadcast(self, client, valid_telemetry_payload):
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()
            response = client.post("/telemetry", json=valid_telemetry_payload)
            assert response.status_code == 200

            found = None
            for _ in range(3):
                msg = ws.receive_json()
                if msg.get("type") == "telemetry":
                    found = msg
                    break
            assert found is not None
            assert found["telemetry"]["robot_id"] == "rover-cam-01"

    def test_websocket_receives_command_broadcast(self, client):
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()
            response = client.post(
                "/command",
                json={"robot_id": "rover-cam-01", "secret_key": "ace-secret-key-123", "command": "/move_forward 50"},
            )
            assert response.status_code == 200

            found = None
            for _ in range(5):
                msg = ws.receive_json()
                if msg.get("type") == "command":
                    found = msg
                    break
            assert found is not None
            assert found["command"] == "/move_forward 50"


class TestDemoEndpoint:
    def test_demo_start_returns_started(self, client):
        response = client.get("/demo/start")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_demo_start_idempotent(self, client):
        first = client.get("/demo/start")
        second = client.get("/demo/start")
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["status"] == "already_running"


class TestHaversineUnit:
    def test_same_point_is_zero(self):
        result = backend_main.haversine_meters(12.9716, 77.5946, 12.9716, 77.5946)
        assert result == 0.0

    def test_known_1km_distance(self):
        result = backend_main.haversine_meters(0.0, 0.0, 0.009, 0.0)
        assert abs(result - 1001) < 10

    def test_symmetry(self):
        d1 = backend_main.haversine_meters(12.90, 77.50, 12.99, 77.60)
        d2 = backend_main.haversine_meters(12.99, 77.60, 12.90, 77.50)
        assert abs(d1 - d2) < 1e-6
