from datetime import datetime, timezone
from typing import Any, Dict, List


def build_telemetry_tick(robots: Dict[str, Dict[str, Any]], alerts: List[Dict[str, Any]], ai_insights: List[Dict[str, Any]], commands: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "telemetry_tick",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "robots": robots,
        "alerts": alerts[-20:],
        "ai_insights": ai_insights[-20:],
        "commands": commands[-20:],
    }
