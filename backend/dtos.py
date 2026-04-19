from pydantic import BaseModel
from typing import List, Dict, Tuple
from enum import Enum

class CircleType(str, Enum):
    HITTER = "hitter"
    GATE = "gate"
    BONUS = "bonus"
    HARM = "harm"

# Mapping types to (R, G, B) and effect ID (1-5)
TYPE_METADATA: Dict[CircleType, Dict] = {
    CircleType.HITTER: {"color": (255, 255, 255), "effect": 1},
    CircleType.GATE:   {"color": (0, 128, 255),   "effect": 2},
    CircleType.BONUS:  {"color": (0, 255, 128),   "effect": 3},
    CircleType.HARM:   {"color": (255, 64, 0),   "effect": 4},
}

class Circle(BaseModel):
    id: int
    x: float
    y: float
    moved: bool = False


class CircleInput(BaseModel):
    id: int
    x: float
    y: float


class CircleRecord(BaseModel):
    id: int
    x: float
    y: float
    in_frame: bool
    type: CircleType


class TurnRecord(BaseModel):
    turn_number: int
    timestamp: str
    circles: List[CircleRecord]


class TurnHistory(BaseModel):
    turns: List[TurnRecord] = []


class CalibrationInput(BaseModel):
    id: int
    x: float
    y: float
