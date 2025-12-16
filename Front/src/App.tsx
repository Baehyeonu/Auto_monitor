import { Navigate, Route, Routes } from 'react-router-dom'
import { MainLayout } from '@/components/layout/MainLayout'
import LogsPage from '@/pages/LogsPage'
import StudentsPage from '@/pages/StudentsPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFoundPage from '@/pages/NotFoundPage'
import { StatusConfirmationDialog } from '@/components/StatusConfirmationDialog'
import { useRealtimeLogs } from '@/hooks/useRealtimeLogs'

function App() {
  const { isConnected } = useRealtimeLogs()

  return (
    <>
      <StatusConfirmationDialog />
      <Routes>
        <Route element={<MainLayout isConnected={isConnected} />}>
          <Route index element={<Navigate to="/logs" replace />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/students" element={<StudentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </>
  )
}

export default App
