import logging
import time
from datetime import datetime
import random
from typing import Awaitable, Callable, Dict, List, Optional, Set
import numpy as np

from backend.player import Player
from backend.dtos import Circle, CircleRecord, TurnHistory, TurnRecord, CircleType

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
        collision_threshold: float = 0.02,
        points_bonus: int = 100,
        points_harm: int = -100,
        points_no_move: int = -300,
        min_move_dist: float = 0.2,
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
        new_circle_detected = False
        for circle in circles:
            new_pos = np.array([circle.x, circle.y])
            self.circle_positions[circle.id] = new_pos
            self.circle_last_seen[circle.id] = now
            if circle.id not in self.circle_ids:
                self.circle_ids.add(circle.id)
                new_circle_detected = True
                logger.info(f"New circle detected: {circle.id}")
        
        # If this is the start of the game (first circles), start the turn
        if new_circle_detected and not self.circle_types:
            asyncio.create_task(self.start_turn())

    async def start_turn(self):
        """Setup for a new turn."""
        self._assign_circle_types()

        if self._on_turn_setup:
            try:
                await self._on_turn_setup()
            except Exception as e:
                logger.error(f"Turn setup callback error: {e}", exc_info=True)
        logger.info(f"--- STARTING TURN {self.turn_count + 1} ---")

    def _assign_circle_types(self):
        """Assign types to all current circles."""
        ids = list(self.circle_ids)
        if not ids:
            return

        random.shuffle(ids)
        
        # 1 Hitter, 2 Gates, rest split
        self.circle_types = {}
        
        # Hitter
        self.circle_types[ids.pop()] = CircleType.HITTER
        
        # Gates
        if ids:
            self.circle_types[ids.pop()] = CircleType.GATE
        if ids:
            self.circle_types[ids.pop()] = CircleType.GATE
        
        # Others
        for cid in ids:
            self.circle_types[cid] = random.choice([CircleType.BONUS, CircleType.HARM])
        
        logger.info(f"Assigned circle types: {self.circle_types}")

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
                    type=self.circle_types.get(cid, CircleType.HITTER),
                )
                for cid in sorted(self.circle_ids)
                if cid in self.circle_positions
            ],
        )
        self.history.turns.append(turn_record)

        # Compute scores
        prev_positions = self.history.turns[-2].circles if len(self.history.turns) > 1 else None
        if prev_positions:
            self._compute_turn_scores(prev_positions)

        # Notify callback
        if self._on_turn_end:
            try:
                await self._on_turn_end(self.circle_positions, self.history, in_frame_ids)
            except Exception as e:
                logger.error(f"Turn end callback error: {e}", exc_info=True)

    def _compute_turn_scores(self, prev_positions: List[CircleRecord]):
        """Compute scores for the current player."""
        player = self._players[self.get_current_player()]
        
        hitter_id = next((cid for cid, ctype in self.circle_types.items() if ctype == CircleType.HITTER), None)
        if not hitter_id or hitter_id not in self.circle_positions: return

        # 1. Hitter movement penalty
        prev_hitter = next((c for c in prev_positions if c.id == hitter_id), None)
        if not prev_hitter or np.linalg.norm(self.circle_positions[hitter_id] - np.array([prev_hitter.x, prev_hitter.y])) < self.min_move_dist:
            player.add_score(self.points_no_move)
            logger.info(f"Player {player.id} penalized: hitter did not move ({self.points_no_move})")
            return

        # 2. Collision score
        self._check_collisions(player, hitter_id)
        
        # 3. Gate score
        self._check_gate_pass(player, hitter_id, prev_positions)

    def _check_collisions(self, player: Player, hitter_id: int):
        hitter_pos = self.circle_positions[hitter_id]
        
        for cid, pos in self.circle_positions.items():
            if cid == hitter_id: continue
            
            if np.linalg.norm(pos - hitter_pos) < self.collision_threshold:
                ctype = self.circle_types.get(cid)
                if ctype == CircleType.BONUS:
                    player.add_score(self.points_bonus)
                    logger.info(f"Player {player.id} hit bonus: +{self.points_bonus}")
                elif ctype == CircleType.HARM:
                    player.add_score(self.points_harm)
                    logger.info(f"Player {player.id} hit harm: {self.points_harm}")

    def _check_gate_pass(self, player: Player, hitter_id: int, prev_positions: List[CircleRecord]):
        gate_ids = [cid for cid, ctype in self.circle_types.items() if ctype == CircleType.GATE]
        if len(gate_ids) != 2: return
        
        prev_pos_map = {c.id: np.array([c.x, c.y]) for c in prev_positions}
        # Filter both to only ids present in both
        common_ids = sorted(list(self.circle_ids.intersection(set(prev_pos_map.keys()))))
        if not common_ids: return
        
        A = np.array([prev_pos_map[cid] for cid in common_ids])
        B = np.array([self.circle_positions[cid] for cid in common_ids])
        
        h_idx_in_common = common_ids.index(hitter_id)
        g_idxs_in_common = [common_ids.index(gid) for gid in gate_ids]
        
        logger.info(f"Gate check: ids={common_ids}, h_idx={h_idx_in_common}, g_idxs={g_idxs_in_common}")
        
        if self._did_hitter_move_between_gates(A, B, g_idxs_in_common, h_idx_in_common):
            dist = np.linalg.norm(B[g_idxs_in_common[0]] - B[g_idxs_in_common[1]])
            points = int(max(30, 200 - dist / 10))
            player.add_score(points)
            logger.info(f"Player {player.id} passed gate: +{points}")
        else:
            logger.info(f"Player {player.id} failed gate pass check")
            
    def _did_hitter_move_between_gates(self, A, B, gate_indices, hitter_index, tol=1e-8):
        """Determines if the hitter point lies on the line segment between the two gates."""
        A = np.asarray(A)
        B = np.asarray(B)
        
        # Extract points from the final state
        g1 = B[gate_indices[0]]
        g2 = B[gate_indices[1]]
        h_final = B[hitter_index]
        
        # Verify the hitter actually moved
        if np.linalg.norm(h_final - A[hitter_index]) < tol:
            return False
            
        # Vectors
        v = g2 - g1          # Gate segment direction
        w = h_final - g1     # Vector from gate1 to hitter
        
        v_len_sq = np.dot(v, v)
        
        # Handle degenerate case where both gates occupy the same position
        if v_len_sq < tol:
            return np.linalg.norm(h_final - g1) < tol
            
        # Projection parameter t: where the hitter's perpendicular projection falls along the gate segment
        t = np.dot(w, v) / v_len_sq
        
        # 1. Check if projection lies within segment bounds [0, 1]
        if t < -tol or t > 1.0 + tol:
            return False
            
        # 2. Check if hitter is actually on the line (perpendicular distance)
        projection = g1 + t * v
        dist_to_segment = np.linalg.norm(h_final - projection)
        
        return dist_to_segment < tol

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
