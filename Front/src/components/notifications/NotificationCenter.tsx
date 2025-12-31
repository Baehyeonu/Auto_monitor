import { Bell, BellRing, CalendarClock, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useNotificationStore } from '@/stores/useNotificationStore'
import { NotificationBadge } from './NotificationBadge'
import { NotificationItem } from './NotificationItem'
import { cn } from '@/lib/utils'
import { fetchScheduledStatuses } from '@/services/studentService'
import type { ScheduledStatus } from '@/types/student'

export function NotificationCenter() {
  const { notifications, markAllAsRead, clearAll, getUnreadCount } =
    useNotificationStore()
  const [scheduledOpen, setScheduledOpen] = useState(false)
  const [scheduledStatuses, setScheduledStatuses] = useState<ScheduledStatus[]>([])
  const [isLoadingScheduled, setIsLoadingScheduled] = useState(false)

  const unreadCount = getUnreadCount()
  const hasUnread = unreadCount > 0
  const scheduledCount = scheduledStatuses.length

  const scheduledHeader = useMemo(() => {
    if (scheduledCount === 0) {
      return '예약이 없습니다'
    }
    return `${scheduledCount}건 예약`
  }, [scheduledCount])

  const formatScheduledTime = (iso?: string | null) => {
    if (!iso) return '시간 없음'
    const dt = new Date(iso)
    if (Number.isNaN(dt.getTime())) return '시간 없음'
    return dt.toLocaleString('ko-KR', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }

  const loadScheduled = async () => {
    setIsLoadingScheduled(true)
    try {
      const data = await fetchScheduledStatuses()
      setScheduledStatuses(Array.isArray(data) ? data : [])
    } catch {
      setScheduledStatuses([])
    } finally {
      setIsLoadingScheduled(false)
    }
  }

  useEffect(() => {
    if (scheduledOpen) {
      loadScheduled()
    }
  }, [scheduledOpen])

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="relative">
            {hasUnread ? (
              <BellRing className={cn('h-5 w-5 text-orange-400', hasUnread && 'animate-pulse')} />
            ) : (
              <Bell className="h-5 w-5" />
            )}
            <NotificationBadge count={unreadCount} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-96 p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="font-semibold">알림</h3>
            <div className="flex gap-2">
              {hasUnread && (
                <Button variant="ghost" size="sm" onClick={markAllAsRead}>
                  모두 읽음
                </Button>
              )}
              {notifications.length > 0 && (
                <Button variant="ghost" size="sm" onClick={clearAll}>
                  <Trash2 className="mr-1 h-3 w-3" />
                  모두 삭제
                </Button>
              )}
            </div>
          </div>

          {notifications.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
              알림이 없습니다
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                />
              ))}
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu onOpenChange={setScheduledOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="relative">
            <CalendarClock className="h-5 w-5" />
            {scheduledCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-orange-500 px-1 text-[11px] font-semibold text-white">
                {scheduledCount}
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-96 p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="font-semibold">예약</h3>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={loadScheduled}
                disabled={isLoadingScheduled}
              >
                새로고침
              </Button>
            </div>
          </div>

          <div className="max-h-[400px] overflow-y-auto">
            {isLoadingScheduled ? (
              <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                예약 목록을 불러오는 중...
              </div>
            ) : scheduledStatuses.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                {scheduledHeader}
              </div>
            ) : (
              scheduledStatuses.map((item) => (
                <div
                  key={`${item.student_id}-${item.scheduled_time ?? 'no-time'}-${item.status_type}`}
                  className="border-b border-border px-4 py-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-medium">{item.student_name}</div>
                    <div className="text-xs text-muted-foreground">({item.camp})</div>
                  </div>
                  <div className="mt-1 text-sm">
                    <span className="font-medium text-orange-400">{item.status_label}</span>
                    {' · '}
                    <span>{formatScheduledTime(item.scheduled_time)}</span>
                    {item.end_date && <span> ~ {item.end_date}</span>}
                  </div>
                  {item.reason && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      사유: {item.reason}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
