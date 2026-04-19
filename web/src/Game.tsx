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
    <div className="rounded-2xl bg-white w-screen h-screen relative flex flex-col overflow-hidden ">
      <div className="px-4 py-2 flex flex-row gap-4 justify-between items-center ">
        <div className="flex gap-4 items-start flex-col">
          <span className="text-lg font-bold">Turn: {turnNumber + 1}</span>
        </div>
        <div className="flex gap-4 items-center">
          {turnNumber == 0 && (
            <button
              onClick={endTurn}
              className="bg-slate-950 hover:bg-slate-700 cursor-pointer text-white px-4 py-1 rounded-lg font-medium transition-colors"
            >
              START
            </button>
          )}
          <span
            className="font-medium text-xs"
            style={{
              color: connected ? "green" : "red",
            }}
          >
            {connected ? "connected" : "disconnected"}
          </span>
        </div>
      </div>

      <div className="absolute pt-32 right-0 pr-8 flex flex-col items-end">
        {Object.entries(scores).map(([p, s]) => (
          <div className="flex gap-6">
            {currentPlayer.toString() == p && (
              <button
                onClick={endTurn}
                className="bg-slate-100 hover:bg-slate-200 cursor-pointer text-slate-600 px-4 py-1 rounded-lg font-medium transition-colors"
              >
                End Turn
              </button>
            )}
            <div className="py-3">
              <div className="text-3xl">{`Player ${p}`}</div>
              <div className="text-5xl">{`${s}`}</div>
            </div>
          </div>
        ))}
        <span className="text-4xl text-gray-600"></span>
      </div>

      <div className="absolute  w-full top-0 p-8 flex flex-col items-center gap-3">
        <span className="text-6xl tracking-tight">Dragonsmack</span>
        <span className="text-md tracking-normal opacity-70">Vision based interactive hokey</span>
      </div>

      <div className="absolute pt-32 left-0 bottom-0 p-8 flex flex-col items-start">
        <div className="flex gap-3 justify-center items-center">
          <div className="bg-red-500 w-6 h-6 rounded-full"></div>
          <div className="bg-red-500 w-6 h-6 rounded-full opacity-0"></div>
          <span className="font-bold text-2xl text-slate-700">-100 Points</span>
        </div>

        <div className="flex gap-3 justify-center items-center">
          <div className="bg-purple-600 w-6 h-6 rounded-full"></div>
          <div className="bg-purple-600 w-6 h-6 rounded-full"></div>
          <span className="font-bold text-2xl text-slate-700">+ points based on the gap</span>
        </div>

        <div className="flex gap-3 justify-center items-center">
          <div className="bg-cyan-300 w-6 h-6 rounded-full"></div>
          <div className="bg-cyan-300 w-6 h-6 rounded-full opacity-0"></div>
          <span className="font-bold text-2xl text-slate-700">+ 100 Points</span>
        </div>

        <div className="flex gap-3 justify-center items-center">
          <div className="bg-gray-300 w-6 h-6 rounded-full"></div>
          <div className="bg-gray-300 w-6 h-6 rounded-full opacity-0"></div>
          <span className="font-bold text-2xl text-slate-700">Hit this puck</span>
        </div>
      </div>

      <div className="h-full p-4 pl-24 pt-24">
        <ResponsiveStage>
          {circles.length > 0 && <CircleRenderer circles={circles} />}
        </ResponsiveStage>
      </div>
    </div>
  );
};
