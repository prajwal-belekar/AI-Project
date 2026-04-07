import cv2
import os
import urllib.request
import numpy as np
# -------------------------------
# AUTO DOWNLOAD YOLO FILES
# -------------------------------
BASE_DIR = os.path.dirname(__file__)

weights_path = os.path.join(BASE_DIR, "yolov4.weights")
cfg_path = os.path.join(BASE_DIR, "yolov4.cfg")
names_path = os.path.join(BASE_DIR, "coco.names")

def download_file(url, path):
    if not os.path.exists(path):
        print(f"⬇️ Downloading {os.path.basename(path)}...")
        urllib.request.urlretrieve(url, path)
        print("✅ Done!")

# Official YOLOv4 files
download_file("https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4.weights", weights_path)
download_file("https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg", cfg_path)
download_file("https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names", names_path)

# -------------------------------
# LOAD MODEL
# -------------------------------
net = cv2.dnn.readNet(weights_path, cfg_path)
layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]

# Load classes
with open(names_path, "r") as f:
    classes = [line.strip() for line in f.readlines()]

# -------------------------------
# DETECT EDGES
# -------------------------------
def detect_edge(frame):
    height, width, _ = frame.shape

    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (320, 320), swapRB=True, crop=False)
    net.setInput(blob)

    outputs = net.forward(output_layers)

    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = scores.argmax()
            confidence = scores[class_id]

            # ONLY PERSON CLASS
            if class_id == 0 and confidence > 0.5:

                # Bounding box
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)

                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                # -------------------------------
                # SAFETY CHECK
                # -------------------------------
                if x < 0 or y < 0 or x + w > width or y + h > height:
                    continue

                roi = frame[y:y+h, x:x+w]

                # -------------------------------
                # 1. SIZE FILTER
                # -------------------------------
                if w < 60 or h < 120:
                    continue

                # -------------------------------
                # 2. ASPECT RATIO (HUMAN SHAPE)
                # -------------------------------
                aspect_ratio = h / float(w)
                if aspect_ratio < 1.5 or aspect_ratio > 4.0:
                    continue

                # -------------------------------
                # 3. COLOR VARIANCE FILTER 🔥
                # -------------------------------
                std_dev = roi.std()

                # Blanket = low variance (flat color)
                # Human = high variance (clothes, skin, edges)
                if std_dev < 25:
                    continue

                # -------------------------------
                # 4. EDGE DENSITY FILTER 🔥
                # -------------------------------
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray_roi, 50, 150)

                edge_density = np.sum(edges) / (w * h)

                if edge_density < 5:   # low texture = blanket
                    continue

                return True, confidence

    return False, 0.0