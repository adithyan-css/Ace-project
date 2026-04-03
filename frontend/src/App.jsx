import React, { useEffect } from 'react'
import DashboardLayout from './components/DashboardLayout'
import { useRobotStore } from './store/useRobotStore'

function App() {
  const initialize = useRobotStore((state) => state.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <div className="w-full h-screen bg-[#0B0F1A] overflow-hidden grid-bg">
      <DashboardLayout />
    </div>
  )
}

export default App
