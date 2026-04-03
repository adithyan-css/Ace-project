import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, X, Bell, Shield, Clock } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const AlertsPanel = () => {
  const { alerts, dismissAlert } = useRobotStore()

  const getAlertStyles = (severity) => {
    switch (severity) {
      case 'danger':
        return 'bg-[#EF4444]/10 border-[#EF4444]/50 text-[#EF4444]'
      case 'warning':
        return 'bg-[#FACC15]/10 border-[#FACC15]/50 text-[#FACC15]'
      default:
        return 'bg-[#00F5FF]/10 border-[#00F5FF]/50 text-[#00F5FF]'
    }
  }

  return (
    <motion.div className="h-64 rounded-xl glass-panel gradient-border p-4 flex flex-col" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-[#00F5FF]" />
          <h3 className="font-orbitron font-semibold text-white tracking-wider">ALERTS</h3>
        </div>
        <div className="flex items-center gap-2">
          {alerts.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-[#EF4444] text-white text-xs font-bold animate-pulse">
              {alerts.length}
            </span>
          )}
          <Shield className="w-4 h-4 text-[#22C55E]" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 relative">
        <AnimatePresence mode="popLayout">
          {alerts.length === 0 ? (
            <motion.div className="h-full flex flex-col items-center justify-center text-gray-500" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <Bell className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs font-orbitron">NO ACTIVE ALERTS</p>
            </motion.div>
          ) : (
            alerts.map((alert) => (
              <motion.div key={alert.id} layout initial={{ opacity: 0, x: 50, scale: 0.9 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: -50, scale: 0.9 }} className={`p-3 rounded-lg border ${getAlertStyles(alert.severity)} relative group`}>
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-white leading-relaxed">{alert.message}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3 opacity-50" />
                      <span className="text-[10px] opacity-50 font-mono">{alert.timestamp}</span>
                    </div>
                  </div>
                  <button onClick={() => dismissAlert(alert.id)} className="p-1 rounded hover:bg-white/10 transition-colors opacity-0 group-hover:opacity-100">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-700">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-500 font-orbitron">THREAT LEVEL</span>
          <div className="flex gap-1">
            {['bg-[#22C55E]', 'bg-[#FACC15]', 'bg-[#EF4444]'].map((color, i) => (
              <div key={i} className={`w-8 h-1.5 rounded-full ${color} ${i === 0 ? 'opacity-100' : 'opacity-30'}`} />
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default AlertsPanel
