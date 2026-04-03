import React, { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Camera, AlertTriangle } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'

const LiveHud = () => {
  const videoRef = useRef(null)
  const overlayRef = useRef(null)
  const [cameraDenied, setCameraDenied] = useState(false)
  const [cameraAvailable, setCameraAvailable] = useState(false)
  const { robots, selectedRobotId, isConnected } = useRobotStore()
  const selectedRobot = robots.find((r) => r.id === selectedRobotId)
  const visionBoxes = selectedRobot?.visionBoxes || []

  useEffect(() => {
    let stream = null
    const attach = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360 }, audio: false })
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }
        setCameraDenied(false)
        setCameraAvailable(true)
      } catch {
        setCameraDenied(true)
        setCameraAvailable(false)
        return
      }
    }
    attach()
    return () => {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop())
      }
      setCameraAvailable(false)
    }
  }, [])

  useEffect(() => {
    const canvas = overlayRef.current
    const video = videoRef.current
    if (!canvas || !video) return

    const ctx = canvas.getContext('2d')
    const draw = () => {
      if (!ctx || !canvas) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.lineWidth = 2
      ctx.font = '12px monospace'
      visionBoxes.forEach((box) => {
        const x = Number(box.x || 0)
        const y = Number(box.y || 0)
        const w = Number(box.w || 80)
        const h = Number(box.h || 80)
        ctx.strokeStyle = box.inside ? '#EF4444' : '#22C55E'
        ctx.fillStyle = box.inside ? '#EF4444' : '#22C55E'
        ctx.strokeRect(x, y, w, h)
        ctx.fillText(`${box.label || 'object'} ${box.conf || ''}`.trim(), x + 4, Math.max(14, y - 4))
      })
      requestAnimationFrame(draw)
    }
    draw()
  }, [visionBoxes])

  return (
    <motion.div className="rounded-xl glass-panel gradient-border overflow-hidden relative" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 bg-[#0B0F1A]/80">
        <div className="flex items-center gap-2">
          <Camera className="w-4 h-4 text-[#00F5FF]" />
          <span className="text-xs font-orbitron text-gray-300 tracking-wider">LIVE HUD</span>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className={isConnected ? 'text-[#22C55E]' : 'text-[#EF4444]'}>{isConnected ? 'STREAM ONLINE' : 'STREAM OFFLINE'}</span>
          {visionBoxes.length > 0 && (
            <span className="text-[#FACC15] flex items-center gap-1"><AlertTriangle className="w-3 h-3" />{visionBoxes.length} boxes</span>
          )}
        </div>
      </div>
      <div className="relative aspect-video bg-black">
        <video ref={videoRef} className={`absolute inset-0 w-full h-full object-cover ${cameraAvailable ? 'opacity-100' : 'opacity-30'}`} muted playsInline />
        <canvas ref={overlayRef} width={640} height={360} className="absolute inset-0 w-full h-full" />
        {!cameraAvailable && (
          <div className="absolute left-3 bottom-3 text-[11px] font-orbitron px-2 py-1 rounded border border-[#FACC15]/40 bg-black/60 text-[#FACC15]">
            Simulated Vision Mode
          </div>
        )}
        {cameraDenied && (
          <div className="absolute left-3 top-3 right-3 text-[11px] leading-relaxed font-mono px-3 py-2 rounded border border-[#EF4444]/40 bg-black/70 text-[#EF4444]">
            Camera access denied. Allow permission or use telemetry-based vision mode.
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default LiveHud
