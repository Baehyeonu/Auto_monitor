import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertCircle, Calendar, Clock, User, Building2, MessageSquare } from 'lucide-react'
import type { StatusConfirmationData } from '@/types/settings'
import { useWebSocket } from '@/hooks/useWebSocket'

export function StatusConfirmationDialog() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<StatusConfirmationData | null>(null)
  const [isRollingBack, setIsRollingBack] = useState(false)

  // 기존 WebSocket 연결 재사용
  useWebSocket({
    onMessage: (message) => {
      if (message.type === 'status_confirmation') {
        setData(message.payload as StatusConfirmationData)
        setOpen(true)
      }
    },
  })

  const handleConfirm = () => {
    // 이미 저장됨 - 팝업만 닫기
    setOpen(false)
    setData(null)
  }

  const handleCancel = async () => {
    if (!data) return

    setIsRollingBack(true)
    try {
      const response = await fetch(`/api/settings/status-rollback/${data.student_id}`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('롤백 실패')
      }
    } catch (error) {
      alert('상태 변경 취소에 실패했습니다.')
    } finally {
      setIsRollingBack(false)
      setOpen(false)
      setData(null)
    }
  }

  if (!data) return null

  // 날짜 포맷팅
  const formatDateRange = () => {
    if (data.end_date && data.end_date !== data.start_date) {
      return `${data.start_date} ~ ${data.end_date}`
    }
    return data.start_date
  }

  // 상태 이모지 매핑
  const getStatusEmoji = (statusKr: string) => {
    const emojiMap: Record<string, string> = {
      조퇴: '🟣',
      외출: '🟠',
      결석: '🔴',
      휴가: '🌴',
    }
    return emojiMap[statusKr] || '📋'
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-amber-600" />
            상태 변경 확인
          </DialogTitle>
          <DialogDescription>
            슬랙 메시지에서 자동으로 파싱된 상태 변경입니다. 확인 후 저장하거나 취소할 수 있습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 상태 정보 */}
          <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
            <span className="text-3xl">{getStatusEmoji(data.status_kr)}</span>
            <div>
              <p className="text-lg font-semibold">{data.status_kr}</p>
              <p className="text-sm text-muted-foreground">상태가 변경되었습니다</p>
            </div>
          </div>

          {/* 상세 정보 */}
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <User className="h-4 w-4 mt-0.5 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium">학생</p>
                <p className="text-sm text-muted-foreground">{data.student_name}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Building2 className="h-4 w-4 mt-0.5 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium">캠프</p>
                <p className="text-sm text-muted-foreground">{data.camp}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Calendar className="h-4 w-4 mt-0.5 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium">일자</p>
                <p className="text-sm text-muted-foreground">{formatDateRange()}</p>
              </div>
            </div>

            {data.time && (
              <div className="flex items-start gap-3">
                <Clock className="h-4 w-4 mt-0.5 text-muted-foreground" />
                <div className="flex-1">
                  <p className="text-sm font-medium">시간</p>
                  <p className="text-sm text-muted-foreground">{data.time}</p>
                </div>
              </div>
            )}

            {data.reason && (
              <div className="flex items-start gap-3">
                <MessageSquare className="h-4 w-4 mt-0.5 text-muted-foreground" />
                <div className="flex-1">
                  <p className="text-sm font-medium">사유</p>
                  <p className="text-sm text-muted-foreground">{data.reason}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleCancel} disabled={isRollingBack}>
            {isRollingBack ? '취소 중...' : '취소'}
          </Button>
          <Button onClick={handleConfirm} disabled={isRollingBack}>
            확인
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
