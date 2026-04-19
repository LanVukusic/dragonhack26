from pydantic import BaseModel
from typing import List

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
