import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "react-router";

interface DeviceUpdate {
  id: number;
  x: number;
  y: number;
  rotation: number;
}

interface DeviceCommand {
  fx_id: number;
  color: number[];
}

interface DeviceState {
  id: number;
  x: number;
  y: number;
  rotation: number;
  color: number[];
}

interface LogEntry {
  id: number;
  message: string;
  timestamp: Date;
}

export const Device = () => {
  const { id } = useParams();
  const deviceId = id ? parseInt(id, 10) : 1;
  const wsRef = useRef<WebSocket | null>(null);
  const [device, setDevice] = useState<DeviceState | null>(null);

  useEffect(() => {
    if (deviceId) {
      setDevice({
        id: deviceId,
        x: 0,
        y: 0,
        rotation: 0,
        color: [255, 0, 0],
      });
    }
  }, [deviceId]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logIdRef = useRef(0);

  const addLog = useCallback((message: string) => {
    const entry: LogEntry = {
      id: ++logIdRef.current,
      message,
      timestamp: new Date(),
    };
    setLogs((prev) => [...prev.slice(-9), entry]);
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/device");
    wsRef.current = ws;

    ws.onopen = () => {
      addLog(`Device ${deviceId} connected`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if ("fx_id" in data) {
          const cmd: DeviceCommand = data;
          if (cmd.fx_id) {
            addLog(`fx_id: ${cmd.fx_id}`);
          }
          return;
        }

        if ("id" in data) {
          const update: DeviceUpdate = data as DeviceUpdate;
          if (update.id !== deviceId) {
            return;
          }
          setDevice((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              ...update,
            };
          });
        }
      } catch (e) {
        console.error("Failed to parse message:", e);
      }
    };

    ws.onclose = () => {
      addLog(`Device ${deviceId} disconnected`);
    };

    return () => {
      ws.close();
    };
  }, [addLog, deviceId]);

  const rgbColor = device
    ? `rgb(${device.color[0]}, ${device.color[1]}, ${device.color[2]})`
    : "rgb(255, 0, 0)";

  if (!device) {
    return <div className="p-5">Loading device {deviceId}...</div>;
  }

  return (
    <div className="flex gap-5 p-5">
      <div className="w-25 h-25" style={{ backgroundColor: rgbColor }} />
      <div className="font-mono text-xs bg-gray-100 p-2.5 w-75 max-h-50 overflow-y-auto">
        {logs.map((log) => (
          <div key={log.id}>
            {log.timestamp.toLocaleTimeString()} - {log.message}
          </div>
        ))}
      </div>
    </div>
  );
};
