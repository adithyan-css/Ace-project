import React from 'react'
import { motion } from 'framer-motion'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { TrendingUp, Activity, Thermometer } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const ChartsPanel = () => {
  const { historicalData } = useRobotStore()

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[#1F2937] border border-[#00F5FF]/30 rounded-lg p-3 shadow-xl">
          <p className="text-xs text-gray-400 font-orbitron mb-2">{label}</p>
          {payload.map((entry, index) => (
            <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
              {entry.name}: {entry.value.toFixed(1)}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  return (
    <div className="p-4 rounded-xl glass-panel gradient-border">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#00F5FF]" />
          <h3 className="font-orbitron font-semibold text-white tracking-wider">TELEMETRY ANALYTICS</h3>
        </div>
        <div className="flex gap-2">
          <span className="px-2 py-1 rounded bg-[#00F5FF]/10 text-[#00F5FF] text-xs font-orbitron">LIVE</span>
          <span className="px-2 py-1 rounded bg-[#1F2937] text-gray-400 text-xs font-orbitron">1s INTERVAL</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 h-48">
        <motion.div className="relative p-3 rounded-lg bg-[#0B0F1A]/50 border border-gray-700" whileHover={{ borderColor: 'rgba(0, 245, 255, 0.3)' }}>
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-[#00F5FF]" />
            <span className="text-xs font-orbitron text-gray-400">SPEED</span>
          </div>
          <ResponsiveContainer width="100%" height="80%">
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="speedGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00F5FF" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00F5FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis dataKey="time" hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="speed" stroke="#00F5FF" strokeWidth={2} fillOpacity={1} fill="url(#speedGradient)" name="Speed" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div className="relative p-3 rounded-lg bg-[#0B0F1A]/50 border border-gray-700" whileHover={{ borderColor: 'rgba(34, 197, 94, 0.3)' }}>
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-[#22C55E]" />
            <span className="text-xs font-orbitron text-gray-400">BATTERY</span>
          </div>
          <ResponsiveContainer width="100%" height="80%">
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="batteryGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis dataKey="time" hide />
              <YAxis hide domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="battery" stroke="#22C55E" strokeWidth={2} fillOpacity={1} fill="url(#batteryGradient)" name="Battery %" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div className="relative p-3 rounded-lg bg-[#0B0F1A]/50 border border-gray-700" whileHover={{ borderColor: 'rgba(250, 204, 21, 0.3)' }}>
          <div className="flex items-center gap-2 mb-2">
            <Thermometer className="w-4 h-4 text-[#FACC15]" />
            <span className="text-xs font-orbitron text-gray-400">TEMPERATURE</span>
          </div>
          <ResponsiveContainer width="100%" height="80%">
            <AreaChart data={historicalData}>
              <defs>
                <linearGradient id="tempGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FACC15" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#FACC15" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis dataKey="time" hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="temperature" stroke="#FACC15" strokeWidth={2} fillOpacity={1} fill="url(#tempGradient)" name="Temp °C" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
      </div>
    </div>
  )
}

export default ChartsPanel
