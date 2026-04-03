import React from 'react'
import { motion } from 'framer-motion'

const TelemetryCard = ({ icon: Icon, label, value, unit, color, delay = 0, subValue }) => {
  return (
    <motion.div
      className="relative p-4 rounded-xl glass-panel gradient-border glass-panel-hover group cursor-pointer overflow-hidden"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.3 }}
      whileHover={{ y: -2 }}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-[#00F5FF]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <div className="absolute top-3 right-3">
        <span className="relative flex h-2 w-2">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color.replace('text-', 'bg-')} opacity-75`} />
          <span className={`relative inline-flex rounded-full h-2 w-2 ${color.replace('text-', 'bg-')}`} />
        </span>
      </div>

      <div className="relative z-10">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-2 rounded-lg bg-[#1F2937] border border-gray-600 group-hover:border-[#00F5FF]/50 transition-colors">
            <Icon className={`w-4 h-4 ${color}`} />
          </div>
          <span className="text-[10px] font-orbitron text-gray-400 tracking-wider">{label}</span>
        </div>

        <div className="flex items-baseline gap-1">
          <span className={`text-2xl font-orbitron font-bold ${color} neon-text`}>
            {value}
          </span>
          <span className="text-xs text-gray-500 font-orbitron">{unit}</span>
        </div>

        {subValue && (
          <p className="mt-1 text-[10px] text-gray-400 font-mono">{subValue}</p>
        )}

        <div className="mt-3 flex items-end gap-0.5 h-8 opacity-50">
          {Array.from({ length: 8 }).map((_, i) => (
            <motion.div
              key={i}
              className={`w-1 rounded-full ${color.replace('text-', 'bg-')}`}
              initial={{ height: '20%' }}
              animate={{
                height: `${20 + Math.random() * 80}%`,
                opacity: [0.3, 1, 0.3],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                delay: i * 0.1,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  )
}

export default TelemetryCard
