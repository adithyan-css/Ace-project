from datetime import datetime, timezone
from typing import Any, Dict, List


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_telemetry_alerts(robot_id: str, telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    battery = float(telemetry.get("battery") or 0.0)
    temp = float(telemetry.get("motor_temp") or 0.0)
    current = float(telemetry.get("current") or 0.0)
    pitch = abs(float(telemetry.get("pitch") or 0.0))
    roll = abs(float(telemetry.get("roll") or 0.0))

    if battery > 0 and battery < 20:
        alerts.append(
            {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "type": "alert",
                "robot_id": robot_id,
                "severity": "danger",
                "message": f"Low battery: {battery:.1f}%",
                "timestamp": _iso_now(),
                "code": "LOW_BATTERY",
            }
        )

    if temp >= 80:
        alerts.append(
            {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000) + 1,
                "type": "alert",
                "robot_id": robot_id,
                "severity": "danger",
                "message": f"High motor temperature: {temp:.1f}C",
                "timestamp": _iso_now(),
                "code": "HIGH_TEMP",
            }
        )
    elif temp >= 68:
        alerts.append(
            {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000) + 2,
                "type": "alert",
                "robot_id": robot_id,
                "severity": "warning",
                "message": f"Rising motor temperature: {temp:.1f}C",
                "timestamp": _iso_now(),
                "code": "RISING_TEMP",
            }
        )

    if current >= 18:
        alerts.append(
            {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000) + 3,
                "type": "alert",
                "robot_id": robot_id,
                "severity": "warning",
                "message": f"Current draw abnormal: {current:.2f}A",
                "timestamp": _iso_now(),
                "code": "ABNORMAL_CURRENT",
            }
        )

    if pitch >= 25 or roll >= 25:
        alerts.append(
            {
                "id": int(datetime.now(timezone.utc).timestamp() * 1000) + 4,
                "type": "alert",
                "robot_id": robot_id,
                "severity": "warning",
                "message": f"Orientation anomaly: pitch={pitch:.1f}, roll={roll:.1f}",
                "timestamp": _iso_now(),
                "code": "ORIENTATION_ANOMALY",
            }
        )

    return alerts
