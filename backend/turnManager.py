import asyncio
import logging
import time
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, Set
import numpy as np

from backend.player import Player
from backend.dtos import Circle,  CircleRecord, TurnHistory, TurnRecord


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TurnManager:
    def __init__(
        self,
        num_players:int = 2,
        turn_delay: float = 1.0,
        cumulative_movement_threshold: float = 10.0,
        min_movement_per_update: float = 2.0,
        missing_timeout_ms: float = 2000.0,
        motion_blur_threshold: float = 100.0,
        on_turn_end: Optional[
            Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]]
        ] = None,

    ):
        self.turn_delay = turn_delay
        self.cumulative_movement_threshold = cumulative_movement_threshold
        self.min_movement_per_update = min_movement_per_update
        self.missing_timeout_ms = missing_timeout_ms
        self.motion_blur_threshold = motion_blur_threshold
        self._on_turn_end = on_turn_end
        self.NUM_PLAYERS = num_players


        self.circle_last_position: Dict[int, np.ndarray] = {}
        self.circle_last_seen_time: Dict[int, float] = {}

        self.circle_ids: Set[int] = set()

        self.circle_prev_position: Dict[int, np.ndarray] = {}

        self.turn_start_positions: Dict[int, np.ndarray] = {}
        self.circle_movement_this_turn: Dict[int, float] = {}

        self.turn_count: int = 0
        self.history = TurnHistory()

        self._players: Dict[int, Player] = {
            i: Player(i) for i in range(1, self.NUM_PLAYERS + 1)
        }

        self._stabilization_task: Optional[asyncio.Task] = None
        self._last_movement_time: float = 0.0
        self._movement_detected: bool = False

    def set_on_turn_end_callback(
        self,
        callback: Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], None],
    ):
        self._on_turn_end = callback

    def _is_in_frame(self, circle_id: int) -> bool:
        last_seen = self.circle_last_seen_time.get(circle_id)
        if last_seen is None:
            return False
        return (time.time() - last_seen) * 1000 < self.missing_timeout_ms

    def _get_in_frame_ids(self) -> Set[int]:
        return {cid for cid in self.circle_ids if self._is_in_frame(cid)}

    def update(self, circles: List[Circle]):
        current_time = time.time()

        received_ids = set()
        for circle in circles:
            received_ids.add(circle.id)
            new_pos = np.array([circle.x, circle.y])

            prev_pos = self.circle_last_position.get(circle.id)
            if prev_pos is not None:
                consec_delta = float(np.linalg.norm(new_pos - prev_pos))
                if consec_delta > self.motion_blur_threshold:
                    logger.warning(
                        f"Circle {circle.id}: motion blur detected, "
                        f"delta={consec_delta:.4f} > {self.motion_blur_threshold:.4f}, ignoring"
                    )
                else:
                    self.circle_last_position[circle.id] = new_pos
            else:
                self.circle_last_position[circle.id] = new_pos

            self.circle_last_seen_time[circle.id] = current_time
            if circle.id not in self.circle_ids:
                self.circle_ids.add(circle.id)
                logger.info(f"New circle detected: {circle.id}")

        moved_circles = []
        for circle_id in self.circle_ids:
            current_pos = self.circle_last_position.get(circle_id)
            if current_pos is None:
                continue

            start_pos = self.turn_start_positions.get(circle_id)

            if start_pos is None:
                self.turn_start_positions[circle_id] = current_pos.copy()
                start_pos = self.turn_start_positions[circle_id]

            delta = float(np.linalg.norm(current_pos - start_pos))
            self.circle_movement_this_turn[circle_id] = delta

            logger.debug(
                f"Circle {circle_id}: pos=[{current_pos[0]:.4f},{current_pos[1]:.4f}], delta={delta:.4f} from turn start"
            )

            if delta >= self.min_movement_per_update:
                moved_circles.append(circle_id)

        in_frame = self._get_in_frame_ids()

        if moved_circles or any(
            self.circle_movement_this_turn.get(cid, 0)
            >= self.cumulative_movement_threshold
            for cid in in_frame
        ):
            self._movement_detected = True
            self._last_movement_time = current_time

            sorted_deltas = sorted(
                self.circle_movement_this_turn.items(), key=lambda x: x[1], reverse=True
            )
            logger.info(f"Movement check: moved={moved_circles}")
            for cid, delta in sorted_deltas:
                logger.info(f"  Circle {cid}: delta={delta:.4f}")

            if self._stabilization_task and not self._stabilization_task.done():
                self._stabilization_task.cancel()

            loop = asyncio.get_event_loop()
            self._stabilization_task = loop.create_task(self._check_turn_end())

    async def _check_turn_end(self):
        logger.info(f"Turn check: waiting {self.turn_delay}s since last movement...")
        await asyncio.sleep(self.turn_delay)

        current_time = time.time()
        time_since_movement = current_time - self._last_movement_time

        logger.info(
            f"Turn check: elapsed={time_since_movement:.2f}s, movement_detected={self._movement_detected}"
        )

        if time_since_movement >= self.turn_delay and self._movement_detected:
            await self._end_turn()
        else:
            logger.info("Turn check: no turn end (insufficient time or no movement)")

    async def _end_turn(self):
        self.turn_count += 1
        logger.info(f"=== TURN {self.turn_count} ENDED ===")

        in_frame_ids = self._get_in_frame_ids()

        turn_record = TurnRecord(
            turn_number=self.turn_count,
            timestamp=datetime.now().isoformat(),
            circles=[
                CircleRecord(
                    id=cid,
                    x=float(self.circle_last_position[cid][0]),
                    y=float(self.circle_last_position[cid][1]),
                    in_frame=cid in in_frame_ids,
                )
                for cid in self.circle_ids
            ],
        )
        self.history.turns.append(turn_record)

        logger.info(
            f"Recording turn {self.turn_count}: {len(self.history.turns)} total turns"
        )
        for cid in sorted(self.circle_ids):
            c = self.circle_last_position[cid]
            in_frame = "IN" if cid in in_frame_ids else "OUT"
            delta = self.circle_movement_this_turn.get(cid, 0)
            logger.info(
                f"  Circle {cid}: ({c[0]:.4f}, {c[1]:.4f}) {in_frame} frame, moved {delta:.4f} this turn"
            )

        self.circle_movement_this_turn.clear()
        self._movement_detected = False

        for cid in self.circle_ids:
            current = self.circle_last_position.get(cid)
            if current is not None:
                self.turn_start_positions[cid] = current.copy()

        if self._on_turn_end is not None:
            callback = self._on_turn_end
            await callback(self.circle_last_position, self.history, in_frame_ids)

    def get_current_state(self) -> Dict[int, np.ndarray]:
        return dict(self.circle_last_position)

    def get_history(self) -> TurnHistory:
        return self.history

    def get_in_frame_ids(self) -> Set[int]:
        return self._get_in_frame_ids()

    def get_current_player(self) -> int:
        return (self.turn_count % self.NUM_PLAYERS) + 1

    def get_scores(self) -> Dict[int, int]:
        return {pid: p.get_score() for pid, p in self._players.items()}
