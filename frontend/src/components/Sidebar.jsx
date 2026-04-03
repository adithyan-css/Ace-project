import React from 'react'
import { motion } from 'framer-motion'
import { Bot, ChevronRight, Activity, MapPin } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const Sidebar = () => {
  const { robots, selectedRobotId, selectRobot } = useRobotStore()

  return (
    <motion.aside
      className="w-64 glass-panel border-r border-[#00F5FF]/20 flex flex-col"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="p-4 border-b border-gray-700">
        <h2 className="font-orbitron text-sm font-semibold text-gray-400 tracking-wider flex items-center gap-2">
          <Bot className="w-4 h-4" />
          ROBOT FLEET
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {robots.map((robot, index) => (
          <motion.button
            key={robot.id}
            onClick={() => selectRobot(robot.id)}
            className={`w-full p-3 rounded-lg border transition-all duration-300 group relative overflow-hidden ${
              selectedRobotId === robot.id
                ? 'bg-[#00F5FF]/10 border-[#00F5FF]/50 shadow-[0_0_15px_rgba(0,245,255,0.2)]'
                : 'bg-[#1F2937]/50 border-gray-700 hover:border-[#00F5FF]/30'
            }`}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {selectedRobotId === robot.id && (
              <motion.div
                className="absolute left-0 top-0 bottom-0 w-1 bg-[#00F5FF]"
                layoutId="selectionIndicator"
              />
            )}

            <div className="flex items-center justify-between mb-2">
              <span className="font-orbitron font-bold text-sm text-white">
                {robot.name}
              </span>
              <ChevronRight className={`w-4 h-4 transition-transform ${
                selectedRobotId === robot.id ? 'text-[#00F5FF] rotate-90' : 'text-gray-500'
              }`} />
            </div>

            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1 text-gray-400">
                <Activity className="w-3 h-3" />
                <span>{robot.telemetry.battery.toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-1 text-gray-400">
                <MapPin className="w-3 h-3" />
                <span>LIVE</span>
              </div>
            </div>

            <div className="mt-2 flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                robot.status === 'OPERATIONAL' ? 'bg-[#22C55E] shadow-[0_0_8px_#22C55E]' : 'bg-[#EF4444]'
              }`} />
              <span className="text-[10px] text-gray-400 font-orbitron">{robot.status}</span>
            </div>
          </motion.button>
        ))}
      </div>

      <div className="p-4 border-t border-gray-700 space-y-3">
        <h3 className="font-orbitron text-xs text-gray-500 tracking-wider">SYSTEM METRICS</h3>

        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">CPU Load</span>
            <span className="text-[#00F5FF]">42%</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full w-[42%] bg-gradient-to-r from-[#00F5FF] to-[#00F5FF]/50 rounded-full" />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Memory</span>
            <span className="text-[#22C55E]">68%</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full w-[68%] bg-gradient-to-r from-[#22C55E] to-[#22C55E]/50 rounded-full" />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Network</span>
            <span className="text-[#FACC15]">24ms</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full w-[30%] bg-gradient-to-r from-[#FACC15] to-[#FACC15]/50 rounded-full" />
          </div>
        </div>
      </div>
    </motion.aside>
  )
}

export default Sidebar
