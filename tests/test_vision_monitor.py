from collections import deque
from datetime import datetime, timedelta, timezone

import pytest

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

try:
    import ai_ml.module1.vision_monitor as vm
except Exception:
    vm = None


pytestmark = pytest.mark.skipif(vm is None or cv2 is None or np is None, reason="Vision dependencies unavailable")


class TestPointInPolygon:
    def test_center_point_inside_square_roi(self):
        roi = [[100, 100], [500, 100], [500, 400], [100, 400]]
        assert vm.point_inside_polygon(300, 250, roi) is True

    def test_point_outside_roi(self):
        roi = [[100, 100], [500, 100], [500, 400], [100, 400]]
        assert vm.point_inside_polygon(50, 50, roi) is False

    def test_point_on_boundary(self):
        roi = [[100, 100], [500, 100], [500, 400], [100, 400]]
        assert vm.point_inside_polygon(100, 250, roi) is True

    def test_point_just_outside_boundary(self):
        roi = [[100, 100], [500, 100], [500, 400], [100, 400]]
        assert vm.point_inside_polygon(99, 250, roi) is False

    def test_with_non_rectangular_polygon(self):
        roi = [[200, 50], [400, 50], [500, 300], [100, 300]]
        assert vm.point_inside_polygon(300, 200, roi) is True
        assert vm.point_inside_polygon(50, 50, roi) is False

    def test_top_left_corner_of_roi(self):
        roi = [[100, 100], [500, 100], [500, 400], [100, 400]]
        assert vm.point_inside_polygon(100, 100, roi) is True


class TestBreachDetectionLogic:
    def test_entry_logged_when_object_enters(self, tmp_log_path):
        active = {}
        vm.apply_entry_exit_logic(1, True, active)
        assert 1 in active

    def test_no_duplicate_entry_logged(self, tmp_log_path):
        active = {1: datetime.now(timezone.utc).isoformat()}
        before = dict(active)
        vm.apply_entry_exit_logic(1, True, active)
        assert active == before

    def test_exit_logged_when_object_leaves(self, tmp_log_path):
        active = {1: datetime.now(timezone.utc).isoformat()}
        vm.apply_entry_exit_logic(1, False, active)
        assert 1 not in active

    def test_duration_calculated_correctly(self, tmp_log_path):
        entered = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        active = {1: entered}
        vm.apply_entry_exit_logic(1, False, active)

        lines = tmp_log_path.read_text(encoding="utf-8").strip().splitlines()
        exit_logs = [line for line in lines if '"event": "EXIT"' in line]
        assert len(exit_logs) >= 1
        parsed = __import__("json").loads(exit_logs[-1])
        assert abs(parsed["duration_seconds"] - 5.0) < 0.4

    def test_multiple_objects_tracked_independently(self, tmp_log_path):
        active = {}
        vm.apply_entry_exit_logic(1, True, active)
        vm.apply_entry_exit_logic(2, True, active)
        vm.apply_entry_exit_logic(3, True, active)
        vm.apply_entry_exit_logic(2, False, active)
        assert 1 in active
        assert 2 not in active
        assert 3 in active


class TestFPSCounter:
    def test_fps_zero_with_one_frame(self):
        times = deque(maxlen=30)
        times.append(1.0)
        assert vm.calculate_fps(times) == 0.0

    def test_fps_approximate_10hz(self):
        times = deque(maxlen=30)
        for i in range(11):
            times.append(i * 0.1)
        fps = vm.calculate_fps(times)
        assert abs(fps - 10.0) < 0.5

    def test_fps_rolling_window_evicts_old_frames(self):
        times = deque(maxlen=30)
        for i in range(35):
            times.append(i * 0.1)
        assert len(times) == 30


class TestLogWriter:
    def test_entry_log_written_correctly(self, tmp_log_path):
        vm.write_log("ENTRY", 5, entered_at="2024-01-01T00:00:00")
        line = tmp_log_path.read_text(encoding="utf-8").strip()
        data = __import__("json").loads(line)
        assert data["event"] == "ENTRY"
        assert data["object_id"] == 5
        assert data["entered_at"] == "2024-01-01T00:00:00"

    def test_exit_log_contains_duration(self, tmp_log_path):
        vm.write_log("EXIT", 5, exited_at="2024-01-01T00:00:05", duration=4.5)
        line = tmp_log_path.read_text(encoding="utf-8").strip()
        data = __import__("json").loads(line)
        assert data["duration_seconds"] == 4.5

    def test_multiple_events_each_on_own_line(self, tmp_log_path):
        vm.write_log("ENTRY", 1, entered_at="t1")
        vm.write_log("EXIT", 1, exited_at="t2", duration=1.0)
        vm.write_log("ENTRY", 2, entered_at="t3")
        lines = tmp_log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            __import__("json").loads(line)

    def test_log_timestamp_is_iso_format(self, tmp_log_path):
        vm.write_log("ENTRY", 6, entered_at="2024-01-01T00:00:00")
        line = tmp_log_path.read_text(encoding="utf-8").strip()
        data = __import__("json").loads(line)
        datetime.fromisoformat(data["timestamp"])


class DummyScalar:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


class DummyArray:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, idx):
        return DummyScalar(self._values[idx])


class DummyXY:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, idx):
        class _T:
            def __init__(self, val):
                self._val = val

            def tolist(self):
                return self._val

        return _T(self._values[idx])


class DummyBoxes:
    def __init__(self, inside=True):
        self.cls = DummyArray([0])
        self.conf = DummyArray([0.9])
        self.xyxy = DummyXY([[200, 150, 260, 300] if inside else [10, 10, 40, 40]])
        self.id = DummyArray([1])

    def __len__(self):
        return 1


class DummyResult:
    def __init__(self, inside=True):
        self.boxes = DummyBoxes(inside=inside)


class DummyYOLO:
    def __init__(self, *args, **kwargs):
        self.names = {0: "person", 39: "bottle", 24: "backpack"}
        self.counter = 0

    def track(self, frame, persist=True, classes=None, conf=0.4, verbose=False):
        self.counter += 1
        inside = self.counter % 2 == 1
        return [DummyResult(inside=inside)]


class TestSyntheticVideoIntegration:
    @pytest.mark.slow
    def test_pipeline_runs_without_crash(self, tmp_path, tmp_log_path, monkeypatch):
        video_path = tmp_path / "test_video.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        for _ in range(150):
            frame = np.full((480, 640, 3), 60, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        monkeypatch.setattr(vm, "YOLO", DummyYOLO)

        vm.run_monitor(source=str(video_path), frame_skip=1, show_window=False, max_frames=60)

    @pytest.mark.slow
    def test_log_file_created(self, tmp_path, tmp_log_path, monkeypatch):
        video_path = tmp_path / "test_video.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        for _ in range(120):
            frame = np.full((480, 640, 3), 90, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        monkeypatch.setattr(vm, "YOLO", DummyYOLO)

        vm.run_monitor(source=str(video_path), frame_skip=1, show_window=False, max_frames=40)
        assert tmp_log_path.exists()

    @pytest.mark.slow
    def test_event_callback_receives_detection_payload(self, tmp_path, tmp_log_path, monkeypatch):
        video_path = tmp_path / "test_video.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        for _ in range(90):
            frame = np.full((480, 640, 3), 120, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        monkeypatch.setattr(vm, "YOLO", DummyYOLO)

        received = []

        def on_event(payload):
            received.append(payload)

        vm.run_monitor(source=str(video_path), frame_skip=1, show_window=False, max_frames=20, event_callback=on_event)

        assert len(received) > 0
        assert "fps" in received[-1]
        assert "zone_breach" in received[-1]
        assert "detections" in received[-1]
