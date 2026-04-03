import json
import os
import re
import requests


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


def extract_issue(text):
    t = text.lower()
    patterns = [
        r"motor temp[^,.]*",
        r"vibration[^,.]*",
        r"battery[^,.]*",
        r"camera[^,.]*",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            return m.group(0)
    return "unspecified issue"


def extract_directive(text):
    t = text.lower()
    actions = [
        "reduce load",
        "switch to autonomous safe mode",
        "return to base",
        "continue mission",
        "monitor",
    ]
    for a in actions:
        if a in t:
            return a
    return "investigate"


def parse_rule_based(text):
    return {
        "issue": extract_issue(text),
        "severity": classify_severity(text),
        "directive": extract_directive(text),
        "urgency": classify_urgency(text),
    }


def parse_with_openai(text, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Extract JSON with keys: issue, severity, directive, urgency. Use one of low|medium|high for severity and urgency.",
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=30)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    try:
        return json.loads(content)
    except Exception:
        return {"raw": content}


if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY", "")
    print("=== NLP Transcript Parser ===")
    for i, line in enumerate(TRANSCRIPTS, start=1):
        if api_key:
            try:
                parsed = parse_with_openai(line, api_key)
                mode = "openai"
            except Exception:
                parsed = parse_rule_based(line)
                mode = "fallback"
        else:
            parsed = parse_rule_based(line)
            mode = "rule"

        print(f"\n[{i}] {line}")
        print(f"mode={mode}")
        print(json.dumps(parsed, indent=2))
