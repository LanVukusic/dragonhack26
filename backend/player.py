class Player:
    def __init__(self, id: int):
        self.id = id
        self.score = 0

    def add_score(self, points: int = 1) -> None:
        self.score += points

    def get_score(self) -> int:
        return self.score


NUM_PLAYERS = 4
