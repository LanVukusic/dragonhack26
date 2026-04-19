import logging
import time
from datetime import datetime
import random
from typing import Awaitable, Callable, Dict, List, Optional, Set
import numpy as np

from backend.player import Player
from backend.dtos import Circle, CircleRecord, TurnHistory, TurnRecord, CircleType

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TurnManager:
    def __init__(
        self,
        num_players: int = 2,
        missing_timeout_ms: float = 3000.0,
        collision_threshold: float = 0.05,  # Now: movement delta to register a "hit"
        points_bonus: int = 100,
        points_harm: int = -100,
        points_no_move: int = -300,
        min_move_dist: float = 0.015,       # Movement threshold for penalty/cheat detection
        on_turn_end: Optional[
            Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]]
        ] = None,
        on_turn_setup: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.missing_timeout_ms = missing_timeout_ms
        self.collision_threshold = collision_threshold
        self.points_bonus = points_bonus
        self.points_harm = points_harm
        self.points_no_move = points_no_move
        self.min_move_dist = min_move_dist
        self._on_turn_end = on_turn_end
        self._on_turn_setup = on_turn_setup
        self.NUM_PLAYERS = num_players

        # Circle state
        self.circle_positions: Dict[int, np.ndarray] = {}
        self.circle_last_seen: Dict[int, float] = {}
        self.circle_ids: Set[int] = set()
        self.circle_types: Dict[int, CircleType] = {}
        self.turn_start_positions: Dict[int, np.ndarray] = {}
        
        # Game state
        self.turn_count: int = 0
        self.history = TurnHistory()
        self._players: Dict[int, Player] = {
            i: Player(i) for i in range(1, self.NUM_PLAYERS + 1)
        }
        self._turn_start_pending = False

    def set_callbacks(
        self,
        on_turn_end: Callable[[Dict[int, np.ndarray], TurnHistory, Set[int]], Awaitable[None]],
        on_turn_setup: Callable[[], Awaitable[None]],
    ):
        self._on_turn_end = on_turn_end
        self._on_turn_setup = on_turn_setup

    def _is_in_frame(self, circle_id: int, now: float) -> bool:
        last_seen = self.circle_last_seen.get(circle_id)
        return last_seen is not None and (now - last_seen) * 1000 < self.missing_timeout_ms

    def _get_in_frame_ids(self, now: float) -> Set[int]:
        return {cid for cid in self.circle_ids if self._is_in_frame(cid, now)}

    def update(self, circles: List[Circle]) -> bool:
        now = time.time()
        new_circle_detected = False
        for circle in circles:
            new_pos = np.array([circle.x, circle.y])
            self.circle_positions[circle.id] = new_pos
            self.circle_last_seen[circle.id] = now
            if circle.id not in self.circle_ids:
                self.circle_ids.add(circle.id)
                new_circle_detected = True
                logger.info(f"New circle detected: {circle.id}")
        
        if new_circle_detected and not self.circle_types:
            self._turn_start_pending = True
            return True
        return False

    def has_pending_turn_start(self) -> bool:
        return self._turn_start_pending

    async def start_turn(self):
        self._turn_start_pending = False
        self._assign_circle_types()
        # Snapshot positions at turn start for movement comparison
        self.turn_start_positions = {cid: pos.copy() for cid, pos in self.circle_positions.items()}
        
        if self._on_turn_setup:
            try:
                await self._on_turn_setup()
            except Exception as e:
                logger.error(f"Turn setup callback error: {e}", exc_info=True)
        logger.info(f"--- STARTING TURN {self.turn_count + 1} ---")

    def _assign_circle_types(self):
        ids = list(self.circle_ids)
        if not ids:
            return
        random.shuffle(ids)
        self.circle_types = {}
        self.circle_types[ids.pop()] = CircleType.HITTER
        for cid in ids:
            self.circle_types[cid] = random.choice([CircleType.BONUS, CircleType.HARM])
        logger.info(f"Assigned types: {self.circle_types}")

    async def end_turn(self):
        # Score the player who JUST played
        prev_positions = self.history.turns[-1].circles if self.history.turns else None
        if prev_positions:
            self._compute_turn_scores(prev_positions)

        self.turn_count += 1
        logger.info(f"=== TURN {self.turn_count} ENDED ===")

        now = time.time()
        in_frame_ids = self._get_in_frame_ids(now)

        turn_record = TurnRecord(
            turn_number=self.turn_count,
            timestamp=datetime.now().isoformat(),
            circles=[
                CircleRecord(
                    id=cid,
                    x=float(self.circle_positions[cid][0]),
                    y=float(self.circle_positions[cid][1]),
                    in_frame=cid in in_frame_ids,
                    type=self.circle_types.get(cid, CircleType.HITTER),
                )
                for cid in sorted(self.circle_ids)
                if cid in self.circle_positions
            ],
        )
        self.history.turns.append(turn_record)

        if self._on_turn_end:
            try:
                await self._on_turn_end(self.circle_positions, self.history, in_frame_ids)
            except Exception as e:
                logger.error(f"Turn end callback error: {e}", exc_info=True)

    def _compute_turn_scores(self, prev_positions: List[CircleRecord]):
        player = self._players[self.get_current_player()]
        hitter_id = next((cid for cid, ctype in self.circle_types.items() if ctype == CircleType.HITTER), None)
        if not hitter_id:
            return

        # HITTER movement check
        hitter_start = self.turn_start_positions.get(hitter_id)
        hitter_end = self.circle_positions.get(hitter_id)
        hitter_moved = False
        if hitter_start is not None and hitter_end is not None:
            hitter_moved = np.linalg.norm(hitter_end - hitter_start) >= self.min_move_dist

        # Check all other circles for significant movement
        hit_detected = False
        scored_circles = []
        for cid, ctype in self.circle_types.items():
            if cid == hitter_id: continue
            start_pos = self.turn_start_positions.get(cid)
            end_pos = self.circle_positions.get(cid)
            if start_pos is None or end_pos is None: continue

            move_dist = np.linalg.norm(end_pos - start_pos)
            if move_dist >= self.collision_threshold:
                hit_detected = True
                scored_circles.append((cid, ctype))

        # CHEAT/PENALTY: Targets moved significantly, but HITTER didn't
        if not hitter_moved and hit_detected:
            player.add_score(self.points_no_move)
            print("SCORE: PENALTY")
            logger.warning(f"Player {player.id} penalized: HITTER stationary, targets moved")
            return

        # NORMAL SCORING: Award points for moved circles
        for cid, ctype in scored_circles:
            if ctype == CircleType.BONUS:
                player.add_score(self.points_bonus)
                print(f"SCORE: BONUS +{self.points_bonus}")
            elif ctype == CircleType.HARM:
                player.add_score(self.points_harm)
                print(f"SCORE: HARM {self.points_harm}")

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
