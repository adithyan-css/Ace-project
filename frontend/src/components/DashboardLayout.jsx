import React from 'react'
import { motion } from 'framer-motion'
import Navbar from './Navbar'
import Sidebar from './Sidebar'
import TelemetryCard from './TelemetryCard'
import ChartsPanel from './ChartsPanel'
import MapView from './MapView'
import AIInsights from './AIInsights'
import AlertsPanel from './AlertsPanel'
import CommandTerminal from './CommandTerminal'
import { useRobotStore } from '../store/useRobotStore'
import { Zap, Battery, Thermometer, Activity, Compass } from 'lucide-react'

const DashboardLayout = () => {
  const { robots, selectedRobotId, isLoading, error } = useRobotStore()
  const selectedRobot = robots.find((r) => r.id === selectedRobotId)

  const telemetryMetrics = [
    {
      icon: Zap,
      label: 'SPEED',
      value: (selectedRobot?.telemetry.speed || 0).toFixed(1),
      unit: 'm/s',
      color: 'text-[#00F5FF]',
      glowColor: 'shadow-[#00F5FF]',
    },
    {
      icon: Battery,
      label: 'BATTERY',
      value: (selectedRobot?.telemetry.battery || 0).toFixed(1),
      unit: '%',
      color: (selectedRobot?.telemetry.battery || 0) > 20 ? 'text-[#22C55E]' : 'text-[#EF4444]',
      glowColor: (selectedRobot?.telemetry.battery || 0) > 20 ? 'shadow-[#22C55E]' : 'shadow-[#EF4444]',
    },
    {
      icon: Thermometer,
      label: 'TEMP',
      value: (selectedRobot?.telemetry.temperature || 0).toFixed(1),
      unit: '°C',
      color: (selectedRobot?.telemetry.temperature || 0) > 60 ? 'text-[#FACC15]' : 'text-[#00F5FF]',
      glowColor: 'shadow-[#FACC15]',
    },
    {
      icon: Activity,
      label: 'CURRENT',
      value: (selectedRobot?.telemetry.current || 0).toFixed(2),
      unit: 'A',
      color: 'text-[#00F5FF]',
      glowColor: 'shadow-[#00F5FF]',
    },
    {
      icon: Compass,
      label: 'ORIENTATION',
      value: `${(selectedRobot?.telemetry.orientation.yaw || 0).toFixed(0)}°`,
      unit: '',
      color: 'text-[#00F5FF]',
      glowColor: 'shadow-[#00F5FF]',
      subValue: `P:${(selectedRobot?.telemetry.orientation.pitch || 0).toFixed(1)}° R:${(selectedRobot?.telemetry.orientation.roll || 0).toFixed(1)}°`,
    },
  ]

  return (
    <div className="flex flex-col h-full">
      <Navbar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {isLoading && <div className="text-xs text-[#00F5FF] font-orbitron">LOADING FLEET DATA...</div>}
          {error && <div className="text-xs text-[#EF4444] font-orbitron">{error}</div>}

          <motion.div
            className="grid grid-cols-5 gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {telemetryMetrics.map((metric, index) => (
              <TelemetryCard
                key={metric.label}
                {...metric}
                delay={index * 0.1}
              />
            ))}
          </motion.div>

          <div className="grid grid-cols-12 gap-4">
            <motion.div
              className="col-span-8 space-y-4"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
            >
              <ChartsPanel />

              <div className="grid grid-cols-2 gap-4">
                <MapView />
                <AIInsights />
              </div>
            </motion.div>

            <motion.div
              className="col-span-4 space-y-4"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
            >
              <AlertsPanel />
              <CommandTerminal />
            </motion.div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout
