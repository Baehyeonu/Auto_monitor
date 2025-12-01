import { useRef, useEffect, memo } from 'react'
import { useLogStore } from '@/stores/useLogStore'
import { EmptyState } from '@/components/common/EmptyState'
import type { LogEntry } from '@/types/log'

const LogItem = memo(({ log }: { log: LogEntry }) => {
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

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      return new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }).format(date)
    } catch {
      return timestamp
    }
  }

  return (
    <div className="rounded border border-border/40 bg-background/50 p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-muted-foreground">
          {formatTimestamp(log.timestamp)}
        </span>
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-1 text-xs ${getLevelColor(log.level)}`}
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
  )
})

LogItem.displayName = 'LogItem'

export function LogViewer() {
  const filteredLogs = useLogStore((state) => state.filteredLogs)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAutoScrollingRef = useRef(true)

  const sortedLogs = [...filteredLogs].sort((a, b) => {
    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  })

  // 사용자가 수동으로 스크롤하면 자동 스크롤 비활성화
  const handleScroll = () => {
    const container = scrollContainerRef.current
    if (!container) return
    
    const isAtBottom = 
      container.scrollHeight - container.scrollTop - container.clientHeight < 50
    isAutoScrollingRef.current = isAtBottom
  }

  // 새로운 로그가 추가되거나 필터가 변경되면 자동 스크롤
  useEffect(() => {
    const container = scrollContainerRef.current
    if (container && sortedLogs.length > 0 && isAutoScrollingRef.current) {
      // 다음 프레임에서 스크롤 (DOM 업데이트 후)
      requestAnimationFrame(() => {
        if (container && isAutoScrollingRef.current) {
          container.scrollTop = container.scrollHeight
        }
      })
    }
  }, [sortedLogs.length, sortedLogs[sortedLogs.length - 1]?.id])

  // 컴포넌트 마운트 시 자동 스크롤
  useEffect(() => {
    const container = scrollContainerRef.current
    if (container && sortedLogs.length > 0) {
      requestAnimationFrame(() => {
        if (container) {
          container.scrollTop = container.scrollHeight
          isAutoScrollingRef.current = true
        }
      })
    }
  }, [])

  if (sortedLogs.length === 0) {
    return (
      <EmptyState
        title="로그가 없습니다"
        description="실시간 로그가 여기에 표시됩니다"
      />
    )
  }

  return (
    <div className="glass-panel rounded-lg border border-border/60">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="max-h-[600px] overflow-y-auto p-4"
      >
        <div className="space-y-2">
          {sortedLogs.map((log) => (
            <LogItem key={log.id} log={log} />
          ))}
        </div>
      </div>
    </div>
  )
}
