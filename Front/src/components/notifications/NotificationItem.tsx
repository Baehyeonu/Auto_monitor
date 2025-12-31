import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { Notification } from '@/types/notification'

function formatRelativeTime(timestamp: string): string {
  const now = Date.now()
  const then = new Date(timestamp).getTime()
  const diff = now - then

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '방금 전'
  if (minutes < 60) return `${minutes}분 전`
  if (hours < 24) return `${hours}시간 전`
  return `${days}일 전`
}

interface NotificationItemProps {
  notification: Notification
  // 읽기 전용: onConfirm, onCancel 제거
}

const STATUS_EMOJI: Record<string, string> = {
  조퇴: '🟣',
  외출: '🟠',
  결석: '🔴',
  휴가: '🌴',
  지각: '🟡',
}

export function NotificationItem({ notification }: NotificationItemProps) {
  const [isHovered, setIsHovered] = useState(false)
  const { data, read, timestamp } = notification

  const emoji = STATUS_EMOJI[data.status_type] || '📌'
  const actionLabel = data.is_immediate ? '적용' : '예약'

  const getDateDisplay = () => {
    if (data.is_future_date && data.start_date) {
      return `${data.start_date}부터`
    }
    if (data.time) {
      return `오늘 ${data.time}`
    }
    return '오늘부터'
  }

  const relativeTime = formatRelativeTime(timestamp)

  return (
    <div
      className={cn(
        'relative border-b border-border p-3 transition-colors',
        !read && 'bg-blue-500/5',
        isHovered && 'bg-accent'
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-start gap-3">
        {!read && (
          <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-blue-500" />
        )}
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-lg">{emoji}</span>
            <span className="font-semibold">{data.student_name}</span>
            <span className="text-xs text-muted-foreground">({data.camp})</span>
          </div>
          <div className="text-sm">
            <span className="font-medium text-orange-400">{data.status_type}</span>
            {' · '}
            <span>{getDateDisplay()}</span>
            {' · '}
            <span className="text-xs text-muted-foreground">{actionLabel}</span>
            {data.end_date && data.end_date !== data.start_date && (
              <span> ~ {data.end_date}</span>
            )}
          </div>
          {data.reason && (
            <div className="text-xs text-muted-foreground">사유: {data.reason}</div>
          )}
          <div className="text-xs text-muted-foreground">{relativeTime}</div>
        </div>
      </div>

    </div>
  )
}
