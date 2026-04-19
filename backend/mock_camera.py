import asyncio
import logging
import random
import sys
from datetime import datetime
from typing import Dict

import aiohttp
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Internal: UV space (0-1)
UPDATE_INTERVAL = 0.1
BURST_DURATION = 0.5
SETTLE_DURATION = 2.0
MOVE_DISTANCE_MIN = 0.1  # 10% of field
MOVE_DISTANCE_MAX = 0.3  # 30% of field
JIGGLE_AMOUNT = 0.003  # noise in UV space
NUM_CIRCLES = 4

# Screen: output transformation
SCREEN_WIDTH = 4000
SCREEN_HEIGHT = 3000


class MockCameraService:
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.positions: Dict[int, np.ndarray] = {}
        self.state = "idle"
        self.active_circle_id: int = 0
        self.target: np.ndarray = np.zeros(2)

    def _uv_to_screen(self, uv: np.ndarray) -> np.ndarray:
        return np.array([uv[0] * SCREEN_WIDTH, uv[1] * SCREEN_HEIGHT], dtype=np.float64)

    def _init_circles(self):
        self.positions = {
            i: np.array(
                [
                    random.uniform(0.1, 0.9),
                    random.uniform(0.1, 0.9),
                ]
            )
            for i in range(NUM_CIRCLES)
        }
        logger.info(f"Initialized {NUM_CIRCLES} circles in UV space")

    def _get_random_target(self, circle_id: int) -> np.ndarray:
        current = self.positions[circle_id]
        angle = random.uniform(0, 2 * np.pi)
        distance = random.uniform(MOVE_DISTANCE_MIN, MOVE_DISTANCE_MAX)

        direction = np.array([np.cos(angle), np.sin(angle)])
        new_pos = current + direction * distance

        return np.clip(new_pos, 0.05, 0.95)

    def _clip_to_field(self):
        for cid in self.positions:
            self.positions[cid] = np.clip(self.positions[cid], 0.05, 0.95)

    async def _send_update(self):
        screen_positions = {
            cid: self._uv_to_screen(pos) for cid, pos in self.positions.items()
        }
        pos_str = ", ".join(
            f"{cid}: ({pos[0]:.0f}, {pos[1]:.0f})"
            for cid, pos in screen_positions.items()
        )
        logger.info(f"Sending positions: {{{pos_str}}}")

        data = [
            {"id": int(cid), "x": float(pos[0]), "y": float(pos[1])}
            for cid, pos in screen_positions.items()
        ]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.backend_url}/api/tracker",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        logger.info(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Sent {len(data)} circles"
                        )
                    else:
                        logger.error(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Error: {resp.status}"
                        )
        except Exception as e:
            logger.error(
                f"[{datetime.now().strftime('%H:%M:%S')}] Connection error: {e}"
            )

    async def _do_burst(self):
        num_steps = int(BURST_DURATION / UPDATE_INTERVAL)

        candidates = [
            cid for cid in self.positions.keys() if cid != self.active_circle_id
        ]
        if candidates:
            self.active_circle_id = random.choice(candidates)
        else:
            self.active_circle_id = random.choice(list(self.positions.keys()))

        self.target = self._get_random_target(self.active_circle_id)
        start = self.positions[self.active_circle_id].copy()
        step = (self.target - start) / num_steps

        for _ in range(num_steps):
            self.positions[self.active_circle_id] += step
            for cid in self.positions:
                if cid != self.active_circle_id:
                    self.positions[cid] += np.random.uniform(
                        -JIGGLE_AMOUNT, JIGGLE_AMOUNT, 2
                    )
            self._clip_to_field()
            await self._send_update()
            await asyncio.sleep(UPDATE_INTERVAL)

    async def _do_settle(self):
        num_steps = int(SETTLE_DURATION / UPDATE_INTERVAL)

        for _ in range(num_steps):
            for cid in self.positions:
                self.positions[cid] += np.random.uniform(
                    -JIGGLE_AMOUNT / 2, JIGGLE_AMOUNT / 2, 2
                )
            self._clip_to_field()
            await self._send_update()
            await asyncio.sleep(UPDATE_INTERVAL)

    async def continuous_mode(self):
        print("Mode 1: burst then settle, Ctrl+C to stop")
        self._init_circles()

        try:
            while True:
                logger.info(f"Burst: moving circle {self.active_circle_id}")
                await self._do_burst()
                logger.info("Settling...")
                await self._do_settle()
        except asyncio.CancelledError:
            logger.info("Stopped continuous mode")

    async def hockey_mode(self):
        print("Mode 3: Real hockey simulation")
        self._init_circles()

        try:
            while True:
                active = random.choice(list(self.positions.keys()))
                logger.info(f"Hockey hit: puck {active}")

                target = self._get_random_target(active)
                start = self.positions[active].copy()
                distance = np.linalg.norm(target - start)

                burst_steps = 3
                for i in range(burst_steps):
                    t = (i + 1) / burst_steps
                    self.positions[active] = start + (target - start) * t
                    await self._send_update()
                    await asyncio.sleep(0.05)

                friction = 0.7
                current_pos = self.positions[active].copy()
                for _ in range(15):
                    self.positions[active] = current_pos
                    current_pos = current_pos * friction + target * (1 - friction)
                    if np.linalg.norm(current_pos - target) > 0.005:
                        break
                    await self._send_update()
                    await asyncio.sleep(UPDATE_INTERVAL)

                await asyncio.sleep(1.5)
        except asyncio.CancelledError:
            logger.info("Stopped hockey mode")

    async def missed_detection_mode(self):
        print("Mode 4: Missed detection simulation")
        self._init_circles()

        skip_chance = 0.3

        try:
            while True:
                data = []
                for cid, pos in self.positions.items():
                    if random.random() > skip_chance:
                        screen_pos = self._uv_to_screen(pos)
                        data.append(
                            {
                                "id": int(cid),
                                "x": float(screen_pos[0]),
                                "y": float(screen_pos[1]),
                            }
                        )
                    else:
                        logger.warning(f"Missed detection: circle {cid}")

                if data:
                    await self._send_update_custom(data)
                else:
                    logger.warning("All circles missed this frame!")

                await asyncio.sleep(UPDATE_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Stopped missed detection mode")

    async def motion_blur_mode(self):
        print("Mode 5: Motion blur simulation")
        self._init_circles()

        try:
            while True:
                active = random.choice(list(self.positions.keys()))
                current = self.positions[active].copy()

                jump_distance = random.uniform(0.4, 0.6)
                angle = random.uniform(0, 2 * np.pi)
                jump_target = (
                    current + np.array([np.cos(angle), np.sin(angle)]) * jump_distance
                )
                jump_target = np.clip(jump_target, 0.05, 0.95)

                logger.warning(
                    f"Motion blur: circle {active} jumping {jump_distance:.3f}"
                )

                self.positions[active] = jump_target
                await self._send_update()
                await asyncio.sleep(UPDATE_INTERVAL * 2)

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Stopped motion blur mode")

    async def collision_mode(self):
        print("Mode 6: Collision simulation")
        self._init_circles()

        ids = list(self.positions.keys())

        try:
            while True:
                c1, c2 = random.sample(ids, 2)

                p1 = self.positions[c1].copy()
                p2 = self.positions[c2].copy()

                mid = (p1 + p2) / 2

                direction = p2 - p1
                if np.linalg.norm(direction) > 0:
                    direction = direction / np.linalg.norm(direction)

                push_distance = random.uniform(0.1, 0.2)
                new_p1 = p1 - direction * push_distance
                new_p2 = p2 + direction * push_distance

                self.positions[c1] = new_p1
                self.positions[c2] = new_p2

                logger.info(f"Collision: pucks {c1} and {c2} pushed")
                await self._send_update()
                await asyncio.sleep(UPDATE_INTERVAL)

                await self._do_settle()
        except asyncio.CancelledError:
            logger.info("Stopped collision mode")

    async def calibration_test_mode(self):
        print("Mode 7: Calibration test - square in center")
        cx, cy = 0.5, 0.5
        half = 0.25  # Half of half = quarter, so full width is 0.5 = 50% of screen
        self.positions = {
            0: np.array([cx - half, cy - half]),
            1: np.array([cx + half, cy - half]),
            2: np.array([cx + half, cy + half]),
            3: np.array([cx - half, cy + half]),
        }
        logger.info(f"Calibration square: center={cx, cy} half={half}")
        logger.info(
            f"Screen coords: {[[int(p[0] * SCREEN_WIDTH), int(p[1] * SCREEN_HEIGHT)] for p in self.positions.values()]}"
        )
        await self._send_update()

    async def _send_update_custom(self, data):
        pos_str = ", ".join(f"{d['id']}: ({d['x']:.0f}, {d['y']:.0f})" for d in data)
        logger.info(f"Sending positions: {{{pos_str}}}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.backend_url}/api/tracker",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        logger.info(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Sent {len(data)} circles"
                        )
                    else:
                        logger.error(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Error: {resp.status}"
                        )
        except Exception as e:
            logger.error(
                f"[{datetime.now().strftime('%H:%M:%S')}] Connection error: {e}"
            )

    async def interactive_mode(self):
        print("Mode 2: Interactive - press Enter to transmit, q to quit")
        self._init_circles()
        await self._send_update()

        try:
            while True:
                print("\nPress Enter to transmit or 'q' to quit...")
                line = await asyncio.get_event_loop().run_in_executor(None, input, "")

                if line.strip().lower() == "q":
                    print("Quit interactive mode")
                    break
                elif line.strip() == "":
                    # Add small jitter in UV space
                    for cid in self.positions:
                        self.positions[cid] += np.random.uniform(-0.02, 0.02, 2)
                    self._clip_to_field()
                    await self._send_update()
        except Exception as e:
            logger.error(f"Error: {e}")


async def main():
    service = MockCameraService()

    print("=" * 40)
    print("Mock Camera Service")
    print("=" * 40)
    print("Modes:")
    print("  [1] Continuous - burst then settle (default)")
    print("  [2] Interactive - press Enter to transmit")
    print("  [3] Real hockey - realistic puck hits with friction")
    print("  [4] Missed detections - skip some circles occasionally")
    print("  [5] Motion blur - large jumps between frames")
    print("  [6] Collision - two pucks hit each other")
    print("  [7] Calibration test - square in center")
    print("  [q] Quit")
    print()

    while True:
        choice = input("Select mode: ").strip()

        if choice == "1":
            await service.continuous_mode()
        elif choice == "2":
            await service.interactive_mode()
        elif choice == "3":
            await service.hockey_mode()
        elif choice == "4":
            await service.missed_detection_mode()
        elif choice == "5":
            await service.motion_blur_mode()
        elif choice == "6":
            await service.collision_mode()
        elif choice == "7":
            await service.calibration_test_mode()
        elif choice.lower() == "q":
            print("Goodbye!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
