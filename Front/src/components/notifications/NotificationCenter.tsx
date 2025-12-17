import { Bell, BellRing, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useNotificationStore } from '@/stores/useNotificationStore'
import { NotificationBadge } from './NotificationBadge'
import { NotificationItem } from './NotificationItem'
import { cn } from '@/lib/utils'

export function NotificationCenter() {
  const { notifications, markAllAsRead, clearAll, getUnreadCount } =
    useNotificationStore()

  const unreadCount = getUnreadCount()
  const hasUnread = unreadCount > 0

  return (
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
          <ScrollArea className="max-h-[400px]">
            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
              />
            ))}
          </ScrollArea>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
