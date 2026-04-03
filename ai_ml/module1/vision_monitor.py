import argparse
import json
import time
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO


parser = argparse.ArgumentParser()
parser.add_argument("--source", default="0")
args = parser.parse_args()

source = 0 if str(args.source).isdigit() else args.source
cap = cv2.VideoCapture(source)
if not cap.isOpened():
    raise RuntimeError("Could not open source")

model = YOLO("yolov8n.pt")
interest_names = {"person", "bottle", "backpack"}
interest_ids = {idx for idx, name in model.names.items() if name in interest_names}

roi_points = [[120, 120], [560, 120], [620, 420], [140, 420]]
selected_idx = -1
active_inside = {}
latest_tracked = []
frame_count = 0
frame_skip = 2
last_time = time.time()
fps = 0.0
log_path = "breach_log.jsonl"


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


cv2.namedWindow("ACE Vision Monitor")
cv2.setMouseCallback("ACE Vision Monitor", on_mouse)

while True:
    ok, frame = cap.read()
    if not ok:
        break

    frame_count += 1

    if frame_count % frame_skip == 0:
        tracked = []
        result = model.track(frame, persist=True, verbose=False)[0]
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                if cls_id not in interest_ids:
                    continue
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                obj_id = -1
                if boxes.id is not None:
                    obj_id = int(boxes.id[i].item())
                tracked.append(
                    {
                        "id": obj_id,
                        "cls": cls_id,
                        "name": model.names[cls_id],
                        "conf": conf,
                        "box": (x1, y1, x2, y2),
                        "center": (cx, cy),
                    }
                )
        latest_tracked = tracked

    now = time.time()
    dt = max(now - last_time, 1e-6)
    fps = 0.9 * fps + 0.1 * (1.0 / dt)
    last_time = now

    inside_now = set()
    breach = False

    for d in latest_tracked:
        x1, y1, x2, y2 = d["box"]
        cx, cy = d["center"]
        is_inside = point_inside_polygon(cx, cy, roi_points)
        if is_inside:
            breach = True
        color = (0, 0, 255) if is_inside else (0, 255, 0)
        label = f"{d['name']} {d['conf']:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (cx, cy), 3, color, -1)
        cv2.putText(frame, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        if d["id"] >= 0 and is_inside:
            inside_now.add(d["id"])
            if d["id"] not in active_inside:
                entered = datetime.utcnow().isoformat()
                active_inside[d["id"]] = entered
                write_log("enter", d["id"], entered_at=entered)

    for obj_id in list(active_inside.keys()):
        if obj_id not in inside_now:
            entered = active_inside.pop(obj_id)
            entered_dt = datetime.fromisoformat(entered)
            exited = datetime.utcnow().isoformat()
            duration = (datetime.fromisoformat(exited) - entered_dt).total_seconds()
            write_log("exit", obj_id, entered_at=entered, exited_at=exited, duration=round(duration, 3))

    poly = as_polygon(roi_points)
    roi_color = (0, 0, 255) if breach else (0, 255, 0)
    cv2.polylines(frame, [poly], True, roi_color, 3)

    for p in roi_points:
        cv2.circle(frame, tuple(p), 8, (255, 255, 0), -1)

    cv2.putText(frame, f"FPS: {fps:.1f}", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Inside: {len(active_inside)}", (16, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.8, roi_color, 2)

    cv2.imshow("ACE Vision Monitor", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
