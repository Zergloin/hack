import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import MapPage from './pages/MapPage'
import ForecastPage from './pages/ForecastPage'
import ReportsPage from './pages/ReportsPage'
import ChatWidget from './components/chat/ChatWidget'

export default function App() {
  return (
    <>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </AppLayout>
      <ChatWidget />
    </>
  )
}
