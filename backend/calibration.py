import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MATRIX_FILE = "homography_matrix.json"
FLOOR_CORNERS = np.array(
    [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32
)


def _sort_corners_by_position(pts: np.ndarray) -> np.ndarray:
    """Order 4 points: top-left, top-right, bottom-right, bottom-left"""
    pts = pts.reshape(4, 2)
    s = pts.sum(axis=1)  # x+y
    diff = np.diff(pts, axis=1).flatten()  # x-y

    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]  # TL: min sum
    ordered[2] = pts[np.argmax(s)]  # BR: max sum
    ordered[1] = pts[np.argmin(diff)]  # TR: min diff (x-y)
    ordered[3] = pts[np.argmax(diff)]  # BL: max diff
    return ordered


class HomographyManager:
    def __init__(self, matrix_path: str = MATRIX_FILE, history_size: int = 100):
        self.matrix_path = matrix_path
        self.H: Optional[np.ndarray] = None
        self.screen_points: Optional[np.ndarray] = None
        self.created_at: Optional[str] = None
        self._circle_history: Dict[int, np.ndarray] = {}
        self._history_size = history_size

    def track_circle(self, circle_id: int, x: float, y: float) -> None:
        self._circle_history[circle_id] = np.array([x, y], dtype=np.float32)
        if len(self._circle_history) > self._history_size:
            oldest = next(iter(self._circle_history))
            del self._circle_history[oldest]

    def get_last_n_circles(self, n: int = 4) -> np.ndarray:
        recent = list(self._circle_history.values())[-n:]
        if len(recent) < n:
            return np.array([], dtype=np.float32).reshape(0, 2)
        return np.array(recent, dtype=np.float32)

    def get_tracked_count(self) -> int:
        return len(self._circle_history)

    def reset(self) -> None:
        self.H = None
        self.screen_points = None
        self.created_at = None
        self._circle_history.clear()

    def load(self) -> bool:
        path = Path(self.matrix_path)
        if not path.exists():
            logger.warning(f"No calibration matrix found at {self.matrix_path}")
            return False

        try:
            with open(path) as f:
                data = json.load(f)

            H_list = data["matrix"]
            self.H = np.array(H_list, dtype=np.float64)
            self.screen_points = np.array(data["screen_points"], dtype=np.float32)
            self.created_at = data.get("created_at")

            logger.info(f"Loaded homography matrix from {self.matrix_path}")
            logger.debug(f"Screen points: {self.screen_points.tolist()}")
            return True
        except Exception as e:
            logger.error(f"Failed to load calibration matrix: {e}")
            return False

    def save(self, H: np.ndarray, screen_points: np.ndarray, created_at: str) -> None:
        self.H = H
        self.screen_points = screen_points
        self.created_at = created_at

        data = {
            "matrix": H.tolist(),
            "screen_points": screen_points.tolist(),
            "created_at": created_at,
        }

        with open(self.matrix_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved homography matrix to {self.matrix_path}")

    def compute_from_corners(self, screen_pts: np.ndarray) -> np.ndarray:
        sorted_pts = _sort_corners_by_position(screen_pts)

        H, mask = cv2.findHomography(sorted_pts, FLOOR_CORNERS, cv2.RANSAC)

        if H is None:
            raise ValueError("Failed to compute homography matrix")

        errors = self._reprojection_error(sorted_pts, H)
        max_error = np.max(errors)
        logger.info(f"Computed homography: max reprojection error = {max_error:.4f}")

        if max_error > 0.1:
            logger.warning(
                f"High reprojection error ({max_error:.4f}). "
                "Calibration may be inaccurate."
            )

        return H

    def _reprojection_error(self, src_pts: np.ndarray, H: np.ndarray) -> np.ndarray:
        ones = np.ones((src_pts.shape[0], 1))
        src_h = np.hstack([src_pts, ones])

        dst_h = H @ src_h.T
        dst = (dst_h[:2] / dst_h[2]).T

        errors = np.linalg.norm(dst - FLOOR_CORNERS, axis=1)
        return errors

    def transform(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        if self.H is None:
            raise RuntimeError("Homography not loaded")

        pt = np.array([[screen_x, screen_y, 1.0]], dtype=np.float64).T
        res = self.H @ pt
        floor_x = float(res[0] / res[2])
        floor_y = float(res[1] / res[2])

        return floor_x, floor_y

    def transform_batch(self, screen_pts: np.ndarray) -> np.ndarray:
        if self.H is None:
            raise RuntimeError("Homography not loaded")

        ones = np.ones((screen_pts.shape[0], 1), dtype=np.float64)
        pts_h = np.hstack([screen_pts, ones]).T

        res = self.H @ pts_h
        floor_pts = (res[:2] / res[2]).T

        return floor_pts

    def is_calibrated(self) -> bool:
        return self.H is not None

    def get_screen_points(self) -> Optional[List[List[float]]]:
        if self.screen_points is None:
            return None
        return self.screen_points.tolist()
