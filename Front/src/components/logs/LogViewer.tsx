import { useLogStore } from '@/stores/useLogStore'
import { EmptyState } from '@/components/common/EmptyState'
import type { LogEntry } from '@/types/log'

export function LogViewer() {
  const logs = useLogStore((state) => state.logs)

  if (logs.length === 0) {
    return (
      <EmptyState
        title="로그가 없습니다"
        description="실시간 로그가 여기에 표시됩니다"
      />
    )
  }

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'bg-red-500/20 text-red-500'
      case 'warning':
        return 'bg-yellow-500/20 text-yellow-500'
      case 'success':
        return 'bg-green-500/20 text-green-500'
      default:
        return 'bg-blue-500/20 text-blue-500'
    }
  }

  return (
    <div className="glass-panel rounded-lg border border-border/60">
      <div className="max-h-[600px] overflow-y-auto p-4">
        <div className="space-y-2">
          {logs.map((log) => (
            <div
              key={log.id}
              className="rounded border border-border/40 bg-background/50 p-3 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-muted-foreground">
                  {log.timestamp}
                </span>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-2 py-1 text-xs ${getLevelColor(
                      log.level,
                    )}`}
                  >
                    {log.level}
                  </span>
                  <span className="rounded bg-muted px-2 py-1 text-xs">
                    {log.source}
                  </span>
                </div>
              </div>
              <p className="mt-1 text-foreground">{log.message}</p>
              {log.student_name && (
                <p className="mt-1 text-xs text-muted-foreground">
                  학생: {log.student_name}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

