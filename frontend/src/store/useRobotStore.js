import { create } from 'zustand'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

const ROBOT_KEYS = {
  'rover-cam-01': 'ace-secret-key-123',
  'rover-arm-02': 'ace-secret-key-456',
}

const INITIAL_HISTORY = Array.from({ length: 21 }, (_, i) => ({
  time: new Date(Date.now() - (20 - i) * 1000).toLocaleTimeString(),
  speed: 0,
  battery: 0,
  temperature: 0,
}))

const defaultRobot = (id, robotId) => ({
  id,
  robotId,
  name: `ROBOT-${id.toString().padStart(3, '0')}`,
  status: 'OPERATIONAL',
  telemetry: {
    speed: 0,
    battery: 0,
    temperature: 0,
    current: 0,
    orientation: { pitch: 0, roll: 0, yaw: 0 },
  },
  location: { lat: 0, lng: 0 },
  path: [],
  lastSeen: null,
})

const toLocalTelemetry = (t) => ({
  speed: Number(t?.speed || 0),
  battery: Number(t?.battery || 0),
  temperature: Number(t?.motor_temp || 0),
  current: Number(t?.current || 0),
  orientation: {
    pitch: Number(t?.pitch || 0),
    roll: Number(t?.roll || 0),
    yaw: Number(t?.yaw || 0),
  },
})

const toSeverity = (value) => {
  const mapped = String(value || '').toLowerCase()
  if (mapped === 'critical' || mapped === 'high' || mapped === 'emergency' || mapped === 'danger') {
    return 'danger'
  }
  if (mapped === 'warning' || mapped === 'medium' || mapped === 'alert') {
    return 'warning'
  }
  if (mapped === 'success' || mapped === 'low' || mapped === 'safe') {
    return 'success'
  }
  return 'info'
}

const mapInsightFromCommand = (commandEvent) => {
  const nlp = commandEvent?.nlp
  if (!nlp) {
    return null
  }
  return {
    id: Date.now(),
    type: 'nlp',
    severity: toSeverity(nlp.overall_status),
    message: `Command analysis: ${nlp.overall_status}`,
    timestamp: commandEvent.timestamp || new Date().toISOString(),
  }
}

export const useRobotStore = create((set, get) => ({
  robots: [],
  selectedRobotId: null,
  historicalData: INITIAL_HISTORY,
  historicalByRobot: {},
  robotIndex: {},
  alerts: [],
  aiInsights: [],
  isConnected: false,
  isLoading: false,
  error: null,
  ws: null,
  terminalHistory: [
    { type: 'system', message: 'Mission Control v2.4.1 initialized', timestamp: new Date().toLocaleTimeString() },
    { type: 'system', message: 'Connecting to backend...', timestamp: new Date().toLocaleTimeString() },
  ],

  selectRobot: (id) => {
    const state = get()
    const selected = state.robots.find((r) => r.id === id)
    const history = state.historicalByRobot[id] || INITIAL_HISTORY
    set({ selectedRobotId: id, historicalData: history })
    if (selected?.robotId) {
      get().loadRobotHistory(selected.robotId)
    }
  },

  upsertRobotTelemetry: (robotId, telemetryPayload) => {
    set((state) => {
      let robotIndex = state.robotIndex
      let robots = state.robots
      let robotNumericId = robotIndex[robotId]

      if (!robotNumericId) {
        robotNumericId = robots.length + 1
        robotIndex = { ...robotIndex, [robotId]: robotNumericId }
        robots = [...robots, defaultRobot(robotNumericId, robotId)]
      }

      const nextRobots = robots.map((robot) => {
        if (robot.id !== robotNumericId) {
          return robot
        }
        const location = {
          lat: Number(telemetryPayload?.latitude || robot.location.lat || 0),
          lng: Number(telemetryPayload?.longitude || robot.location.lng || 0),
        }
        const path = [...robot.path, [location.lat, location.lng]].slice(-120)
        return {
          ...robot,
          status: 'OPERATIONAL',
          telemetry: toLocalTelemetry(telemetryPayload),
          location,
          path,
          lastSeen: telemetryPayload?.timestamp || new Date().toISOString(),
        }
      })

      const selectedRobotId = state.selectedRobotId || robotNumericId
      const selectedRobot = nextRobots.find((r) => r.id === selectedRobotId)
      const nextHistoryByRobot = {
        ...state.historicalByRobot,
        [robotNumericId]: [
          ...(state.historicalByRobot[robotNumericId] || INITIAL_HISTORY).slice(-20),
          {
            time: new Date().toLocaleTimeString(),
            speed: selectedRobot?.telemetry.speed || 0,
            battery: selectedRobot?.telemetry.battery || 0,
            temperature: selectedRobot?.telemetry.temperature || 0,
          },
        ],
      }

      return {
        robots: nextRobots,
        robotIndex,
        selectedRobotId,
        historicalByRobot: nextHistoryByRobot,
        historicalData: nextHistoryByRobot[selectedRobotId] || INITIAL_HISTORY,
      }
    })
  },

  loadFleet: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_URL}/robots`)
      if (!response.ok) {
        throw new Error(`Failed to load robots (${response.status})`)
      }
      const data = await response.json()
      const robots = (data.robots || []).map((r, idx) => ({
        ...defaultRobot(idx + 1, r.robot_id),
        telemetry: {
          speed: Number(r.speed || 0),
          battery: Number(r.battery || 0),
          temperature: 0,
          current: 0,
          orientation: { pitch: 0, roll: 0, yaw: 0 },
        },
      }))
      const robotIndex = robots.reduce((acc, robot) => {
        acc[robot.robotId] = robot.id
        return acc
      }, {})

      set((state) => ({
        robots,
        robotIndex,
        selectedRobotId: state.selectedRobotId || robots[0]?.id || null,
      }))

      const selected = get().robots.find((r) => r.id === get().selectedRobotId)
      if (selected?.robotId) {
        await get().loadRobotHistory(selected.robotId)
      }
      set({ isLoading: false })
    } catch (err) {
      set({ isLoading: false, error: err.message })
      get().addTerminalLine({
        type: 'error',
        message: `Backend fetch failed: ${err.message}`,
        timestamp: new Date().toLocaleTimeString(),
      })
    }
  },

  loadRobotHistory: async (robotId) => {
    const state = get()
    const numericId = state.robotIndex[robotId]
    if (!numericId) {
      return
    }
    try {
      const response = await fetch(`${API_URL}/telemetry/${robotId}?limit=120`)
      if (!response.ok) {
        return
      }
      const rows = await response.json()
      const ordered = [...rows].reverse()
      const history = ordered.slice(-21).map((item) => ({
        time: new Date(item.timestamp).toLocaleTimeString(),
        speed: Number(item.speed || 0),
        battery: Number(item.battery || 0),
        temperature: Number(item.motor_temp || 0),
      }))

      let updatedRobot = null
      if (ordered.length > 0) {
        const latest = ordered[ordered.length - 1]
        updatedRobot = {
          telemetry: toLocalTelemetry(latest),
          location: { lat: Number(latest.latitude || 0), lng: Number(latest.longitude || 0) },
          path: ordered.slice(-120).map((x) => [Number(x.latitude || 0), Number(x.longitude || 0)]),
        }
      }

      set((current) => {
        const nextRobots = updatedRobot
          ? current.robots.map((robot) =>
              robot.id === numericId
                ? {
                    ...robot,
                    ...updatedRobot,
                  }
                : robot,
            )
          : current.robots

        const historicalByRobot = {
          ...current.historicalByRobot,
          [numericId]: history.length > 0 ? history : INITIAL_HISTORY,
        }

        return {
          robots: nextRobots,
          historicalByRobot,
          historicalData:
            current.selectedRobotId === numericId
              ? historicalByRobot[numericId]
              : current.historicalData,
        }
      })
    } catch {
      return
    }
  },

  connectWebSocket: () => {
    const state = get()
    if (state.ws && state.isConnected) {
      return
    }

    const ws = new WebSocket(WS_URL)
    ws.onopen = () => {
      set({ isConnected: true, error: null, ws })
      get().addTerminalLine({
        type: 'system',
        message: 'WebSocket connection established',
        timestamp: new Date().toLocaleTimeString(),
      })
      ws.send(JSON.stringify({ type: 'ping' }))
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'telemetry' && payload.telemetry?.robot_id) {
          get().upsertRobotTelemetry(payload.telemetry.robot_id, payload.telemetry)
        }

        if (payload.type === 'snapshot' && payload.robots) {
          Object.entries(payload.robots).forEach(([robotId, telemetry]) => {
            get().upsertRobotTelemetry(robotId, telemetry)
          })
        }

        if (payload.type === 'command') {
          get().addTerminalLine({
            type: 'success',
            message: `Command queued for ${payload.robot_id}: ${payload.command}`,
            timestamp: new Date(payload.timestamp || Date.now()).toLocaleTimeString(),
          })

          const insight = mapInsightFromCommand(payload)
          if (insight) {
            set((current) => ({ aiInsights: [insight, ...current.aiInsights].slice(0, 20) }))
          }
        }

        if (payload.type === 'ai_insight' && payload.insight) {
          const item = {
            id: Date.now(),
            type: payload.insight.source || 'prediction',
            message: payload.insight.message,
            severity: toSeverity(payload.insight.severity),
            timestamp: payload.timestamp || new Date().toISOString(),
          }
          set((current) => ({ aiInsights: [item, ...current.aiInsights].slice(0, 20) }))

          if (item.severity === 'danger' || item.severity === 'warning') {
            get().addAlert({
              id: Date.now(),
              severity: item.severity,
              message: item.message,
              timestamp: new Date().toLocaleTimeString(),
            })
          }
        }
      } catch {
        return
      }
    }

    ws.onclose = () => {
      set({ isConnected: false, ws: null })
      get().addTerminalLine({
        type: 'warning',
        message: 'WebSocket disconnected. Reconnecting...',
        timestamp: new Date().toLocaleTimeString(),
      })
      setTimeout(() => {
        if (!get().isConnected) {
          get().connectWebSocket()
        }
      }, 1500)
    }

    ws.onerror = () => {
      set({ isConnected: false })
    }
  },

  initialize: async () => {
    await get().loadFleet()
    get().connectWebSocket()
    try {
      await fetch(`${API_URL}/demo/start`)
    } catch {
      return
    }
  },

  addAlert: (alert) => set((state) => ({ alerts: [alert, ...state.alerts].slice(0, 10) })),

  dismissAlert: (id) => set((state) => ({ alerts: state.alerts.filter((a) => a.id !== id) })),

  addTerminalLine: (line) =>
    set((state) => ({
      terminalHistory: [...state.terminalHistory, line].slice(-50),
    })),

  clearTerminal: () =>
    set({
      terminalHistory: [
        { type: 'system', message: 'Terminal history cleared', timestamp: new Date().toLocaleTimeString() },
      ],
    }),

  executeCommand: async (command) => {
    const state = get()
    const selectedRobot = state.robots.find((r) => r.id === state.selectedRobotId)
    const timestamp = new Date().toLocaleTimeString()

    if (!selectedRobot) {
      get().addTerminalLine({ type: 'error', message: 'No robot selected', timestamp })
      return
    }

    set((current) => ({
      terminalHistory: [...current.terminalHistory, { type: 'input', message: `> ${command}`, timestamp }].slice(-50),
    }))

    try {
      const key = ROBOT_KEYS[selectedRobot.robotId]
      if (!key) {
        throw new Error(`No key configured for ${selectedRobot.robotId}`)
      }

      const response = await fetch(`${API_URL}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          robot_id: selectedRobot.robotId,
          secret_key: key,
          command,
        }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Command failed (${response.status})`)
      }

      const result = await response.json()
      get().addTerminalLine({
        type: 'success',
        message: `Command accepted: ${result.parsed?.action || command}`,
        timestamp: new Date(result.timestamp || Date.now()).toLocaleTimeString(),
      })

      const nlpResponse = await fetch(`${API_URL}/ai/parse-command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: command }),
      })
      if (nlpResponse.ok) {
        const nlpData = await nlpResponse.json()
        const insight = {
          id: Date.now(),
          type: 'nlp',
          message: `NLP status: ${nlpData.parsed?.overall_status || 'SAFE'}`,
          severity: toSeverity(nlpData.parsed?.overall_status),
          timestamp: new Date().toISOString(),
        }
        set((current) => ({ aiInsights: [insight, ...current.aiInsights].slice(0, 20) }))
      }

      const latestTelemetry = selectedRobot.telemetry
      const predictionBody = {
        robot_id: selectedRobot.robotId,
        secret_key: key,
        history: [
          {
            current: Number(latestTelemetry.current || 0),
            rpm: Number(Math.max(1000, (latestTelemetry.speed || 0) * 220)),
            temperature: Number(latestTelemetry.temperature || 0),
            vibration: Number((Math.abs(latestTelemetry.orientation?.pitch || 0) + Math.abs(latestTelemetry.orientation?.roll || 0)) / 100),
          },
        ],
      }
      const predictResponse = await fetch(`${API_URL}/ai/predict/motor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(predictionBody),
      })
      if (predictResponse.ok) {
        const prediction = await predictResponse.json()
        const msg = `Motor risk ${prediction.risk_level} (${(prediction.failure_probability * 100).toFixed(1)}%)`
        set((current) => ({
          aiInsights: [
            {
              id: Date.now() + 1,
              type: 'prediction',
              message: msg,
              severity: toSeverity(prediction.risk_level),
              timestamp: new Date().toISOString(),
            },
            ...current.aiInsights,
          ].slice(0, 20),
        }))
      }
    } catch (err) {
      get().addTerminalLine({ type: 'error', message: err.message, timestamp: new Date().toLocaleTimeString() })
    }
  },
}))
