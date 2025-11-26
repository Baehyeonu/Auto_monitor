import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useLogStore } from '@/stores/useLogStore'
import { formatKoreanTime } from '@/lib/utils'
import type { Student } from '@/types/student'
import { useMemo } from 'react'
import { ArrowLeft } from 'lucide-react'

interface StudentLogModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  student: Student | null
  onBack?: () => void
}

export function StudentLogModal({ open, onOpenChange, student, onBack }: StudentLogModalProps) {
  const logs = useLogStore((state) => state.logs)

  const studentLogs = useMemo(() => {
    if (!student) return []
    
    return logs
      .filter((log) => 
        (log.student_name === student.zep_name || log.student_id === student.id) &&
        (log.event_type === 'camera_on' || 
         log.event_type === 'camera_off' || 
         log.event_type === 'user_join' || 
         log.event_type === 'user_leave' ||
         log.event_type === 'dm_sent')
      )
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 50) // 최근 50개만 표시
  }, [logs, student])

  const getEventTypeLabel = (eventType: string) => {
    switch (eventType) {
      case 'camera_on':
        return '카메라 ON'
      case 'camera_off':
        return '카메라 OFF'
      case 'user_join':
        return '입장'
      case 'user_leave':
        return '퇴장'
      case 'dm_sent':
        return 'DM 발신'
      default:
        return eventType
    }
  }

  const getEventTypeBadgeVariant = (eventType: string) => {
    switch (eventType) {
      case 'camera_on':
      case 'user_join':
        return 'default'
      case 'camera_off':
      case 'user_leave':
        return 'outline'
      case 'dm_sent':
        return 'outline'
      default:
        return 'outline'
    }
  }

  if (!student) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            {onBack && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onBack}
                className="h-6 w-6"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}
            <div>
              <DialogTitle>학생 로그 기록</DialogTitle>
              <DialogDescription>
                {student.zep_name}님의 상태 변화 기록입니다.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <ScrollArea className="h-[500px] pr-4">
          {studentLogs.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              로그 기록이 없습니다.
            </div>
          ) : (
            <div className="space-y-2">
              {studentLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={getEventTypeBadgeVariant(log.event_type)}>
                        {getEventTypeLabel(log.event_type)}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {formatKoreanTime(new Date(log.timestamp))}
                      </span>
                    </div>
                    <p className="text-sm">{log.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}

