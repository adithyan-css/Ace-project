import React, { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Terminal, Send, Trash2, Command } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const CommandTerminal = () => {
  const { terminalHistory, executeCommand, clearTerminal, selectedRobotId } = useRobotStore()
  const [input, setInput] = useState('')
  const terminalRef = useRef(null)

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [terminalHistory])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return

    executeCommand(input)
    setInput('')
  }

  const getLineColor = (type) => {
    switch (type) {
      case 'system': return 'text-[#00F5FF]'
      case 'success': return 'text-[#22C55E]'
      case 'error': return 'text-[#EF4444]'
      case 'warning': return 'text-[#FACC15]'
      case 'input': return 'text-white'
      default: return 'text-gray-300'
    }
  }

  const getPrefix = (type) => {
    switch (type) {
      case 'system': return '[SYS]'
      case 'success': return '[OK]'
      case 'error': return '[ERR]'
      case 'warning': return '[WARN]'
      case 'input': return '>'
      default: return '  '
    }
  }

  return (
    <motion.div className="h-64 rounded-xl glass-panel gradient-border flex flex-col overflow-hidden" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }}>
      <div className="flex items-center justify-between px-4 py-3 bg-[#0B0F1A] border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#00F5FF]" />
          <span className="text-xs font-orbitron text-gray-400 tracking-wider">COMMAND INTERFACE</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#EF4444]" />
          <div className="w-2 h-2 rounded-full bg-[#FACC15]" />
          <div className="w-2 h-2 rounded-full bg-[#22C55E]" />
        </div>
      </div>

      <div ref={terminalRef} className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1 bg-[#0B0F1A]/80">
        {terminalHistory.map((line, index) => (
          <motion.div key={index} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className={`${getLineColor(line.type)}`}>
            <span className="text-gray-600 mr-2">[{line.timestamp}]</span>
            <span className="font-bold mr-2">{getPrefix(line.type)}</span>
            <span>{line.message}</span>
          </motion.div>
        ))}
        <div className="flex items-center text-[#00F5FF]">
          <span className="text-gray-600 mr-2">[{new Date().toLocaleTimeString()}]</span>
          <span className="font-bold mr-2">{'>'}</span>
          <span className="terminal-cursor w-2 h-4 bg-[#00F5FF]" />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="p-3 bg-[#0B0F1A] border-t border-gray-700">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1F2937] border border-gray-600 flex-1 focus-within:border-[#00F5FF]/50 transition-colors">
            <Command className="w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Enter command for ROBOT-${(selectedRobotId || 0).toString().padStart(3, '0')}...`}
              className="flex-1 bg-transparent text-xs text-white placeholder-gray-500 outline-none font-mono"
              spellCheck={false}
            />
          </div>
          <button type="submit" className="p-2 rounded-lg bg-[#00F5FF]/10 border border-[#00F5FF]/30 text-[#00F5FF] hover:bg-[#00F5FF]/20 transition-colors">
            <Send className="w-4 h-4" />
          </button>
          <button type="button" onClick={clearTerminal} className="p-2 rounded-lg bg-[#EF4444]/10 border border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/20 transition-colors">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        <div className="flex gap-2 mt-2">
          {['STATUS', 'PATROL', 'RETURN', 'STOP'].map((cmd) => (
            <button key={cmd} type="button" onClick={() => executeCommand(cmd)} className="px-2 py-1 rounded text-[10px] font-mono bg-[#1F2937] text-gray-400 hover:text-[#00F5FF] hover:bg-[#00F5FF]/10 transition-colors border border-gray-700 hover:border-[#00F5FF]/30">
              {cmd}
            </button>
          ))}
        </div>
      </form>
    </motion.div>
  )
}

export default CommandTerminal
