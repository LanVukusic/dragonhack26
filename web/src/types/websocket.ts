export interface CircleData {
  id: number;
  x: number;
  y: number;
}

export interface PositionMessage {
  type: "positions";
  circles: CircleData[];
}

export interface TurnChangeMessage {
  type: "turn_change";
  turn_number: number;
  player: number;
  circles: CircleData[];
  scores: Record<number, number>;
}

export type WebSocketMessage = PositionMessage | TurnChangeMessage;