import asyncio
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
        turn_delay: float = 1.0,
        cumulative_movement_threshold: float = 0.1,
        min_movement_per_update: float = 0.05,
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

        # Circle state
        self.circle_positions: Dict[int, np.ndarray] = {}
        self.circle_last_seen: Dict[int, float] = {}
        self.circle_ids: Set[int] = set()
        
        # Turn state
        self.turn_start_positions: Dict[int, np.ndarray] = {}
        self.turn_movement: Dict[int, float] = {}
        
        # Game state
        self.turn_count: int = 0
        self.history = TurnHistory()
        self._players: Dict[int, Player] = {
            i: Player(i) for i in range(1, self.NUM_PLAYERS + 1)
        }
        
        # Stabilization state
        self._is_moving: bool = False
        self._stabilization_task: Optional[asyncio.Task] = None

    def set_on_turn_end_callback(
        self,
        callback: Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]],
    ):
        """Set the async callback for turn end events."""
        self._on_turn_end = callback

    def _is_in_frame(self, circle_id: int, now: float) -> bool:
        last_seen = self.circle_last_seen.get(circle_id)
        return last_seen is not None and (now - last_seen) * 1000 < self.missing_timeout_ms

    def _get_in_frame_ids(self, now: float) -> Set[int]:
        return {cid for cid in self.circle_ids if self._is_in_frame(cid, now)}

    def _cancel_stabilization(self):
        """Cancel pending turn-end check."""
        if self._stabilization_task and not self._stabilization_task.done():
            self._stabilization_task.cancel()
        self._stabilization_task = None

    async def _wait_for_settle(self):
        """Wait for movement to stop, then end turn."""
        try:
            await asyncio.sleep(self.turn_delay)
            if not self._is_moving:  # Double-check no movement occurred
                await self._end_turn()
        except asyncio.CancelledError:
            pass  # Expected when new movement cancels this task

    def update(self, circles: List[Circle]):
        now = time.time()

        # Process new/updated circles
        for circle in circles:
            new_pos = np.array([circle.x, circle.y])
            old_pos = self.circle_positions.get(circle.id)
            
            # Filter motion blur
            if old_pos is not None:
                delta = float(np.linalg.norm(new_pos - old_pos))
                if delta > self.motion_blur_threshold:
                    logger.warning(f"Circle {circle.id}: motion blur (Δ={delta:.1f}), skipping")
                    continue
            
            self.circle_positions[circle.id] = new_pos
            self.circle_last_seen[circle.id] = now
            
            if circle.id not in self.circle_ids:
                self.circle_ids.add(circle.id)
                self.turn_start_positions[circle.id] = new_pos.copy()
                self.turn_movement[circle.id] = 0.0
                logger.info(f"New circle: {circle.id}")

        # Calculate movement for all known circles
        for cid in list(self.circle_ids):
            pos = self.circle_positions.get(cid)
            if pos is None:
                continue
                
            # Init turn start if needed
            if cid not in self.turn_start_positions:
                self.turn_start_positions[cid] = pos.copy()
            
            # Cumulative movement this turn
            start = self.turn_start_positions[cid]
            cumulative = float(np.linalg.norm(pos - start))
            self.turn_movement[cid] = cumulative
            
            # Instant movement (for noise filtering)
            if cid in self.circle_positions and cid in [c.id for c in circles]:
                # Only check circles updated this frame
                pass  # cumulative check below handles this

        in_frame = self._get_in_frame_ids(now)
        
        # Detect significant movement
        has_significant_move = any(
            self.turn_movement.get(cid, 0) >= self.min_movement_per_update
            for cid in in_frame
        )
        has_cumulative_move = any(
            self.turn_movement.get(cid, 0) >= self.cumulative_movement_threshold
            for cid in in_frame
        )

        if has_significant_move or has_cumulative_move:
            # Movement detected - reset stabilization
            if not self._is_moving:
                logger.info("→ Movement started")
            self._is_moving = True
            self._cancel_stabilization()
        elif self._is_moving:
            # Movement stopped - start stabilization timer
            self._is_moving = False
            logger.info("→ Movement settled, waiting for turn end...")
            self._cancel_stabilization()
            self._stabilization_task = asyncio.create_task(self._wait_for_settle())

    async def _end_turn(self):
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

        # Log summary
        for cid in sorted(self.circle_ids):
            if cid not in self.circle_positions:
                continue
            pos = self.circle_positions[cid]
            status = "IN" if cid in in_frame_ids else "OUT"
            moved = self.turn_movement.get(cid, 0)
            logger.info(f"  Circle {cid}: ({pos[0]:.1f}, {pos[1]:.1f}) [{status}] Δ={moved:.1f}")

        # Reset for next turn
        self.turn_movement.clear()
        for cid in self.circle_ids:
            if cid in self.circle_positions:
                self.turn_start_positions[cid] = self.circle_positions[cid].copy()

        # Notify callback
        if self._on_turn_end:
            try:
                await self._on_turn_end(self.circle_positions, self.history, in_frame_ids)
            except Exception as e:
                logger.error(f"Turn end callback error: {e}", exc_info=True)

    # --- Getters (unchanged) ---
    def get_current_state(self) -> Dict[int, np.ndarray]:
        return dict(self.circle_positions)

    def get_history(self) -> TurnHistory:
        return self.history

    def get_in_frame_ids(self) -> Set[int]:
        return self._get_in_frame_ids(time.time())

    def get_current_player(self) -> int:
        return (self.turn_count % self.NUM_PLAYERS) + 1

    def get_scores(self) -> Dict[int, int]:
        return {pid: p.get_score() for pid, p in self._players.items()}
