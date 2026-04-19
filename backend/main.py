import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.dtos import Circle, CircleInput, TurnHistory, TYPE_METADATA
from backend.connectionManager import ConnectionManager
from backend.calibration import HomographyManager
from backend.player import NUM_PLAYERS
from backend.turnManager import TurnManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

frontend_clients: List[WebSocket] = []
effect_manager = ConnectionManager()

async def set_circle_effect(esp_id: int, effect: int, r: int = 0, g: int = 0, b: int = 0):
    payload = [{"id": esp_id, "effect": effect, "r": r, "g": g, "b": b}]
    await effect_manager.broadcast(json.dumps(payload))

calibration = HomographyManager()

async def broadcast_to_frontends(data: dict):
    if not frontend_clients:
        return
    message = json.dumps(data)
    # Fire-and-forget with error isolation
    for client in frontend_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")

async def default_on_turn_end(
    circles: Dict[int, np.ndarray], history: TurnHistory, in_frame_ids: Set[int]
):
    turn_count = history.turns[-1].turn_number if history.turns else 0
    circles_list = []
    for cid, pos in circles.items():
        ctype = turn_manager.circle_types.get(int(cid))
        meta = TYPE_METADATA.get(ctype) if ctype else None
        circles_list.append({
            "id": int(cid), "x": float(pos[0]), "y": float(pos[1]),
            "type": ctype,
            "color": meta["color"] if meta else (255, 255, 255),
            "effect": meta["effect"] if meta else 1
        })
    await broadcast_to_frontends({
        "type": "turn_change",
        "turn_number": turn_count,
        "player": turn_manager.get_current_player(),
        "circles": circles_list,
        "scores": turn_manager.get_scores(),
    })

async def default_on_turn_setup():
    logger.info("Setting up turn...")
    for cid, ctype in turn_manager.circle_types.items():
        meta = TYPE_METADATA.get(ctype)
        if meta:
            try:
                r, g, b = meta["color"]
                await set_circle_effect(esp_id=cid, effect=meta["effect"], r=r, g=g, b=b)
            except Exception as e:
                logger.error(f"Failed to set effect for circle {cid}: {e}")

turn_manager = TurnManager(
    NUM_PLAYERS,
    missing_timeout_ms=2000.0,
    on_turn_end=default_on_turn_end,
    on_turn_setup=default_on_turn_setup,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    if calibration.load():
        logger.info("Calibration loaded")
    # Removed background effect_loop — not needed for core gameplay

@app.post("/api/calibrate")
async def calibrate():
    circles = calibration.get_last_n_circles(4)
    if len(circles) < 4:
        return {"status": "error", "message": f"need 4 circles, have {len(circles)}"}
    H = calibration.compute_from_corners(circles)
    calibration.save(H, circles, datetime.now().isoformat())
    return {"status": "ok", "message": "calibration saved"}

@app.post("/api/calibrate/reset")
async def calibrate_reset():
    calibration.reset()
    return {"status": "ok", "message": "calibration reset"}

@app.post("/api/turn/end")
async def end_turn():
    # ✅ FIX: Score computation happens INSIDE end_turn() now
    await turn_manager.end_turn()
    
    # ✅ FIX: Only start new turn if circles exist AND pending flag is set
    if turn_manager.has_pending_turn_start() or turn_manager.circle_ids:
        await turn_manager.start_turn()  # Runs on_turn_setup (color effects)
    
    return {"status": "ok", "turn": turn_manager.turn_count, "scores": turn_manager.get_scores()}

@app.get("/api/calibration/status")
async def calibration_status():
    last_4 = calibration.get_last_n_circles(4).tolist()
    return {
        "calibrated": calibration.is_calibrated(),
        "tracked_count": calibration.get_tracked_count(),
        "last_positions": last_4 if last_4 else [],
    }

@app.post("/api/tracker")
async def tracker_update(circles: List[CircleInput]):
    for c in circles:
        calibration.track_circle(c.id, c.x, c.y)

    if not calibration.is_calibrated():
        screen_circles = [Circle(id=c.id, x=c.x / 3000.0, y=c.y / 4000.0) for c in circles]
        # ✅ FIX: Handle pending turn start
        pending = turn_manager.update(screen_circles)
        if pending:
            await turn_manager.start_turn()
        # Broadcast positions (uncalibrated)
        circles_list = [{
            "id": c.id, "x": c.x / 3000.0, "y": c.y / 4000.0,
            "type": turn_manager.circle_types.get(c.id),
            "color": (255,255,255), "effect": 1
        } for c in circles]
        await broadcast_to_frontends({"type": "positions", "circles": circles_list})
        return {"status": "uncalibrated"}

    # Calibrated path
    screen_pts = np.array([[c.x, c.y] for c in circles], dtype=np.float32)
    uv_pts = calibration.transform_batch(screen_pts)
    circle_objs = [Circle(id=c.id, x=float(uv_pts[i, 0]), y=float(uv_pts[i, 1])) for i, c in enumerate(circles)]

    # ✅ FIX: Handle pending turn start after update
    pending = turn_manager.update(circle_objs)
    if pending:
        await turn_manager.start_turn()

    # Broadcast calibrated positions
    circles_list = [{
        "id": c.id, "x": float(uv_pts[i, 0]), "y": float(uv_pts[i, 1]),
        "type": turn_manager.circle_types.get(c.id),
        "color": TYPE_METADATA.get(turn_manager.circle_types.get(c.id), {}).get("color", (255,255,255)),
        "effect": TYPE_METADATA.get(turn_manager.circle_types.get(c.id), {}).get("effect", 1)
    } for i, c in enumerate(circles)]
    
    await broadcast_to_frontends({"type": "positions", "circles": circles_list})
    return {"status": "ok", "circles_count": len(circles_list)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    frontend_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        frontend_clients.remove(websocket)

@app.websocket("/ws/device")
async def device_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/effects")
async def effects_websocket_endpoint(websocket: WebSocket):
    await effect_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        effect_manager.disconnect(websocket)

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
