import { useEffect, useState, useMemo, useRef } from "react";
import type { CircleData, WebSocketMessage } from "./types/websocket";
import { CircleRenderer } from "./components/CircleRenderer";
import { ResponsiveStage } from "./components/ResponsiveStage";

function App() {
  const [connected, setConnected] = useState(false);
  const [circles, setCircles] = useState<CircleData[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const port = window.location.port;
    const wsHost = ["5173", "5174", "3000", "5175"].includes(port) ? "localhost:8000" : window.location.host;
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
        if (data.circles) {
          setCircles(data.circles);
        }
      } catch (e) {
        console.error("Failed to parse message:", e);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const circleElements = useMemo(() => {
    return circles.map(circle => ({
      id: circle.id,
      x: circle.x,
      y: circle.y,
      in_frame: circle.in_frame
    }));
  }, [circles]);

  return (
    <div className="bg-slate-950 p-3 overflow-hidden w-screen h-screen">
      <div className="rounded-2xl bg-white w-full h-full relative">
        <div className="px-4 py-2 flex flex-row gap-4 justify-between">
          <div className="flex gap-2">
            <button type="button" className="px-4 py-2"> New game </button>
          </div>
          <span
            style={{
              color: connected ? "green" : "red",
            }}
          >
            {connected ? "connected" : "disconnected"}
          </span>
        </div>
        <div className="w-full h-full">
          <ResponsiveStage>
            {circles.length > 0 && <CircleRenderer circles={circleElements} />}
          </ResponsiveStage>
        </div>
      </div>
    </div>
  );
}

export default App;
