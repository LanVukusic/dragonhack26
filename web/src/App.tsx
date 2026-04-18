import { useEffect, useState } from "react";
import type { CircleData, WebSocketMessage } from "./types/websocket";
import { CircleRenderer } from "./components/CircleRenderer";
import { ResponsiveStage } from "./components/ResponsiveStage";

function App() {
  const [connected, setConnected] = useState(false);
  const [circles, setCircles] = useState<CircleData[]>([]);

  useEffect(() => {
    // Use same host in prod, localhost:8000 for common dev ports
    const port = window.location.port;
    const wsHost = ["5173", "5174", "3000", "5175"].includes(port) ? "localhost:8000" : window.location.host;
    const wsUrl = `ws://${wsHost}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected!");
      setConnected(true);
    };
    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setConnected(false);
    };
    ws.onerror = (e) => {
      console.log("WebSocket error:", e);
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
            {circles.length > 0 && <CircleRenderer circles={circles} />}
          </ResponsiveStage>
        </div>
      </div>
    </div>
  );
}

export default App;
