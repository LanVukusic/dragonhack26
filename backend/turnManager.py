import logging
import time
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, Set
import numpy as np

from backend.player import Player
from backend.dtos import Circle, CircleRecord, TurnHistory, TurnRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TurnManager:
    def __init__(
        self,
        num_players: int = 2,
        missing_timeout_ms: float = 3000.0,
        on_turn_end: Optional[
            Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]]
        ] = None,
        on_turn_setup: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.missing_timeout_ms = missing_timeout_ms
        self._on_turn_end = on_turn_end
        self._on_turn_setup = on_turn_setup
        self.NUM_PLAYERS = num_players

        # Circle state
        self.circle_positions: Dict[int, np.ndarray] = {}
        self.circle_last_seen: Dict[int, float] = {}
        self.circle_ids: Set[int] = set()
        
        # Game state
        self.turn_count: int = 0
        self.history = TurnHistory()
        self._players: Dict[int, Player] = {
            i: Player(i) for i in range(1, self.NUM_PLAYERS + 1)
        }

    def set_callbacks(
        self,
        on_turn_end: Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]],
        on_turn_setup: Callable[[], Awaitable[None]],
    ):
        """Set the async callbacks for turn events."""
        self._on_turn_end = on_turn_end
        self._on_turn_setup = on_turn_setup

    def _is_in_frame(self, circle_id: int, now: float) -> bool:
        last_seen = self.circle_last_seen.get(circle_id)
        return last_seen is not None and (now - last_seen) * 1000 < self.missing_timeout_ms

    def _get_in_frame_ids(self, now: float) -> Set[int]:
        return {cid for cid in self.circle_ids if self._is_in_frame(cid, now)}

    def update(self, circles: List[Circle]):
        now = time.time()
        for circle in circles:
            new_pos = np.array([circle.x, circle.y])
            self.circle_positions[circle.id] = new_pos
            self.circle_last_seen[circle.id] = now
            if circle.id not in self.circle_ids:
                self.circle_ids.add(circle.id)
                logger.info(f"New circle detected: {circle.id}")

    async def start_turn(self):
        """Setup for a new turn."""
        if self._on_turn_setup:
            try:
                await self._on_turn_setup()
            except Exception as e:
                logger.error(f"Turn setup callback error: {e}", exc_info=True)
        logger.info(f"--- STARTING TURN {self.turn_count + 1} ---")

    async def end_turn(self):
        """Manually end the current turn."""
        self.turn_count += 1
        logger.info(f"=== TURN {self.turn_count} ENDED ===")

        now = time.time()
        in_frame_ids = self._get_in_frame_ids(now)

        # Record turn
        turn_record = TurnRecord(
            turn_number=self.turn_count,
            timestamp=datetime.now().isoformat(),
            circles=[
                CircleRecord(
                    id=cid,
                    x=float(self.circle_positions[cid][0]),
                    y=float(self.circle_positions[cid][1]),
                    in_frame=cid in in_frame_ids,
                )
                for cid in sorted(self.circle_ids)
                if cid in self.circle_positions
            ],
        )
        self.history.turns.append(turn_record)

        # Notify callback
        if self._on_turn_end:
            try:
                await self._on_turn_end(self.circle_positions, self.history, in_frame_ids)
            except Exception as e:
                logger.error(f"Turn end callback error: {e}", exc_info=True)

    def get_current_state(self) -> Dict[int, np.ndarray]:
        return dict(self.circle_positions)

    def get_history(self) -> TurnHistory:
        return self.history

    def get_in_frame_ids(self) -> Set[int]:
        return self._get_in_frame_ids(time.time())

    def get_current_player(self) -> int:
        return ((self.turn_count) % self.NUM_PLAYERS) + 1

    def get_scores(self) -> Dict[int, int]:
        return {pid: p.get_score() for pid, p in self._players.items()}
