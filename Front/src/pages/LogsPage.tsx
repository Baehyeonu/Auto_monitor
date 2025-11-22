import { useLogStore } from '@/stores/useLogStore'
import { LogStats } from '@/components/logs/LogStats'
import { LogViewer } from '@/components/logs/LogViewer'

export default function LogsPage() {
  const stats = useLogStore((state) => state.stats)

  return (
    <div className="space-y-4">
      <LogStats stats={stats} />
      <LogViewer />
    </div>
  )
}

