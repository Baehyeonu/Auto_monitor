import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface NotificationBadgeProps {
  count: number
  className?: string
}

export function NotificationBadge({ count, className }: NotificationBadgeProps) {
  if (count === 0) return null

  return (
    <Badge
      variant="destructive"
      className={cn(
        'absolute -right-1 -top-1 h-5 min-w-5 justify-center p-0 px-1',
        className
      )}
    >
      {count > 99 ? '99+' : count}
    </Badge>
  )
}
