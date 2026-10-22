#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting FloodLens - Geospatial Flood Impact Engine"
echo "=========================================================="

# 1. Ensure Python dependencies are installed
if ! python3 -c "import fastapi, uvicorn, pydantic" 2>/dev/null; then
    echo "[FloodLens] Installing backend dependencies..."
    if ! command -v pip &> /dev/null; then
        curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
        python3 /tmp/get-pip.py --break-system-packages
    fi
    pip install --break-system-packages fastapi uvicorn pydantic pytest httpx
fi

# 2. Generate GIS synthetic data if missing
echo "[FloodLens] Checking geospatial layers and cache..."
python3 -m backend.synthetic

# 3. Start Backend in Background
echo "[FloodLens] Starting FastAPI backend on http://127.0.0.1:8001..."
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!

trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

# 4. Start Frontend Vite Server
echo "[FloodLens] Starting Vite Frontend on http://0.0.0.0:3000..."
npm run dev
