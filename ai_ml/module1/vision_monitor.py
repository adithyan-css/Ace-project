import argparse
import json
import time
from datetime import datetime
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO


# Parse input source so the script can run with webcam or a video file.
parser = argparse.ArgumentParser()
parser.add_argument("--source", default="0")
args = parser.parse_args()

source = 0 if str(args.source).isdigit() else args.source
cap = cv2.VideoCapture(source)
if not cap.isOpened():
    raise RuntimeError("Could not open source")

# Load YOLO and keep only the classes required in the task.
model = YOLO("yolov8n.pt")
interest_names = {"person", "bottle", "backpack"}
interest_ids = {idx for idx, name in model.names.items() if name in interest_names}

# Keep ROI mutable so corner points can be dragged with the mouse.
roi_points = [[120, 120], [560, 120], [620, 420], [140, 420]]
selected_idx = -1
active_inside = {}
latest_tracked = []
frame_count = 0
frame_skip = 2
log_path = "breach_log.jsonl"
fps_times = deque(maxlen=30)


# Write structured breach logs to JSONL.
def write_log(event_type, object_id, entered_at=None, exited_at=None, duration=None):
    payload = {
        "event": event_type,
        "object_id": int(object_id),
        "entered_at": entered_at,
        "exited_at": exited_at,
        "duration_seconds": duration,
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


# Convert a list of points into OpenCV polygon format.
def as_polygon(points):
    return np.array(points, dtype=np.int32).reshape((-1, 1, 2))


# Check whether a point lies inside the ROI polygon.
def point_inside_polygon(x, y, points):
    poly = np.array(points, dtype=np.int32)
    return cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0


# Allow interactive dragging of ROI corners.
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


cv2.namedWindow("ACE Vision Monitor")
cv2.setMouseCallback("ACE Vision Monitor", on_mouse)

# Main inference and visualization loop.
while True:
    ok, frame = cap.read()
    if not ok:
        break

    # Optional resize for consistent speed while keeping aspect ratio.
    frame_h, frame_w = frame.shape[:2]
    target_w = 640
    if frame_w > target_w:
        scale = target_w / float(frame_w)
        frame = cv2.resize(frame, (target_w, int(frame_h * scale)), interpolation=cv2.INTER_AREA)

    frame_count += 1
    run_inference = (frame_count % frame_skip == 0)
    zone_breach = False

    # Run detector/tracker every N frames for lower latency.
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

                if has_ids:
                    track_id = int(boxes.id[i].item())
                else:
                    track_id = int(i)

                now_iso = datetime.utcnow().isoformat()
                if inside and track_id not in active_inside:
                    active_inside[track_id] = now_iso
                    write_log("ENTRY", track_id, entered_at=now_iso)

                if (not inside) and track_id in active_inside:
                    entered = active_inside.pop(track_id)
                    duration = (datetime.utcnow() - datetime.fromisoformat(entered)).total_seconds()
                    write_log(
                        "EXIT",
                        track_id,
                        entered_at=entered,
                        exited_at=now_iso,
                        duration=round(duration, 3),
                    )

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

        # Handle edge case where tracked IDs disappear between frames.
        visible_ids = {d["track_id"] for d in latest_tracked}
        for track_id in list(active_inside.keys()):
            if track_id not in visible_ids:
                entered = active_inside.pop(track_id)
                exited = datetime.utcnow().isoformat()
                duration = (datetime.fromisoformat(exited) - datetime.fromisoformat(entered)).total_seconds()
                write_log("EXIT", track_id, entered_at=entered, exited_at=exited, duration=round(duration, 3))

    # Draw detections from the latest tracker output.
    for d in latest_tracked:
        x1, y1, x2, y2 = d["xyxy"]
        cx, cy = d["center"]
        inside = d["inside"]
        zone_breach = zone_breach or inside
        color = (0, 0, 255) if inside else (0, 255, 0)
        label = f"{d['name']} #{d['track_id']} {d['conf']:.0%}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (cx, cy), 4, color, -1)
        cv2.putText(
            frame,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    # Draw ROI with translucent fill and draggable corner handles.
    roi_color = (0, 0, 255) if zone_breach else (0, 255, 0)
    poly = as_polygon(roi_points)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [poly], roi_color)
    frame = cv2.addWeighted(overlay, 0.15, frame, 0.85, 0.0)
    cv2.polylines(frame, [poly], True, roi_color, 2)
    for p in roi_points:
        cv2.circle(frame, tuple(p), 8, (255, 255, 0), -1)

    # Compute rolling FPS from the last 30 frame timestamps.
    fps_times.append(time.time())
    if len(fps_times) >= 2:
        elapsed = max(fps_times[-1] - fps_times[0], 1e-6)
        fps = (len(fps_times) - 1) / elapsed
    else:
        fps = 0.0

    # Draw a semi-transparent top bar with monitor status.
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
    cv2.putText(
        frame,
        fps_text,
        (frame.shape[1] - fps_size[0] - 12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    # Draw footer helper text so users know available controls.
    footer = "Drag corners to edit ROI | Q to quit"
    cv2.putText(
        frame,
        footer,
        (12, frame.shape[0] - 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 180, 180),
        2,
        cv2.LINE_AA,
    )

    cv2.imshow("ACE Vision Monitor", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Close any active sessions still inside ROI and flush exit logs.
for track_id, entered in list(active_inside.items()):
    exited = datetime.utcnow().isoformat()
    duration = (datetime.fromisoformat(exited) - datetime.fromisoformat(entered)).total_seconds()
    write_log("EXIT", track_id, entered_at=entered, exited_at=exited, duration=round(duration, 3))

cap.release()
cv2.destroyAllWindows()
print(f"Logs saved to {log_path}")
