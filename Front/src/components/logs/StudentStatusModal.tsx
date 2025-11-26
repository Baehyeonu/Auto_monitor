import { useState, useEffect, useCallback } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fetchStudents } from '@/services/studentService'
import type { Student } from '@/types/student'
import { formatKoreanTime } from '@/lib/utils'

interface StudentStatusModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  status: string | null
  statusLabel: string
}

function getStatusBadge(student: Student) {
  // 관리자는 "관리자"로 표시
  if (student.is_admin) {
    return <Badge variant="outline" className="border-yellow-500 text-yellow-600">관리자</Badge>
  }
  
  if (student.last_leave_time) {
    return <Badge variant="destructive">접속 종료</Badge>
  }
  
  if (student.not_joined) {
    return <Badge variant="outline" className="border-gray-400 text-gray-600">미접속</Badge>
  }
  
  if (student.is_absent) {
    return (
      <Badge variant="destructive">
        {student.absent_type === 'leave' ? '외출' : student.absent_type === 'early_leave' ? '조퇴' : '미접속'}
      </Badge>
    )
  }
  
  if (student.is_cam_on) {
    return <Badge variant="default" className="bg-green-600">카메라 ON</Badge>
  } else {
    return <Badge variant="warning">카메라 OFF</Badge>
  }
}

export function StudentStatusModal({ open, onOpenChange, status, statusLabel }: StudentStatusModalProps) {
  const [students, setStudents] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const loadStudents = useCallback(async () => {
    if (!open) return
    
    setIsLoading(true)
    try {
      // "입장"은 status가 null이므로 전체 학생을 가져온 후 필터링
      if (status === null) {
        // 입장 = 카메라 ON + OFF (last_leave_time이 null인 학생)
        // 관리자 제외
        const response = await fetchStudents({
          page: 1,
          limit: 1000, // 전체 가져오기
          is_admin: false, // 관리자 제외
        })
        const joinedStudents = response.data.filter(
          (s) => !s.last_leave_time && !s.not_joined && !s.is_admin
        )
        setStudents(joinedStudents)
      } else {
        // 관리자 제외하고 학생만 조회 (전체 가져오기)
        const response = await fetchStudents({
          page: 1,
          limit: 1000, // 전체 가져오기
          status: status,
          is_admin: false, // 관리자 제외
        })
        // 추가 필터링 (API에서 관리자를 제외했지만, 혹시 모를 경우를 대비)
        const filteredStudents = response.data.filter((s) => !s.is_admin)
        setStudents(filteredStudents)
      }
    } catch (error) {
      console.error('학생 목록 로드 실패:', error)
      setStudents([])
    } finally {
      setIsLoading(false)
    }
  }, [open, status])

  useEffect(() => {
    if (open) {
      loadStudents()
    }
  }, [open, status, loadStudents])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{statusLabel} 학생 목록</DialogTitle>
          <DialogDescription>
            총 {students.length}명의 학생이 있습니다.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 overflow-hidden flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">데이터를 불러오는 중입니다...</p>
            </div>
          ) : students.length === 0 ? (
            <div className="flex-1 flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">해당 상태의 학생이 없습니다.</p>
            </div>
          ) : (
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-3">
                {students.map((student) => (
                  <div
                    key={student.id}
                    className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3"
                  >
                    <div className="flex-1">
                      <p className="font-semibold text-foreground">{student.zep_name}</p>
                      <p className="text-xs text-muted-foreground">
                        마지막 상태 변경:{' '}
                        {student.last_status_change
                          ? formatKoreanTime(student.last_status_change)
                          : '정보 없음'}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(student)}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

