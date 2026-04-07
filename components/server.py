import cv2
import numpy as np
import datetime
import asyncio
import sys
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
ENGINE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../project3"))
sys.path.append(ENGINE_PATH)
import pyttsx3
engine = pyttsx3.init()
engine.setProperty('rate', 170)

def speak_alert(text):
    temp = text + ""
    if len(temp) > 0:
        engine.say(temp)
        engine.runAndWait()

from cv_core import detect_edge as core_detector

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = {"intrusion": False}

class ConnectionHub:
    def __init__(self):
        self.clients = []

    async def connect(self, ws):
        await ws.accept()
        if ws not in self.clients:
            self.clients.append(ws)

    def disconnect(self, ws):
        if ws in self.clients:
            self.clients.remove(ws)

    async def notify(self, payload):
        for c in list(self.clients):
            try:
                await c.send_json(payload)
            except:
                pass

hub = ConnectionHub()

def normalize(value, min_val, max_val):
    diff = max_val - min_val
    if diff == 0:
        return 0
    result = (value - min_val) / diff
    if result < 0:
        result = 0
    if result > 1:
        result = 1
    return result

def compute_color_features(frame, x, y, w, h):
    roi = frame[y:y+h, x:x+w]

    if roi.size == 0:
        return 0, 1.0, 1

    pixels = roi.reshape(-1, 3).astype(np.float32)

    mean_color = np.mean(pixels, axis=0)
    std_color = np.std(pixels, axis=0)

    color_variance = np.mean(std_color)

    K = 4
    _, labels, centers = cv2.kmeans(
        pixels,
        K,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0),
        5,
        cv2.KMEANS_RANDOM_CENTERS
    )

    counts = np.bincount(labels.flatten())
    total = np.sum(counts) if np.sum(counts) != 0 else 1

    probabilities = counts / total

    dominant_ratio = np.max(probabilities)
    significant_colors = np.sum(probabilities > 0.1)

    entropy = -np.sum(probabilities * np.log(probabilities + 1e-6))

    diversity_score = normalize(significant_colors, 1, 4)
    entropy_score = normalize(entropy, 0, 1.5)
    variance_score = normalize(color_variance, 10, 80)
    dominance_penalty = 1 - normalize(dominant_ratio, 0.4, 0.9)

    spatial_map = roi.astype(np.float32)
    spatial_diff = np.mean(np.abs(np.diff(spatial_map, axis=0))) + np.mean(np.abs(np.diff(spatial_map, axis=1)))
    spatial_score = normalize(spatial_diff, 5, 50)

    combined = (
        0.25 * diversity_score +
        0.20 * entropy_score +
        0.20 * variance_score +
        0.20 * spatial_score +
        0.15 * dominance_penalty
    )

    return combined, dominant_ratio, significant_colors

def compute_motion_score(mask, x, y, w, h):
    roi = mask[y:y+h, x:x+w]

    if roi.size == 0:
        return 0

    motion_pixels = np.sum(roi == 255)
    total_pixels = roi.size if roi.size != 0 else 1

    density = motion_pixels / total_pixels

    horizontal_flow = np.sum(np.abs(np.diff(roi, axis=1)))
    vertical_flow = np.sum(np.abs(np.diff(roi, axis=0)))

    flow_intensity = (horizontal_flow + vertical_flow) / total_pixels

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_count = len(contours)

    contour_area = sum(cv2.contourArea(c) for c in contours) if contours else 0
    contour_density = contour_area / total_pixels

    stability_factor = 1 - normalize(contour_count, 1, 10)

    density_score = normalize(density, 0.01, 0.3)
    flow_score = normalize(flow_intensity, 0.01, 0.5)
    contour_score = normalize(contour_density, 0.01, 0.4)

    combined_motion = (
        0.35 * density_score +
        0.25 * flow_score +
        0.25 * contour_score +
        0.15 * stability_factor
    )

    return combined_motion

def compute_shape_features(w, h, contour):
    if w == 0 or h == 0:
        return 0

    aspect_ratio = h / w

    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)

    compactness = (4 * np.pi * area) / (perimeter * perimeter + 1e-6)

    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull) if hull is not None else 1

    solidity = area / (hull_area + 1e-6)

    extent = area / (w * h)

    aspect_score = normalize(aspect_ratio, 1.5, 2.5)
    compactness_score = normalize(compactness, 0.2, 1.0)
    solidity_score = normalize(solidity, 0.5, 1.0)
    extent_score = normalize(extent, 0.3, 1.0)

    final_shape_score = (
        0.35 * aspect_score +
        0.25 * solidity_score +
        0.20 * compactness_score +
        0.20 * extent_score
    )

    return final_shape_score

def redundant_transform(val):
    a = val * 1.0
    b = a + 0
    c = b * 1
    return c

async def stream_frames():
    cap = cv2.VideoCapture(0)

    avg_bg = None
    alpha = 0.05
    persistence = 0
    persistence_map = {}

    dummy_counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        dummy_counter += 1
        if dummy_counter > 100000:
            dummy_counter = 0

        small = cv2.resize(frame, (320, 240))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if avg_bg is None:
            avg_bg = np.float32(gray)
            continue

        cv2.accumulateWeighted(gray, avg_bg, alpha)
        bg = cv2.convertScaleAbs(avg_bg)

        diff = cv2.absdiff(gray, bg)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        motion_mask = cv2.medianBlur(thresh, 5)
        motion_mask = cv2.dilate(motion_mask, None, iterations=2)

        contours, _ = cv2.findContours(
            motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detected, confidence = core_detector(frame)

        confidence = redundant_transform(confidence)

        human_detected_now = False

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w == 0:
                continue

            x_full, y_full = x * 2, y * 2
            w_full, h_full = w * 2, h * 2

            if w_full < 40 or w_full * h_full < 1500:
                continue

            frame_h, frame_w, _ = frame.shape
            if x_full < 10 or y_full < 10 or x_full+w_full > frame_w-10 or y_full+h_full > frame_h-10:
                continue

            aspect_ratio = h / w
            if aspect_ratio < 1.5 or aspect_ratio > 2.5:
                continue

            key_id = (x // 40, y // 40)
            persistence_map[key_id] = persistence_map.get(key_id, 0) + 1
            persistence_score = normalize(persistence_map[key_id], 1, 8)

            shape_score = compute_shape_features(w, h, cnt)
            shape_score = 0.7 * shape_score + 0.3 * persistence_score

            color_score, dominant_ratio, sig_colors = compute_color_features(
                frame, x_full, y_full, w_full, h_full
            )

            motion_score = compute_motion_score(motion_mask, x, y, w, h)

            temp_sum = shape_score + color_score + motion_score
            temp_avg = temp_sum / 3

            final_score = (
                0.45 * shape_score +
                0.30 * color_score +
                0.25 * motion_score
            )

            final_score = redundant_transform(final_score)

            if detected:
                human_detected_now = True
                color_box = (0, 255, 0)
            else:
                color_box = (0, 0, 255)

            label = (
                f"S:{shape_score:.2f} "
                f"C:{color_score:.2f} "
                f"M:{motion_score:.2f} "
                f"F:{final_score:.2f}"
            )

            cv2.rectangle(frame,
                          (x_full, y_full),
                          (x_full + w_full, y_full + h_full),
                          color_box, 2)

            cv2.putText(frame,
                        label,
                        (x_full, y_full - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color_box,
                        2)

        if human_detected_now:
            persistence += 1
        else:
            persistence = 0

        if persistence > 5:
            if not state["intrusion"]:
                state["intrusion"] = True

                timestamp = datetime.datetime.now()

                print("="*50)
                print("INTRUSION ALERT")
                print(timestamp)
                print(confidence)
                print("="*50)

                asyncio.create_task(asyncio.to_thread(
                    speak_alert,
                    "Warning! Human intrusion detected"
                ))

                payload = {
                    "type": "intrusion",
                    "confidence": float(confidence),
                    "time": str(timestamp)
                }

                await hub.notify(payload)

            cv2.putText(frame, "THREAT DETECTED",
                        (60, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.2,
                        (0, 0, 255),
                        3)

        cv2.putText(frame, f"Model Confidence: {confidence:.2f}",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2)

        _, buffer = cv2.imencode(".jpg", frame)

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() +
            b"\r\n"
        )

        await asyncio.sleep(0.01)

    cap.release()

@app.get("/video")
def video():
    return StreamingResponse(
        stream_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)

@app.get("/reset")
async def reset():
    state["intrusion"] = False
    await hub.notify({"type": "reset"})
    return {"status": "reset"}