import { useEffect, useMemo, useRef, useState } from "react";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

function Gauge({ label, value, min = 0, max = 100, unit = "", warn = 60, danger = 80 }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const dash = c * pct;
  let color = "#4ade80";
  if (value >= danger) color = "#f87171";
  else if (value >= warn) color = "#facc15";

  return (
    <div style={styles.gaugeCard}>
      <svg width="160" height="110" viewBox="0 0 140 100">
        <path d="M 15 85 A 55 55 0 0 1 125 85" fill="none" stroke="#2a3654" strokeWidth="12" strokeLinecap="round" />
        <path
          d="M 15 85 A 55 55 0 0 1 125 85"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
        />
      </svg>
      <div style={styles.gaugeValue}>{value.toFixed(1)}{unit}</div>
      <div style={styles.gaugeLabel}>{label}</div>
    </div>
  );
}

export default function MissionControl() {
  const [connected, setConnected] = useState(false);
  const [robotId, setRobotId] = useState("rover-cam-01");
  const [driveMode, setDriveMode] = useState("Manual");
  const [lastSeenAt, setLastSeenAt] = useState(null);
  const [telemetry, setTelemetry] = useState({
    speed: 0,
    battery: 100,
    temperature: 25,
    current: 0,
    pitch: 0,
    roll: 0,
    yaw: 0,
    latitude: 12.9716,
    longitude: 77.5946,
  });
  const [chartData, setChartData] = useState([]);
  const [path, setPath] = useState([]);
  const [commandInput, setCommandInput] = useState("/help");
  const [terminalLines, setTerminalLines] = useState(["ACE terminal ready. Type /help"]);
  const [wsTick, setWsTick] = useState(0);

  const mapCanvasRef = useRef(null);

  useEffect(() => {
    let ws;
    let retry;

    const connect = () => {
      ws = new WebSocket(WS);

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);

        if (payload.type === "command" && payload.command) {
          setTerminalLines((prev) => [...prev, `WS command: ${payload.command}`].slice(-60));
        }

        const robots = payload.robots || {};
        const keys = Object.keys(robots);
        if (!keys.length) return;

        const active = robots[robotId] || robots[keys[0]];
        if (!active) return;

        setRobotId(active.robot_id);
        setTelemetry((prev) => ({
          ...prev,
          ...active,
          temperature: active.motor_temp ?? active.temperature ?? prev.temperature,
        }));
        setLastSeenAt(new Date().toISOString());
        setWsTick((x) => x + 1);

        setChartData((prev) => {
          const next = [...prev, { t: prev.length + 1, current: active.current ?? 0 }];
          return next.slice(-60);
        });

        setPath((prev) => {
          const point = [active.latitude, active.longitude];
          const same = prev.length > 0 && prev[prev.length - 1][0] === point[0] && prev[prev.length - 1][1] === point[1];
          if (same) return prev;
          return [...prev, point].slice(-250);
        });
      };

      ws.onclose = () => {
        setConnected(false);
        retry = setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      if (retry) clearTimeout(retry);
      if (ws) ws.close();
    };
  }, [robotId]);

  useEffect(() => {
    const canvas = mapCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#071427";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "#16315d";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 30) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    if (path.length < 2) return;

    const lats = path.map((p) => p[0]);
    const lons = path.map((p) => p[1]);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);

    const mapPoint = ([lat, lon]) => {
      const x = ((lon - minLon) / ((maxLon - minLon) || 1)) * (w - 40) + 20;
      const y = h - (((lat - minLat) / ((maxLat - minLat) || 1)) * (h - 40) + 20);
      return [x, y];
    };

    ctx.beginPath();
    path.forEach((p, i) => {
      const [x, y] = mapPoint(p);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = 2;
    ctx.stroke();

    const [rx, ry] = mapPoint(path[path.length - 1]);
    ctx.beginPath();
    ctx.arc(rx, ry, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#f97316";
    ctx.fill();
  }, [path, wsTick]);

  const imu = useMemo(
    () => [
      { label: "Pitch", value: telemetry.pitch || 0 },
      { label: "Roll", value: telemetry.roll || 0 },
      { label: "Yaw", value: telemetry.yaw || 0 },
    ],
    [telemetry]
  );

  const startDemo = async () => {
    try {
      await fetch(`${API}/demo/start`);
      setTerminalLines((prev) => [...prev, "Demo stream started"].slice(-60));
    } catch {
      setTerminalLines((prev) => [...prev, "Failed to start demo"].slice(-60));
    }
  };

  const sendCommand = async () => {
    const body = {
      robot_id: robotId,
      secret_key: "ace-secret-key-123",
      command: commandInput,
    };

    try {
      const res = await fetch(`${API}/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setTerminalLines((prev) => [...prev, `> ${commandInput}`, JSON.stringify(data)].slice(-60));
    } catch {
      setTerminalLines((prev) => [...prev, `> ${commandInput}`, "Command failed"].slice(-60));
    }
  };

  return (
    <div style={styles.page}>
      <style>{globalCss}</style>
      {!connected && <div style={styles.banner}>DISCONNECTED - Reconnecting...</div>}

      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>ACE Mission Control</h1>
          <div style={styles.sub}>Robot: {robotId} | Mode: {driveMode} | Link: {connected ? "CONNECTED" : "DISCONNECTED"}</div>
          <div style={styles.subMuted}>Last known update: {lastSeenAt ? new Date(lastSeenAt).toLocaleTimeString() : "No telemetry yet"}</div>
        </div>
        <div style={styles.headerButtons}>
          <button style={styles.primaryBtn} onClick={startDemo}>▶ Start Demo</button>
          <button
            style={styles.secondaryBtn}
            onClick={() => setDriveMode((m) => (m === "Manual" ? "Autonomous" : "Manual"))}
          >
            {driveMode === "Manual" ? "Switch to Autonomous" : "Switch to Manual"}
          </button>
        </div>
      </header>

      <main style={styles.grid}>
        <section style={styles.videoCard}>
          <div style={styles.cardTitle}>Live Camera Feed</div>
          <div style={styles.fakeVideo}>
            <div style={styles.zone}>Restricted Zone</div>
            <div style={styles.boxA}>person 0.91</div>
            <div style={styles.boxB}>backpack 0.79</div>
          </div>
        </section>

        <section style={styles.metricsCard}>
          <div style={styles.cardTitle}>Power and Thermal</div>
          <div style={styles.gauges}>
            <Gauge label="Battery" value={telemetry.battery || 0} unit="%" warn={45} danger={25} />
            <Gauge label="Temp" value={telemetry.temperature || 0} unit="°C" min={0} max={120} warn={70} danger={85} />
            <Gauge label="Current" value={telemetry.current || 0} unit="A" min={0} max={30} warn={18} danger={24} />
          </div>
        </section>

        <section style={styles.imuCard}>
          <div style={styles.cardTitle}>IMU</div>
          {imu.map((item) => {
            const width = Math.min(100, Math.abs(item.value));
            return (
              <div key={item.label} style={styles.imuRow}>
                <div style={styles.imuLabel}>{item.label}</div>
                <div style={styles.imuTrack}>
                  <div style={{ ...styles.imuFill, width: `${width}%` }} />
                </div>
                <div style={styles.imuVal}>{item.value.toFixed(1)}°</div>
              </div>
            );
          })}
        </section>

        <section style={styles.chartCard}>
          <div style={styles.cardTitle}>Motor Current vs Time</div>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <LineChart data={chartData}>
                <XAxis dataKey="t" hide />
                <YAxis domain={[0, 30]} stroke="#8ea3c8" />
                <Tooltip />
                <Line type="monotone" dataKey="current" stroke="#22d3ee" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section style={styles.mapCard}>
          <div style={styles.cardTitle}>GPS Path</div>
          <canvas ref={mapCanvasRef} width={520} height={220} style={styles.canvas} />
          <div style={styles.coords}>Lat: {(telemetry.latitude || 0).toFixed(6)} | Lon: {(telemetry.longitude || 0).toFixed(6)}</div>
        </section>

        <section style={styles.terminalCard}>
          <div style={styles.cardTitle}>Command Terminal</div>
          <div style={styles.terminalLog}>
            {terminalLines.map((line, i) => (
              <div key={i} style={styles.terminalLine}>{line}</div>
            ))}
          </div>
          <div style={styles.terminalInputRow}>
            <input
              value={commandInput}
              onChange={(e) => setCommandInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendCommand()}
              style={styles.input}
            />
            <button style={styles.primaryBtn} onClick={sendCommand}>Send</button>
          </div>
        </section>
      </main>
    </div>
  );
}

const globalCss = `
  :root {
    color-scheme: dark;
  }
  * {
    box-sizing: border-box;
  }
  body {
    margin: 0;
    font-family: 'Space Grotesk', sans-serif;
    background: radial-gradient(1400px 700px at 20% -10%, #1b315e 0%, #07111f 50%, #030812 100%);
    color: #dbe7ff;
  }
`;

const styles = {
  page: {
    minHeight: "100vh",
    padding: 16,
  },
  banner: {
    background: "#b91c1c",
    color: "#fee2e2",
    padding: "8px 12px",
    borderRadius: 8,
    marginBottom: 12,
    fontWeight: 700,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  h1: {
    margin: 0,
    fontSize: "1.7rem",
    letterSpacing: "0.04em",
  },
  sub: {
    opacity: 0.8,
    marginTop: 4,
  },
  subMuted: {
    opacity: 0.7,
    marginTop: 2,
    fontSize: 13,
  },
  headerButtons: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  primaryBtn: {
    background: "linear-gradient(90deg, #14b8a6, #06b6d4)",
    color: "#00151f",
    border: "none",
    fontWeight: 700,
    padding: "10px 14px",
    borderRadius: 10,
    cursor: "pointer",
  },
  secondaryBtn: {
    background: "#1d2a42",
    color: "#dbe7ff",
    border: "1px solid #2a436f",
    fontWeight: 700,
    padding: "10px 14px",
    borderRadius: 10,
    cursor: "pointer",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 12,
  },
  videoCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
    minHeight: 270,
  },
  metricsCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
  },
  imuCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
  },
  chartCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
  },
  mapCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
  },
  terminalCard: {
    background: "rgba(8,17,34,0.8)",
    border: "1px solid #203250",
    borderRadius: 12,
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  cardTitle: {
    fontWeight: 700,
    marginBottom: 8,
    color: "#8bd8ff",
  },
  fakeVideo: {
    position: "relative",
    height: 220,
    borderRadius: 10,
    border: "1px solid #334a72",
    background: "linear-gradient(120deg, #061328, #112947)",
    overflow: "hidden",
  },
  zone: {
    position: "absolute",
    left: "16%",
    top: "16%",
    width: "55%",
    height: "60%",
    border: "2px dashed #ef4444",
    color: "#fecaca",
    display: "grid",
    placeItems: "center",
    fontWeight: 700,
  },
  boxA: {
    position: "absolute",
    left: "28%",
    top: "36%",
    border: "2px solid #22c55e",
    color: "#bbf7d0",
    padding: "4px 6px",
  },
  boxB: {
    position: "absolute",
    left: "58%",
    top: "46%",
    border: "2px solid #eab308",
    color: "#fef08a",
    padding: "4px 6px",
  },
  gauges: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  gaugeCard: {
    flex: "1 1 160px",
    background: "#0a1830",
    borderRadius: 10,
    border: "1px solid #203250",
    padding: 8,
    textAlign: "center",
  },
  gaugeValue: {
    marginTop: -14,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "1.1rem",
    fontWeight: 600,
  },
  gaugeLabel: {
    opacity: 0.85,
    marginTop: 4,
  },
  imuRow: {
    display: "grid",
    gridTemplateColumns: "68px 1fr 58px",
    alignItems: "center",
    gap: 8,
    marginBottom: 10,
  },
  imuLabel: {
    fontWeight: 700,
  },
  imuTrack: {
    background: "#13243f",
    borderRadius: 999,
    height: 10,
    overflow: "hidden",
  },
  imuFill: {
    height: "100%",
    background: "linear-gradient(90deg, #06b6d4, #34d399)",
  },
  imuVal: {
    textAlign: "right",
    fontFamily: "'JetBrains Mono', monospace",
  },
  canvas: {
    width: "100%",
    border: "1px solid #203250",
    borderRadius: 8,
  },
  coords: {
    marginTop: 6,
    opacity: 0.8,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 13,
  },
  terminalLog: {
    height: 160,
    overflow: "auto",
    background: "#031021",
    border: "1px solid #1e355a",
    borderRadius: 8,
    padding: 8,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
  },
  terminalLine: {
    whiteSpace: "pre-wrap",
    marginBottom: 4,
  },
  terminalInputRow: {
    display: "flex",
    gap: 8,
  },
  input: {
    flex: 1,
    background: "#0b1b36",
    color: "#dbe7ff",
    border: "1px solid #2a446f",
    borderRadius: 8,
    padding: "10px 12px",
    fontFamily: "'JetBrains Mono', monospace",
  },
};
