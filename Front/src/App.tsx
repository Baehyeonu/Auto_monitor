import { Navigate, Route, Routes } from 'react-router-dom'
import { MainLayout } from '@/components/layout/MainLayout'
import LogsPage from '@/pages/LogsPage'
import StudentsPage from '@/pages/StudentsPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFoundPage from '@/pages/NotFoundPage'
import { useRealtimeLogs } from '@/hooks/useRealtimeLogs'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNotificationStore } from '@/stores/useNotificationStore'
import type { StatusNotificationData } from '@/types/notification'

function App() {
  const { isConnected } = useRealtimeLogs()
  const { addNotification } = useNotificationStore()

  useWebSocket({
    onMessage: (message) => {
      if (message.type === 'status_notification') {
        addNotification(
          message.payload as StatusNotificationData,
          message.timestamp || new Date().toISOString()
        )
      }
    },
  })

  return (
    <Routes>
      <Route element={<MainLayout isConnected={isConnected} />}>
        <Route index element={<Navigate to="/logs" replace />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/students" element={<StudentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
