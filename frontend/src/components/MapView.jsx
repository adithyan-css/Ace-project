import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Polyline, Popup } from 'react-leaflet'
import { motion } from 'framer-motion'
import { MapPin, Navigation } from 'lucide-react'
import { useRobotStore } from '../store/useRobotStore'
import L from 'leaflet'

const createCustomIcon = (color) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div style="
        width: 24px;
        height: 24px;
        background: ${color};
        border: 3px solid #0B0F1A;
        border-radius: 50%;
        box-shadow: 0 0 15px ${color};
        position: relative;
      ">
        <div style="
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 8px;
          height: 8px;
          background: #0B0F1A;
          border-radius: 50%;
        "></div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })
}

const MapView = () => {
  const { robots, selectedRobotId } = useRobotStore()
  const selectedRobot = robots.find((r) => r.id === selectedRobotId)
  const [mapKey, setMapKey] = useState(0)

  useEffect(() => {
    setMapKey((prev) => prev + 1)
  }, [selectedRobotId])

  const position = [selectedRobot?.location.lat || 12.9716, selectedRobot?.location.lng || 77.5946]
  const pathPositions = selectedRobot?.path?.map((p) => [p[0], p[1]]) || []

  return (
    <motion.div className="h-80 rounded-xl glass-panel gradient-border overflow-hidden relative" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }}>
      <div className="absolute top-3 left-3 right-3 z-[400] flex items-center justify-between">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0B0F1A]/90 border border-[#00F5FF]/30 backdrop-blur-sm">
          <MapPin className="w-4 h-4 text-[#00F5FF]" />
          <span className="text-xs font-orbitron text-white tracking-wider">GPS TRACKING</span>
        </div>

        <div className="flex items-center gap-2">
          <div className="px-3 py-2 rounded-lg bg-[#0B0F1A]/90 border border-gray-700 backdrop-blur-sm">
            <span className="text-xs text-gray-400">LAT: </span>
            <span className="text-xs font-mono text-[#00F5FF]">{position[0].toFixed(6)}</span>
          </div>
          <div className="px-3 py-2 rounded-lg bg-[#0B0F1A]/90 border border-gray-700 backdrop-blur-sm">
            <span className="text-xs text-gray-400">LNG: </span>
            <span className="text-xs font-mono text-[#00F5FF]">{position[1].toFixed(6)}</span>
          </div>
        </div>
      </div>

      <MapContainer key={mapKey} center={position} zoom={15} style={{ height: '100%', width: '100%' }} zoomControl={false}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={20}
        />

        <Marker position={position} icon={createCustomIcon('#00F5FF')}>
          <Popup className="custom-popup">
            <div className="p-2 bg-[#1F2937] text-white">
              <p className="font-orbitron font-bold">{selectedRobot?.name}</p>
              <p className="text-xs text-gray-400">Speed: {selectedRobot?.telemetry.speed.toFixed(1)} m/s</p>
            </div>
          </Popup>
        </Marker>

        {pathPositions.length > 1 && (
          <Polyline positions={pathPositions} color="#00F5FF" weight={3} opacity={0.6} dashArray="5, 10" />
        )}
      </MapContainer>

      <div className="absolute inset-0 pointer-events-none border-2 border-[#00F5FF]/10 rounded-xl" />
      <div className="absolute bottom-3 right-3 z-[400]">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0B0F1A]/90 border border-gray-700 backdrop-blur-sm">
          <Navigation className="w-4 h-4 text-[#00F5FF]" />
          <span className="text-xs font-orbitron text-gray-400">TRACKING ACTIVE</span>
        </div>
      </div>
    </motion.div>
  )
}

export default MapView
