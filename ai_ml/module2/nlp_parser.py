import json
import os
import re
from datetime import datetime
from typing import Dict, List
from urllib import request, error


TRANSCRIPTS = [
    "Control, left rear motor temp is rising above threshold, reduce load now.",
    "Team, vibration spike on drive train, switch to autonomous safe mode immediately.",
    "Battery at 18 percent and dropping fast, return to base.",
    "Minor camera blur observed, continue mission and monitor.",
]


def classify_severity(text):
    t = text.lower()
    if any(k in t for k in ["immediately", "critical", "failure", "spike"]):
        return "high"
    if any(k in t for k in ["above threshold", "warning", "reduce", "dropping"]):
        return "medium"
    return "low"


def classify_urgency(text):
    t = text.lower()
    if any(k in t for k in ["immediately", "now", "urgent"]):
        return "high"
    if any(k in t for k in ["soon", "reduce", "monitor"]):
        return "medium"
    return "low"


# Map domain keywords to structured subsystem names.
COMPONENT_KEYWORD_MAP = {
    "motor": "Motor",
    "battery": "Battery",
    "camera": "Camera",
    "vibration": "Drive Train",
    "drive": "Drive Train",
    "temperature": "Thermal System",
    "temp": "Thermal System",
    "lidar": "LiDAR",
    "mcu": "MCU",
    "wheel": "Drive System",
    "voltage": "Power System",
}


# Define directive patterns that map free text to structured actions.
DIRECTIVE_PATTERNS = [
    {
        "pattern": "reduce load",
        "action": "Reduce motor load",
        "target": "Drive System",
    },
    {
        "pattern": "return to base",
        "action": "Return to base immediately",
        "target": "Navigation",
    },
    {
        "pattern": "switch to autonomous",
        "action": "Engage autonomous safe mode",
        "target": "Control System",
    },
    {
        "pattern": "switch to safe mode",
        "action": "Engage autonomous safe mode",
        "target": "Control System",
    },
    {
        "pattern": "safe mode",
        "action": "Engage autonomous safe mode",
        "target": "Control System",
    },
    {
        "pattern": "continue mission",
        "action": "Continue current mission",
        "target": "Operator",
    },
    {
        "pattern": "monitor",
        "action": "Monitor and log values",
        "target": "Operator",
    },
]


# Extract issue objects from transcript text.
def extract_issues(text: str) -> List[Dict[str, str]]:
    lower = text.lower()
    clauses = [c.strip() for c in re.split(r"[.,;]", text) if c.strip()]
    issues: List[Dict[str, str]] = []
    used = set()

    for keyword, component in COMPONENT_KEYWORD_MAP.items():
        if keyword in lower and component not in used:
            description = ""
            for clause in clauses:
                if keyword in clause.lower():
                    description = clause
                    break
            if not description:
                description = f"{component} anomaly reported"
            issues.append(
                {
                    "component": component,
                    "description": description,
                    "severity": classify_severity(text),
                }
            )
            used.add(component)

    return issues


# Extract directive objects from transcript text.
def extract_directives(text: str) -> List[Dict[str, str]]:
    lower = text.lower()
    directives: List[Dict[str, str]] = []
    for rule in DIRECTIVE_PATTERNS:
        if rule["pattern"] in lower:
            directives.append(
                {
                    "action": rule["action"],
                    "target": rule["target"],
                    "urgency": classify_urgency(text),
                }
            )
    return directives


# Convert issue severities into a single overall status.
def calculate_overall_status(issues: List[Dict[str, str]]) -> str:
    if not issues:
        return "SAFE"
    severities = {i["severity"] for i in issues}
    if "high" in severities:
        return "EMERGENCY"
    if "medium" in severities:
        return "ALERT"
    return "CAUTION"


# Parse JSON response from OpenAI endpoint when available.
def call_openai_parser(text: str, api_key: str) -> Dict[str, object]:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return strictly valid JSON with keys: issues, directives, overall_status. "
                    "issues: list of {component, description, severity}. "
                    "directives: list of {action, target, urgency}. "
                    "overall_status: SAFE|CAUTION|ALERT|EMERGENCY."
                ),
            },
            {"role": "user", "content": text},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"].strip()
    return json.loads(content)


# Parse transcript using optional OpenAI path with safe rule-based fallback.
def parse_transcript(text: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            parsed = call_openai_parser(text, api_key)
            issues = parsed.get("issues", [])
            directives = parsed.get("directives", [])
            overall = parsed.get("overall_status", "SAFE")
            return {
                "issues": issues,
                "directives": directives,
                "overall_status": overall,
                "mode": "openai",
            }
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
            pass

    issues = extract_issues(text)
    if not issues and classify_severity(text) == "high":
        issues.append(
            {
                "component": "General",
                "description": text.strip(),
                "severity": "high",
            }
        )
    directives = extract_directives(text)
    overall = calculate_overall_status(issues)
    return {
        "issues": issues,
        "directives": directives,
        "overall_status": overall,
        "mode": "rule-based",
    }


# Render output in a readable incident-console style.
def pretty_print(text: str, result: dict) -> None:
    severity_icon = {"low": "🟢", "medium": "🟠", "high": "🔴"}
    urgency_icon = {"low": "🕐", "medium": "⏰", "high": "🚨"}
    overall_icon = {
        "SAFE": "✅",
        "CAUTION": "⚠️",
        "ALERT": "🔴",
        "EMERGENCY": "🚨",
    }

    print("─" * 60)
    print(f"📻 TRANSCRIPT: '{text}'")
    print(f"Mode: {result.get('mode', 'rule-based')}")
    print(f"Overall: {overall_icon.get(result['overall_status'], '✅')} {result['overall_status']}")

    print("ISSUES DETECTED:")
    if result["issues"]:
        for item in result["issues"]:
            icon = severity_icon.get(item["severity"], "🟢")
            print(f"  {icon} {item['component']}: {item['description']} (severity={item['severity']})")
    else:
        print("  🟢 None")

    print("DIRECTIVES:")
    if result["directives"]:
        for item in result["directives"]:
            icon = urgency_icon.get(item["urgency"], "🕐")
            print(f"  {icon} {item['action']} -> {item['target']} (urgency={item['urgency']})")
    else:
        print("  🕐 None")


# Print Jetson deployment options requested in the evaluation prompt.
def print_jetson_deployment_box() -> None:
    lines = [
        "Jetson Deployment Options",
        "1) GGUF Quantization: Use llama.cpp or Ollama with Llama-3.2-3B-Instruct.Q4_K_M.gguf.",
        "   This can run around ~10 tok/s on a 4GB Jetson Orin with careful memory settings.",
        "2) RAG: Store known failure-pattern rulebook in FAISS/ChromaDB.",
        "   Retrieve top-3 similar rules and feed them to a compact 1B model for fast domain decisions.",
        "3) Fine-tuned BERT: Train bert-tiny or distilbert on labeled transcripts.",
        "   Model size can stay under 50MB and latency can be under 5ms without GPU.",
    ]
    width = max(len(line) for line in lines) + 4
    print("\n" + "=" * width)
    for line in lines:
        print(f"| {line.ljust(width - 4)} |")
    print("=" * width)


# Parse each transcript, display result, and save a JSON log for auditability.
if __name__ == "__main__":
    print("ACE NLP Technical Intelligence Parser")
    all_results = []

    for transcript in TRANSCRIPTS:
        result = parse_transcript(transcript)
        pretty_print(transcript, result)
        all_results.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "transcript": transcript,
                "result": result,
            }
        )

    with open("nlp_parse_log.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("\nResults saved to nlp_parse_log.json")
    print_jetson_deployment_box()
