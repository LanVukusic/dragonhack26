export interface CircleData {
  id: number;
  x: number;
  y: number;
  in_frame?: boolean;
}

export interface WebSocketMessage {
  timestamp?: string;
  circles: CircleData[];
}
