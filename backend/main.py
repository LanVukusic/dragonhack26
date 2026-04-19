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
from backend.player import  NUM_PLAYERS
from backend.turnManager import TurnManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

frontend_clients: List[WebSocket] = []
effect_manager = ConnectionManager()




async def set_circle_effect(esp_id: int, effect: int, r: int = 0, g: int = 0, b: int = 0):
    """
    Call this async function from anywhere in your backend logic
    to push a new effect and color to the ESP.
    """
    payload = [{"id": esp_id, "effect": effect, "r": r, "g": g, "b": b}]

    # Broadcasts the JSON array to all connected ESPs
    await effect_manager.broadcast(json.dumps(payload))


calibration = HomographyManager()

async def broadcast_to_frontends(data: dict):
    if not frontend_clients:
        return
    message = json.dumps(data)
    await asyncio.gather(
        *[client.send_text(message) for client in frontend_clients],
        return_exceptions=True,
    )


async def default_on_turn_end(
    circles: Dict[int, np.ndarray], history: TurnHistory, in_frame_ids: Set[int]
):
    turn_count = history.turns[-1].turn_number if history.turns else 0

    circles_list = []
    for cid, pos in circles.items():
        ctype = turn_manager.circle_types.get(int(cid))
        meta = TYPE_METADATA.get(ctype) if ctype else None
        circles_list.append({
            "id": int(cid),
            "x": float(pos[0]),
            "y": float(pos[1]),
            "type": ctype,
            "color": meta["color"] if meta else (255, 255, 255),
            "effect": meta["effect"] if meta else 1
        })

    await broadcast_to_frontends(
        {
            "type": "turn_change",
            "turn_number": turn_count,
            "player": turn_manager.get_current_player(),
            "circles": circles_list,
            "scores": turn_manager.get_scores(),
        }
    )


async def default_on_turn_setup():
    logger.info("Setting up turn...")
    # Trigger set_circle_effect for all circles
    for cid, ctype in turn_manager.circle_types.items():
        meta = TYPE_METADATA.get(ctype)
        if meta:
            try:
                # meta['color'] is a tuple like (255, 255, 255)
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    if calibration.load():
        logger.info("Calibration loaded successfully")
    else:
        logger.warning(
            "No calibration found. Use frontend Calibrate button or "
            "POST /api/calibrate to calibrate."
        )

    async def effect_loop():
        # Setup initial turn state
        await turn_manager.start_turn()

        while True:
            await asyncio.sleep(10)
            # Example call: Set ESP 1 to rainbow effect (4) every 10 seconds
            # await set_circle_effect(esp_id=1, effect=4)

    asyncio.create_task(effect_loop())




@app.post("/api/calibrate")
async def calibrate():
    circles = calibration.get_last_n_circles(4)
    if len(circles) < 4:
        return {"status": "error", "message": f"need 4 circles, have {len(circles)}"}

    H = calibration.compute_from_corners(circles)
    calibration.save(H, circles, datetime.now().isoformat())

    logger.info("Calibration complete!")

    return {
        "status": "ok",
        "message": "calibration saved",
        "screen_points": circles.tolist(),
    }


@app.post("/api/calibrate/reset")
async def calibrate_reset():
    calibration.reset()
    logger.info("Calibration reset")
    return {"status": "ok", "message": "calibration reset"}


@app.post("/api/turn/end")
async def end_turn():
    await turn_manager.end_turn()
    await turn_manager.start_turn()
    return {"status": "ok", "turn": turn_manager.turn_count}


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
        logger.warning("/api/tracker: no calibration, passing scaled coords")
        screen_circles = [
            Circle(id=c.id, x=c.x / 3000.0, y=c.y / 4000.0) for c in circles
        ]
        turn_manager.update(screen_circles)
        circles_list = []
        for c in circles:
            ctype = turn_manager.circle_types.get(c.id)
            meta = TYPE_METADATA.get(ctype) if ctype else None
            circles_list.append({
                "id": c.id,
                "x": c.x / 3000.0,
                "y": c.y / 4000.0,
                "type": ctype,
                "color": meta["color"] if meta else (255, 255, 255),
                "effect": meta["effect"] if meta else 1
            })
        await broadcast_to_frontends(
            {
                "type": "positions",
                "circles": circles_list,
            }
        )
        return {"status": "error", "message": "not calibrated"}

    screen_pts = np.array([[c.x, c.y] for c in circles], dtype=np.float32)
    uv_pts = calibration.transform_batch(screen_pts)

    circle_objs = [
        Circle(id=c.id, x=float(uv_pts[i, 0]), y=float(uv_pts[i, 1]))
        for i, c in enumerate(circles)
    ]

    logger.info(
        f"POST /api/tracker: received {len(circles)} circles: [{', '.join(f'id={c.id} x={c.x:.0f} y={c.y:.0f}' for c in circles)}] -> "
        f"[{', '.join(f'id={c.id} x={uv_pts[i, 0]:.4f} y={uv_pts[i, 1]:.4f}' for i, c in enumerate(circles))}]"
    )

    turn_manager.update(circle_objs)

    circles_list = []
    for i, c in enumerate(circles):
        ctype = turn_manager.circle_types.get(c.id)
        meta = TYPE_METADATA.get(ctype) if ctype else None
        circles_list.append({
            "id": c.id,
            "x": float(uv_pts[i, 0]),
            "y": float(uv_pts[i, 1]),
            "type": ctype,
            "color": meta["color"] if meta else (255, 255, 255),
            "effect": meta["effect"] if meta else 1
        })

    await broadcast_to_frontends(
        {
            "type": "positions",
            "circles": circles_list,
        }
    )
    return {"status": "ok", "circles_count": len(circles_list)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    frontend_clients.append(websocket)

    current_state = turn_manager.get_current_state()
    in_frame_ids = turn_manager.get_in_frame_ids()
    if current_state:
        circles_list = [
            {
                "id": cid,
                "x": float(pos[0]),
                "y": float(pos[1]),
                "in_frame": cid in in_frame_ids,
            }
            for cid, pos in current_state.items()
        ]
        await websocket.send_text(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "circles": circles_list,
                }
            )
        )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        frontend_clients.remove(websocket)


@app.websocket("/ws/device")
async def device_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Device connected")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Device disconnected")


@app.websocket("/ws/effects")
async def effects_websocket_endpoint(websocket: WebSocket):
    await effect_manager.connect(websocket)
    logger.info("ESP LED client connected")
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        effect_manager.disconnect(websocket)
        logger.info("ESP LED client disconnected")

""" @app.get("/health")
def health():
    return PlainTextResponse("ok")
 """

""" @app.get("/api/game/state")
async def get_game_state():
    current = turn_manager.get_current_state()
    return {
        "turn_count": turn_manager.turn_count,
        "current_state": {
            cid: {"id": cid, "x": float(pos[0]), "y": float(pos[1])}
            for cid, pos in current.items()
        },
        "in_frame_ids": list(turn_manager.get_in_frame_ids()),
        "history": turn_manager.get_history().model_dump(),
    }
 """

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()