import { useEffect, useState, useRef } from "react";
import type { CircleData, WebSocketMessage } from "./types/websocket";
import { CircleRenderer } from "./components/CircleRenderer";
import { ResponsiveStage } from "./components/ResponsiveStage";

function App() {
  const [connected, setConnected] = useState(false);
  const [circles, setCircles] = useState<CircleData[]>([]);
  const [calibrated, setCalibrated] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const API_HOST = `${window.location.hostname}:8000`;

  useEffect(() => {
    const wsUrl = `ws://${API_HOST}/ws`;

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

  const handleCalibrate = async () => {
    setCalibrating(true);
    try {
      const res = await fetch(`${API_HOST}/api/calibrate`, { method: "POST" });
      const text = await res.text();
      if (!text) {
        alert("Empty response from server");
        setCalibrating(false);
        return;
      }
      const data = JSON.parse(text);
      if (data.status === "ok") {
        setCalibrated(true);
        alert("Calibration saved!");
      } else {
        alert(data.message || "Calibration failed");
      }
    } catch (e) {
      alert("Calibration failed: " + e);
    }
    setCalibrating(false);
  };

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_HOST}/api/calibration/status`);
        const text = await res.text();
        if (!text) return;
        const data = JSON.parse(text);
        setCalibrated(data.calibrated);
      } catch {
        setCalibrated(false);
      }
    };
    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-950 p-3 overflow-hidden w-screen h-screen">
      <div className="rounded-2xl bg-white w-full h-full relative">
        <div className="px-4 py-2 flex flex-row gap-4 justify-between">
          <div className="flex gap-2 items-center">
            <button type="button" className="px-4 py-2">
              New game
            </button>
            {circles.length}
            {!calibrated && (
              <button
                type="button"
                className="px-4 py-2 bg-yellow-500 text-white"
                onClick={handleCalibrate}
                disabled={calibrating}
              >
                {calibrating ? "Calibrating..." : "Calibrate"}
              </button>
            )}
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
