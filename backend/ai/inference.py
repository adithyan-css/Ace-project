from typing import Dict, List


def risk_label(probability: float) -> str:
    if probability >= 0.8:
        return "critical"
    if probability >= 0.6:
        return "high"
    if probability >= 0.35:
        return "medium"
    return "low"


def severity_from_risk(risk: str) -> str:
    r = risk.lower()
    if r in {"critical", "high"}:
        return "danger"
    if r == "medium":
        return "warning"
    return "info"


def score_vision_breach(inside_count: int, object_count: int) -> float:
    if object_count <= 0:
        return 0.0
    ratio = inside_count / object_count
    if ratio < 0:
        ratio = 0.0
    if ratio > 1:
        ratio = 1.0
    return float(ratio)


def summarize_vision(objects: List[Dict[str, float]], inside_count: int) -> Dict[str, object]:
    total = len(objects)
    score = score_vision_breach(inside_count, total)
    if score >= 0.75:
        status = "critical"
    elif score >= 0.4:
        status = "warning"
    else:
        status = "normal"

    return {
        "object_count": total,
        "inside_roi_count": inside_count,
        "anomaly_score": round(score, 4),
        "status": status,
    }
