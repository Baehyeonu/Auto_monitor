import { useLogStore } from '@/stores/useLogStore'
import { LogStats } from '@/components/logs/LogStats'
import { LogViewer } from '@/components/logs/LogViewer'

export default function LogsPage() {
  const stats = useLogStore((state) => state.stats)
  const logCount = useLogStore((state) => state.logs.length)

  return (
    <div className="space-y-4">
      <LogStats stats={{ ...stats, total: logCount }} />
      <LogViewer />
    </div>
  )
}

