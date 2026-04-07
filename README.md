# Human Intrusion Detection

This project detects humans from your webcam feed and shows live intrusion alerts in a Next.js dashboard.

## Tech stack

- Frontend: Next.js (App Router)
- Backend: FastAPI + OpenCV
- Detector: YOLOv4 (auto-downloaded on first run)

## 1) Install dependencies

Frontend:

```bash
npm install
```

Backend (Python 3.10+ recommended):

```bash
pip install -r requirements.txt
```

## 2) Run backend server

From the project root:

```bash
uvicorn components.server:app --host 0.0.0.0 --port 8000 --reload
```

Notes:

- The first run can take time because YOLOv4 files are downloaded automatically.
- Allow webcam permission when prompted by your OS.

## 3) Run frontend server

In another terminal:

```bash
npm run dev
```

Open http://localhost:3000

## 4) How intrusion alert works

- Backend streams camera frames at http://localhost:8000/video
- Frontend displays the stream and listens to WebSocket alerts at ws://localhost:8000/ws
- When a human intrusion is confirmed, UI shows alert and timestamp
- Click Resume Surveillance to clear alert state

## Troubleshooting

- If UI shows Backend Disconnected, make sure FastAPI is running on port 8000.
- If no detections happen, check webcam access and lighting.
- If Python import errors occur, confirm you installed requirements in the active Python environment.



first time setup
cd C:\Users\hp\intrusion-detection
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install

run backend 
cd C:\Users\hp\intrusion-detection
.\.venv\Scripts\Activate.ps1
python -m uvicorn components.server:app --host 0.0.0.0 --port 8000 --reload

run frontend 
cd C:\Users\hp\intrusion-detection
npm run dev
