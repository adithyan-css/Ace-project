import argparse
import json
import time
from collections import deque
from datetime import datetime, timezone

import cv2
import numpy as np
from ultralytics import YOLO


roi_points = [[120, 120], [560, 120], [620, 420], [140, 420]]
selected_idx = -1
log_path = "breach_log.jsonl"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_log_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def write_log(event_type, object_id, entered_at=None, exited_at=None, duration=None):
    payload = {
        "event": event_type,
        "object_id": int(object_id),
        "entered_at": entered_at,
        "exited_at": exited_at,
        "duration_seconds": duration,
        "timestamp": now_utc().isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def as_polygon(points):
    return np.array(points, dtype=np.int32).reshape((-1, 1, 2))


def point_inside_polygon(x, y, points):
    poly = np.array(points, dtype=np.int32)
    return cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0


def on_mouse(event, x, y, flags, param):
    global selected_idx
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, (px, py) in enumerate(roi_points):
            if (px - x) * (px - x) + (py - y) * (py - y) <= 18 * 18:
                selected_idx = i
                break
    elif event == cv2.EVENT_MOUSEMOVE and selected_idx != -1:
        roi_points[selected_idx] = [x, y]
    elif event == cv2.EVENT_LBUTTONUP:
        selected_idx = -1


def calculate_fps(fps_times):
    if len(fps_times) < 2:
        return 0.0
    elapsed = max(fps_times[-1] - fps_times[0], 1e-6)
    return (len(fps_times) - 1) / elapsed


def apply_entry_exit_logic(track_id, inside, active_inside):
    now_iso = now_utc().isoformat()
    if inside and track_id not in active_inside:
        active_inside[track_id] = now_iso
        write_log("ENTRY", track_id, entered_at=now_iso)
    elif (not inside) and track_id in active_inside:
        entered = active_inside.pop(track_id)
        duration = (now_utc() - parse_log_ts(entered)).total_seconds()
        write_log("EXIT", track_id, entered_at=entered, exited_at=now_iso, duration=round(duration, 3))
        return duration
    return 0.0


def close_active_tracks(active_inside):
    total = 0.0
    for track_id, entered in list(active_inside.items()):
        exited = now_utc().isoformat()
        duration = (parse_log_ts(exited) - parse_log_ts(entered)).total_seconds()
        write_log("EXIT", track_id, entered_at=entered, exited_at=exited, duration=round(duration, 3))
        total += duration
    return total


def run_monitor(source=0, frame_skip=2, show_window=True, max_frames=None, event_callback=None):
    cap = cv2.VideoCapture(source)
    time.sleep(2)
    if not cap.isOpened():
        raise RuntimeError("Could not open source")

    model = YOLO("yolov8n.pt")
    interest_names = {"person", "car", "truck", "bus", "motorcycle"}
    interest_ids = {idx for idx, name in model.names.items() if name in interest_names}

    if show_window:
        cv2.namedWindow("ACE Vision Monitor")
        cv2.setMouseCallback("ACE Vision Monitor", on_mouse)

    active_inside = {}
    total_occupancy_seconds = 0.0
    latest_tracked = []
    frame_count = 0
    fps_times = deque(maxlen=30)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_h, frame_w = frame.shape[:2]
        target_w = 640
        if frame_w > target_w:
            scale = target_w / float(frame_w)
            frame = cv2.resize(frame, (target_w, int(frame_h * scale)), interpolation=cv2.INTER_AREA)

        frame_count += 1
        run_inference = (frame_count % frame_skip == 0)
        zone_breach = False

        if run_inference:
            tracked = []
            results = model.track(
                frame,
                persist=True,
                classes=list(interest_ids),
                conf=0.4,
                verbose=False,
            )
            result = results[0]

            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                has_ids = boxes.id is not None
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i].item())
                    if cls_id not in interest_ids:
                        continue

                    conf = float(boxes.conf[i].item())
                    x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    inside = point_inside_polygon(cx, cy, roi_points)
                    if inside:
                        zone_breach = True

                    track_id = int(boxes.id[i].item()) if has_ids else int(i)
                    total_occupancy_seconds += apply_entry_exit_logic(track_id, inside, active_inside)

                    tracked.append(
                        {
                            "track_id": track_id,
                            "cls_id": cls_id,
                            "name": model.names[cls_id],
                            "conf": conf,
                            "xyxy": (x1, y1, x2, y2),
                            "center": (cx, cy),
                            "inside": inside,
                        }
                    )

            latest_tracked = tracked

            visible_ids = {d["track_id"] for d in latest_tracked}
            for track_id in list(active_inside.keys()):
                if track_id not in visible_ids:
                    entered = active_inside.pop(track_id)
                    exited = now_utc().isoformat()
                    duration = (parse_log_ts(exited) - parse_log_ts(entered)).total_seconds()
                    write_log("EXIT", track_id, entered_at=entered, exited_at=exited, duration=round(duration, 3))
                    total_occupancy_seconds += duration

        for d in latest_tracked:
            x1, y1, x2, y2 = d["xyxy"]
            cx, cy = d["center"]
            inside = d["inside"]
            zone_breach = zone_breach or inside
            color = (0, 0, 255) if inside else (0, 255, 0)
            label = f"{d['name']} #{d['track_id']} {d['conf']:.0%}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 4, color, -1)
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

        roi_color = (0, 0, 255) if zone_breach else (0, 255, 0)
        poly = as_polygon(roi_points)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly], roi_color)
        frame = cv2.addWeighted(overlay, 0.15, frame, 0.85, 0.0)
        cv2.polylines(frame, [poly], True, roi_color, 2)
        for p in roi_points:
            cv2.circle(frame, tuple(p), 8, (255, 255, 0), -1)

        fps_times.append(time.time())
        fps = calculate_fps(fps_times)

        if event_callback and run_inference:
            detections = []
            for d in latest_tracked:
                x1, y1, x2, y2 = d["xyxy"]
                detections.append(
                    {
                        "id": d["track_id"],
                        "label": d["name"],
                        "conf": round(d["conf"], 3),
                        "x": x1,
                        "y": y1,
                        "w": max(0, x2 - x1),
                        "h": max(0, y2 - y1),
                        "inside": bool(d["inside"]),
                    }
                )
            event_callback(
                {
                    "timestamp": now_utc().isoformat(),
                    "fps": round(fps, 2),
                    "zone_breach": bool(zone_breach),
                    "polygon": [list(p) for p in roi_points],
                    "detections": detections,
                    "occupancy_seconds": round(total_occupancy_seconds, 3),
                }
            )

        hud_h = 48
        hud = frame.copy()
        cv2.rectangle(hud, (0, 0), (frame.shape[1], hud_h), (15, 15, 15), -1)
        frame = cv2.addWeighted(hud, 0.4, frame, 0.6, 0.0)

        status_text = "STATUS: BREACH" if zone_breach else "STATUS: SAFE"
        status_color = (0, 0, 255) if zone_breach else (0, 255, 0)
        cv2.putText(frame, "ACE Vision Monitor", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
        center_x = int((frame.shape[1] - text_size[0]) / 2)
        cv2.putText(frame, status_text, (center_x, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2, cv2.LINE_AA)
        fps_text = f"FPS: {fps:.1f}"
        fps_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
        cv2.putText(frame, fps_text, (frame.shape[1] - fps_size[0] - 12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Occupancy: {total_occupancy_seconds:.1f}s", (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.putText(frame, "Drag corners to edit ROI | Q to quit", (12, frame.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 2, cv2.LINE_AA)

        if show_window:
            cv2.imshow("ACE Vision Monitor", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        if max_frames is not None and frame_count >= max_frames:
            break

    total_occupancy_seconds += close_active_tracks(active_inside)
    cap.release()
    if show_window:
        cv2.destroyAllWindows()
    print(f"Logs saved to {log_path}")
    print(f"Total occupancy time: {round(total_occupancy_seconds, 3)} seconds")
    return {
        "status": "ok",
        "total_occupancy_seconds": round(total_occupancy_seconds, 3),
        "frames_processed": frame_count,
    }


def parse_source(value):
    return int(value) if str(value).isdigit() else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0")
    args = parser.parse_args()
    run_monitor(source=parse_source(args.source), frame_skip=2, show_window=True)


if __name__ == "__main__":
    main()
