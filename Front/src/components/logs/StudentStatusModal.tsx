import { useState, useEffect, useCallback } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fetchStudents } from '@/services/studentService'
import type { Student } from '@/types/student'
import { formatKoreanTime } from '@/lib/utils'
import { StudentActionModal } from '@/components/students/StudentActionModal'
import { StudentStatusManagementModal } from '@/components/students/StudentStatusManagementModal'
import { SendDMModal } from '@/components/students/SendDMModal'
import { StudentLogModal } from '@/components/students/StudentLogModal'

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

  // 상태 관리(status_type)가 있으면 우선 표시
  if (student.status_type) {
    const statusConfig: Record<string, { label: string; className: string }> = {
      late: {
        label: '지각',
        className: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/50',
      },
      leave: {
        label: '외출',
        className: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/50',
      },
      early_leave: {
        label: '조퇴',
        className: 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/50',
      },
      vacation: {
        label: '휴가',
        className: 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/50',
      },
      absence: {
        label: '결석',
        className: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/50',
      },
      not_joined: {
        label: '미접속',
        className: 'bg-gray-500/10 text-gray-700 dark:text-gray-400 border-gray-500/50',
      },
    }
    const config = statusConfig[student.status_type]
    if (config) {
      return (
        <Badge variant="outline" className={config.className}>
          {config.label}
        </Badge>
      )
    }
    return (
      <Badge variant="outline" className="border-purple-500 text-purple-600">
        {student.status_type}
      </Badge>
    )
  }

  // 오늘 퇴장한 학생 (백엔드에서 계산된 값 사용) - 특이사항보다 우선
  // last_leave_time이 있고 not_joined가 false면 오늘 퇴장한 학생
  if (student.last_leave_time && student.not_joined === false) {
    return <Badge variant="destructive">퇴장</Badge>
  }

  // 특이사항 상태 (백엔드에서 계산된 값 사용)
  if (student.not_joined === true) {
    return <Badge variant="outline" className="border-gray-400 text-gray-600">특이사항</Badge>
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
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null)
  const [isActionModalOpen, setIsActionModalOpen] = useState(false)
  const [isStatusManagementOpen, setIsStatusManagementOpen] = useState(false)
  const [isDMModalOpen, setIsDMModalOpen] = useState(false)
  const [isLogModalOpen, setIsLogModalOpen] = useState(false)

  const loadStudents = useCallback(async () => {
    if (!open) return
    
    setIsLoading(true)
    try {
      // "입장"은 status가 null이므로 전체 학생을 가져온 후 필터링
      if (status === null) {
        // 입장 = 카메라 ON + OFF (last_leave_time이 null인 학생)
        // 관리자 제외
        // limit이 100으로 제한되어 있으므로 여러 페이지를 가져와야 함
        let allStudents: Student[] = []
        let page = 1
        let hasMore = true
        
        while (hasMore) {
          const response = await fetchStudents({
            page,
            limit: 100, // API 최대값
            is_admin: false, // 관리자 제외
          })
          allStudents.push(...response.data)
          hasMore = response.data.length === 100 && allStudents.length < response.total
          page++
        }
        
        const joinedStudents = allStudents.filter(
          (s) => !s.last_leave_time && !s.not_joined && !s.is_admin
        )
        setStudents(joinedStudents)
      } else {
        // 관리자 제외하고 학생만 조회 (전체 가져오기)
        // limit이 100으로 제한되어 있으므로 여러 페이지를 가져와야 함
        let allStudents: Student[] = []
        let page = 1
        let hasMore = true
        
        while (hasMore) {
          const response = await fetchStudents({
            page,
            limit: 100, // API 최대값
            status: status,
            is_admin: false, // 관리자 제외
          })
          allStudents.push(...response.data)
          hasMore = response.data.length === 100 && allStudents.length < response.total
          page++
        }
        
        // 추가 필터링 (API에서 관리자를 제외했지만, 혹시 모를 경우를 대비)
        const filteredStudents = allStudents.filter((s) => !s.is_admin)
        console.log(`[특이사항] 총 ${filteredStudents.length}명 로드됨:`, filteredStudents.map(s => ({name: s.zep_name, status: s.status_type, leave: s.last_leave_time})))
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

  const handleStudentClick = (student: Student) => {
    setSelectedStudent(student)
    setIsActionModalOpen(true)
  }

  const handleSelectDM = () => {
    setIsDMModalOpen(true)
  }

  const handleSelectLog = () => {
    setIsLogModalOpen(true)
  }

  const handleSelectStatus = () => {
    setIsStatusManagementOpen(true)
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>{statusLabel} 학생 목록</DialogTitle>
            <DialogDescription>
              총 {students.length}명의 학생이 있습니다.
            </DialogDescription>
          </DialogHeader>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">데이터를 불러오는 중입니다...</p>
            </div>
          ) : students.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">해당 상태의 학생이 없습니다.</p>
            </div>
          ) : (
            <ScrollArea className="h-[60vh] pr-4">
              <div className="space-y-3">
                {students.map((student) => (
                  <div
                    key={student.id}
                    className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3 cursor-pointer hover:bg-muted/20 transition-colors"
                    onClick={() => handleStudentClick(student)}
                  >
                    <div className="flex-1">
                      <p className="font-semibold text-foreground">{student.zep_name}</p>
                      <p className="text-xs text-muted-foreground">
                        마지막 상태 변경:{' '}
                        {student.last_status_change
                          ? formatKoreanTime(student.last_status_change)
                          : student.status_set_at
                            ? formatKoreanTime(student.status_set_at)
                            : student.not_joined
                              ? '입장 기록 없음'
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
        </DialogContent>
      </Dialog>

      <StudentActionModal
        open={isActionModalOpen}
        onOpenChange={setIsActionModalOpen}
        student={selectedStudent}
        onSelectDM={handleSelectDM}
        onSelectLog={handleSelectLog}
        onSelectStatus={handleSelectStatus}
      />

      <SendDMModal
        open={isDMModalOpen}
        onOpenChange={setIsDMModalOpen}
        student={selectedStudent}
        onBack={() => {
          setIsDMModalOpen(false)
          setIsActionModalOpen(true)
        }}
      />

      <StudentLogModal
        open={isLogModalOpen}
        onOpenChange={setIsLogModalOpen}
        student={selectedStudent}
        onBack={() => {
          setIsLogModalOpen(false)
          setIsActionModalOpen(true)
        }}
      />

      <StudentStatusManagementModal
        open={isStatusManagementOpen}
        onOpenChange={setIsStatusManagementOpen}
        student={selectedStudent}
        onBack={() => {
          setIsStatusManagementOpen(false)
          setIsActionModalOpen(true)
        }}
        onUpdated={() => {
          loadStudents()
        }}
      />
    </>
  )
}
