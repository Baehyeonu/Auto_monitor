import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useState } from 'react'
import { updateStudentStatus } from '@/services/studentService'
import type { Student } from '@/types/student'
import { Clock, DoorOpen, LogOut, Calendar, XCircle, CheckCircle2 } from 'lucide-react'
import { formatKoreanTime } from '@/lib/utils'

interface StudentStatusManagementModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  student: Student | null
  onBack?: () => void
  onUpdated?: () => void
}

type StatusType = 'late' | 'leave' | 'early_leave' | 'vacation' | 'absence' | null

const STATUS_OPTIONS: Array<{
  value: StatusType
  label: string
  description: string
  icon: React.ReactNode
  color: string
}> = [
  {
    value: 'late',
    label: '지각',
    description: '상태 변화가 있기 전까지 알람 금지',
    icon: <Clock className="h-4 w-4" />,
    color: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/50',
  },
  {
    value: 'leave',
    label: '외출',
    description: '지각과 동일 (상태 변화 전까지 알람 금지)',
    icon: <DoorOpen className="h-4 w-4" />,
    color: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/50',
  },
  {
    value: 'early_leave',
    label: '조퇴',
    description: '조퇴 처리 이후 알람 금지',
    icon: <LogOut className="h-4 w-4" />,
    color: 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/50',
  },
  {
    value: 'vacation',
    label: '휴가',
    description: '당일 알람 금지',
    icon: <Calendar className="h-4 w-4" />,
    color: 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/50',
  },
  {
    value: 'absence',
    label: '결석',
    description: '휴가와 동일 (당일 알람 금지)',
    icon: <XCircle className="h-4 w-4" />,
    color: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/50',
  },
  {
    value: null,
    label: '정상',
    description: '알람 정상 작동',
    icon: <CheckCircle2 className="h-4 w-4" />,
    color: 'bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/50',
  },
]

export function StudentStatusManagementModal({
  open,
  onOpenChange,
  student,
  onBack,
  onUpdated,
}: StudentStatusManagementModalProps) {
  const [selectedStatus, setSelectedStatus] = useState<StatusType>(student?.status_type || null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!student) return null

  const handleStatusChange = async () => {
    if (selectedStatus === student.status_type) {
      onOpenChange(false)
      return
    }

    setIsSubmitting(true)
    try {
      await updateStudentStatus(student.id, selectedStatus)
      await onUpdated?.()
      onOpenChange(false)
    } catch (error) {
      console.error('Failed to update student status:', error)
      alert('상태 변경에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const currentStatusOption = STATUS_OPTIONS.find((opt) => opt.value === student.status_type)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>학생 상태 관리</DialogTitle>
          <DialogDescription>
            {student.zep_name}님의 상태를 관리합니다. 상태에 따라 알람이 자동으로 제어됩니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* 현재 상태 표시 */}
          <div className="rounded-lg border p-4 bg-muted/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">현재 상태</p>
                {currentStatusOption ? (
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={currentStatusOption.color}>
                      {currentStatusOption.icon}
                      <span className="ml-1">{currentStatusOption.label}</span>
                    </Badge>
                    {student.status_set_at && (
                      <span className="text-xs text-muted-foreground">
                        설정: {formatKoreanTime(student.status_set_at)}
                      </span>
                    )}
                  </div>
                ) : (
                  <Badge variant="outline" className="bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/50">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    정상
                  </Badge>
                )}
              </div>
            </div>
            {student.alarm_blocked_until && (
              <p className="text-xs text-muted-foreground mt-2">
                알람 금지 종료: {formatKoreanTime(student.alarm_blocked_until)}
              </p>
            )}
          </div>

          {/* 상태 선택 */}
          <div>
            <p className="text-sm font-medium mb-3">상태 선택</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {STATUS_OPTIONS.map((option) => {
                const isSelected = selectedStatus === option.value
                return (
                  <button
                    key={option.value || 'normal'}
                    onClick={() => setSelectedStatus(option.value)}
                    className={`rounded-lg border p-4 text-left transition-all hover:bg-muted/50 ${
                      isSelected
                        ? 'border-primary bg-primary/5 ring-2 ring-primary ring-offset-2'
                        : 'border-border'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`}>
                        {option.icon}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-semibold">{option.label}</p>
                          {isSelected && (
                            <Badge variant="outline" className="text-xs">
                              선택됨
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{option.description}</p>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* 하단 버튼 */}
          <div className="flex items-center justify-between pt-4 border-t">
            <Button variant="outline" onClick={onBack || (() => onOpenChange(false))}>
              뒤로
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                취소
              </Button>
              <Button onClick={handleStatusChange} disabled={isSubmitting}>
                {isSubmitting ? '저장 중...' : '저장'}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

