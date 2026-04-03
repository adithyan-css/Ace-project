import json
import runpy
from datetime import datetime

import pytest

try:
    import ai_ml.module2.nlp_parser as nlp
except Exception:
    nlp = None


pytestmark = pytest.mark.skipif(nlp is None, reason="NLP parser module unavailable")


class TestSeverityClassifier:
    def test_immediately_is_high(self):
        assert nlp.classify_severity("Switch to safe mode immediately") == "high"

    def test_above_threshold_is_medium(self):
        assert nlp.classify_severity("temp is above threshold") == "medium"

    def test_minor_is_low(self):
        assert nlp.classify_severity("minor blur observed") == "low"

    def test_critical_keyword_is_high(self):
        assert nlp.classify_severity("critical failure detected") == "high"


class TestUrgencyClassifier:
    def test_now_is_high_urgency(self):
        assert nlp.classify_urgency("reduce load now") == "high"

    def test_monitor_is_medium_urgency(self):
        assert nlp.classify_urgency("monitor and continue") == "medium"

    def test_no_keywords_is_low(self):
        assert nlp.classify_urgency("all systems nominal") == "low"


class TestIssueExtractor:
    def test_motor_issue_detected(self):
        result = nlp.parse_transcript("left rear motor temp is rising above threshold")
        components = [item["component"] for item in result["issues"]]
        assert any(("Motor" in c) or ("Thermal" in c) for c in components)

    def test_battery_issue_detected(self):
        result = nlp.parse_transcript("Battery at 18 percent and dropping fast")
        components = [item["component"] for item in result["issues"]]
        assert "Battery" in components

    def test_no_issue_on_nominal_message(self):
        result = nlp.parse_transcript("All systems nominal, continuing mission")
        assert (result["issues"] == []) or (result["overall_status"] == "SAFE")

    def test_multiple_issues_in_one_transcript(self):
        result = nlp.parse_transcript("Motor overheating and battery critically low")
        assert len(result["issues"]) >= 2


class TestDirectiveExtractor:
    def test_return_to_base_directive(self):
        result = nlp.parse_transcript("Battery critical, return to base")
        actions = [d["action"].lower() for d in result["directives"]]
        assert any(("base" in a) or ("return" in a) for a in actions)

    def test_reduce_load_directive(self):
        result = nlp.parse_transcript("motor overheating, reduce load now")
        actions = [d["action"].lower() for d in result["directives"]]
        assert any(("reduce" in a) or ("load" in a) for a in actions)

    def test_urgency_matches_transcript_tone(self):
        result = nlp.parse_transcript("immediately switch to safe mode")
        assert result["directives"][0]["urgency"] == "high"


class TestOverallStatus:
    def test_high_severity_gives_emergency(self):
        result = nlp.parse_transcript("critical failure immediately")
        assert result["overall_status"] == "EMERGENCY"

    def test_clean_message_gives_safe(self):
        result = nlp.parse_transcript("All systems nominal")
        assert result["overall_status"] == "SAFE"

    def test_output_schema_complete(self):
        result = nlp.parse_transcript("battery warning")
        assert "issues" in result
        assert "directives" in result
        assert "overall_status" in result

    def test_overall_status_is_valid_enum(self):
        valid = {"SAFE", "CAUTION", "ALERT", "EMERGENCY"}
        for text in nlp.TRANSCRIPTS:
            result = nlp.parse_transcript(text)
            assert result["overall_status"] in valid


class TestFullPipeline:
    def test_all_sample_transcripts_parse_without_error(self):
        for text in nlp.TRANSCRIPTS:
            result = nlp.parse_transcript(text)
            assert isinstance(result, dict)

    def test_log_file_created(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runpy.run_module("ai_ml.module2.nlp_parser", run_name="__main__")
        assert (tmp_path / "nlp_parse_log.json").exists()
        data = json.loads((tmp_path / "nlp_parse_log.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)

    def test_log_contains_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runpy.run_module("ai_ml.module2.nlp_parser", run_name="__main__")
        data = json.loads((tmp_path / "nlp_parse_log.json").read_text(encoding="utf-8"))
        for item in data:
            assert "timestamp" in item
            datetime.fromisoformat(item["timestamp"])
