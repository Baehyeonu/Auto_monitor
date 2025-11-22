import { useMemo, useRef, useEffect, memo, useState } from 'react'
import { useLogStore } from '@/stores/useLogStore'
import { EmptyState } from '@/components/common/EmptyState'
import type { LogEntry } from '@/types/log'

const ITEM_HEIGHT = 100
const VISIBLE_ITEMS = 6
const BUFFER = 2

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
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)
      const diffDays = Math.floor(diffMs / 86400000)

      if (diffMins < 1) {
        return '방금 전'
      } else if (diffMins < 60) {
        return `${diffMins}분 전`
      } else if (diffHours < 24) {
        return `${diffHours}시간 전`
      } else if (diffDays === 1) {
        return '어제'
      } else if (diffDays < 7) {
        return `${diffDays}일 전`
      } else {
        return date.toLocaleString('ko-KR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      }
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
  const [startIndex, setStartIndex] = useState(0)
  const [endIndex, setEndIndex] = useState(VISIBLE_ITEMS + BUFFER)

  const visibleLogs = useMemo(() => {
    return filteredLogs.slice(startIndex, endIndex)
  }, [filteredLogs, startIndex, endIndex])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const scrollTop = container.scrollTop
      const newStartIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - BUFFER)
      const newEndIndex = Math.min(
        filteredLogs.length,
        newStartIndex + VISIBLE_ITEMS + BUFFER * 2
      )
      
      if (newStartIndex !== startIndex || newEndIndex !== endIndex) {
        setStartIndex(newStartIndex)
        setEndIndex(newEndIndex)
      }
    }

    container.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()

    return () => {
      container.removeEventListener('scroll', handleScroll)
    }
  }, [filteredLogs.length, startIndex, endIndex])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (container && filteredLogs.length > 0) {
      const shouldAutoScroll = 
        container.scrollHeight - container.scrollTop - container.clientHeight < 100
      if (shouldAutoScroll) {
        container.scrollTop = container.scrollHeight
      }
    }
  }, [filteredLogs.length])

  if (filteredLogs.length === 0) {
    return (
      <EmptyState
        title="로그가 없습니다"
        description="실시간 로그가 여기에 표시됩니다"
      />
    )
  }

  const totalHeight = filteredLogs.length * ITEM_HEIGHT
  const offsetY = startIndex * ITEM_HEIGHT

  return (
    <div className="glass-panel rounded-lg border border-border/60">
      <div
        ref={scrollContainerRef}
        className="max-h-[600px] overflow-y-auto p-4"
        style={{ position: 'relative' }}
      >
        <div style={{ height: totalHeight, position: 'relative' }}>
          <div
            style={{
              transform: `translateY(${offsetY}px)`,
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
            }}
          >
            <div className="space-y-2">
              {visibleLogs.map((log) => (
                <LogItem key={log.id} log={log} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
