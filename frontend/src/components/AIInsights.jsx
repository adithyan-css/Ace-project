import React from 'react'
import { motion } from 'framer-motion'
import { Brain, Eye, MessageSquare, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const AIInsights = () => {
  const { aiInsights } = useRobotStore()

  const getIcon = (type) => {
    switch (type) {
      case 'prediction': return Brain
      case 'vision': return Eye
      case 'nlp': return MessageSquare
      default: return Info
    }
  }

  const getColor = (severity) => {
    switch (severity) {
      case 'danger': return 'text-[#EF4444] border-[#EF4444]/50 bg-[#EF4444]/10'
      case 'warning': return 'text-[#FACC15] border-[#FACC15]/50 bg-[#FACC15]/10'
      case 'success': return 'text-[#22C55E] border-[#22C55E]/50 bg-[#22C55E]/10'
      default: return 'text-[#00F5FF] border-[#00F5FF]/50 bg-[#00F5FF]/10'
    }
  }

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'danger': return AlertTriangle
      case 'warning': return AlertTriangle
      case 'success': return CheckCircle
      default: return Info
    }
  }

  return (
    <motion.div className="h-80 rounded-xl glass-panel gradient-border p-4 flex flex-col" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-[#00F5FF]" />
          <h3 className="font-orbitron font-semibold text-white tracking-wider">AI INSIGHTS</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00F5FF] opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00F5FF]" />
          </span>
          <span className="text-xs text-[#00F5FF] font-orbitron">AI ACTIVE</span>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        {aiInsights.map((insight, index) => {
          const Icon = getIcon(insight.type)
          const SeverityIcon = getSeverityIcon(insight.severity)
          const colorClass = getColor(insight.severity)

          return (
            <motion.div key={insight.id} className={`p-3 rounded-lg border ${colorClass} relative overflow-hidden group cursor-pointer`} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.1 }} whileHover={{ scale: 1.02, x: 5 }}>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />

              <div className="relative z-10 flex items-start gap-3">
                <div className="p-2 rounded-lg bg-[#0B0F1A]/50">
                  <Icon className="w-4 h-4" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-orbitron uppercase tracking-wider opacity-70">
                      {insight.type}
                    </span>
                    <SeverityIcon className="w-3 h-3" />
                  </div>
                  <p className="text-xs text-white leading-relaxed">{insight.message}</p>
                  <p className="mt-1 text-[10px] opacity-50 font-mono">
                    {new Date(insight.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      <div className="mt-3 pt-3 border-t border-gray-700">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500 font-orbitron">MODEL STATUS</span>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            <span className="text-[#22C55E]">ONLINE</span>
          </div>
        </div>
        <div className="mt-2 h-1 bg-gray-700 rounded-full overflow-hidden">
          <motion.div className="h-full bg-gradient-to-r from-[#00F5FF] to-[#22C55E]" initial={{ width: '0%' }} animate={{ width: '100%' }} transition={{ duration: 2, repeat: Infinity }} />
        </div>
      </div>
    </motion.div>
  )
}

export default AIInsights
