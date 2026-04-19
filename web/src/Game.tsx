import { useEffect, useState, useRef } from "react";
import type { CircleData, WebSocketMessage } from "./types/websocket";
import { CircleRenderer } from "./components/CircleRenderer";
import { ResponsiveStage } from "./components/ResponsiveStage";

export const Game = () => {
  const [connected, setConnected] = useState(false);
  const [circles, setCircles] = useState<CircleData[]>([]);
  const [turnNumber, setTurnNumber] = useState(0);
  const [currentPlayer, setCurrentPlayer] = useState(1);
  const [scores, setScores] = useState<Record<number, number>>({});
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsHost = window.location.hostname + ":8000";
    const wsUrl = `ws://${wsHost}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
    };

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);

        // Handle new format: positions
        if (data.type === "positions" && data.circles) {
          setCircles(() =>
            data.circles.map((c) => ({
              ...c,
              x: c.x * 1000,
              y: c.y * 1000,
            })),
          );
        }
        // Handle new format: turn_change
        else if (data.type === "turn_change") {
          setTurnNumber(data.turn_number);
          setCurrentPlayer(data.player);
          setScores(data.scores);
          setCircles(() =>
            data.circles.map((c) => ({
              ...c,
              x: c.x * 1000,
              y: c.y * 1000,
            })),
          );
        }
      } catch (e) {
        console.error("Failed to parse message:", e);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const endTurn = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/turn/end", {
        method: "POST",
      });
      if (!response.ok) {
        console.error("Failed to end turn");
      }
    } catch (e) {
      console.error("Error ending turn:", e);
    }
  };

  return (
    <div className="bg-slate-950 p-3 overflow-hidden w-screen h-screen">
      <div className="rounded-2xl bg-white w-full h-full relative flex flex-col">
        <div className="px-4 py-2 flex flex-row gap-4 justify-between items-center border-b">
          <div className="flex gap-4 items-center">
            <span className="text-lg font-bold">
              Turn: {turnNumber+1} | Player: {currentPlayer}
            </span>
            <span className="text-sm text-gray-600">
              Scores:{" "}
              {Object.entries(scores)
                .map(([p, s]) => `P${p}:${s}`)
                .join(", ")}
            </span>
          </div>
          <div className="flex gap-4 items-center">
            <button
              onClick={endTurn}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1 rounded-lg font-medium transition-colors"
            >
              End Turn
            </button>
            <span
              className="font-medium"
              style={{
                color: connected ? "green" : "red",
              }}
            >
              {connected ? "connected" : "disconnected"}
            </span>
          </div>
        </div>
        <div className="flex-1 w-full h-full relative">
          <ResponsiveStage>
            {circles.length > 0 && <CircleRenderer circles={circles} />}
          </ResponsiveStage>
        </div>
      </div>
    </div>
  );
};
