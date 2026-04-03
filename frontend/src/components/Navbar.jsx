import React from 'react'
import { motion } from 'framer-motion'
import { Radio, Wifi, User, Settings, Bell } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const Navbar = () => {
  const { isConnected, robots, selectedRobotId } = useRobotStore()
  const selectedRobot = robots.find((r) => r.id === selectedRobotId)

  return (
    <motion.nav
      className="h-16 glass-panel border-b border-[#00F5FF]/20 flex items-center justify-between px-6 relative z-50"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#00F5FF]/20 to-[#00F5FF]/5 border border-[#00F5FF]/30 flex items-center justify-center neon-border">
            <Radio className="w-5 h-5 text-[#00F5FF]" />
          </div>
          <div>
            <h1 className="font-orbitron text-xl font-bold text-white tracking-wider neon-text">
              NEXUS
            </h1>
            <p className="text-xs text-gray-400 font-orbitron tracking-widest">MISSION CONTROL</p>
          </div>
        </div>

        <div className="h-8 w-px bg-gray-700" />

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-[#22C55E] animate-pulse' : 'bg-[#EF4444]'}`} />
            <span className="text-xs font-medium text-gray-300 font-orbitron">
              {isConnected ? 'SYSTEM ONLINE' : 'OFFLINE'}
            </span>
          </div>

          <div className="px-3 py-1 rounded-full bg-[#00F5FF]/10 border border-[#00F5FF]/30">
            <span className="text-xs text-[#00F5FF] font-orbitron">
              {robots.length} UNITS ACTIVE
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 px-6 py-2 rounded-lg bg-[#1F2937]/50 border border-gray-700">
        <span className="text-xs text-gray-400 font-orbitron">ACTIVE UNIT</span>
        <span className="text-lg font-orbitron font-bold text-[#00F5FF] neon-text">
          {selectedRobot?.name}
        </span>
        <div className={`px-2 py-0.5 rounded text-xs font-medium ${
          selectedRobot?.status === 'OPERATIONAL' ? 'bg-[#22C55E]/20 text-[#22C55E]' : 'bg-[#EF4444]/20 text-[#EF4444]'
        }`}>
          {selectedRobot?.status}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="p-2 rounded-lg hover:bg-[#00F5FF]/10 transition-colors relative">
          <Bell className="w-5 h-5 text-gray-400" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-[#EF4444] rounded-full animate-pulse" />
        </button>

        <button className="p-2 rounded-lg hover:bg-[#00F5FF]/10 transition-colors">
          <Wifi className="w-5 h-5 text-gray-400" />
        </button>

        <button className="p-2 rounded-lg hover:bg-[#00F5FF]/10 transition-colors">
          <Settings className="w-5 h-5 text-gray-400" />
        </button>

        <div className="h-8 w-px bg-gray-700" />

        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[#1F2937]/50 border border-gray-700">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#00F5FF] to-[#00F5FF]/50 flex items-center justify-center">
            <User className="w-4 h-4 text-[#0B0F1A]" />
          </div>
          <div className="text-left">
            <p className="text-xs font-medium text-white">CMDR. CHEN</p>
            <p className="text-[10px] text-gray-400">ADMIN</p>
          </div>
        </div>
      </div>
    </motion.nav>
  )
}

export default Navbar
