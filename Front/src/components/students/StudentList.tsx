import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Student } from '@/types/student'
import { formatKoreanTime } from '@/lib/utils'
import { SendDMModal } from './SendDMModal'
import { useState } from 'react'

interface Props {
  students: Student[]
  isLoading: boolean
  onRefresh: () => void
  pagination?: {
    page: number
    total: number
    limit: number
    onPageChange: (page: number) => void
  }
}

function getStatusBadge(student: Student) {
  // 관리자는 "관리자"로 표시
  if (student.is_admin) {
    return <Badge variant="outline" className="border-yellow-500 text-yellow-600">관리자</Badge>
  }
  
  // 접속 종료 상태
  if (student.last_leave_time) {
    return <Badge variant="destructive">접속 종료</Badge>
  }
  
  // 미접속 상태 (오늘 초기화 시간 이후 접속하지 않음) - 우선 체크
  // not_joined가 true이거나, last_leave_time이 없고 카메라가 꺼져있고 not_joined가 undefined가 아닌 경우
  if (student.not_joined === true) {
    return <Badge variant="outline" className="border-gray-400 text-gray-600">미접속</Badge>
  }
  
  // 외출/조퇴 상태
  if (student.is_absent) {
    return (
      <Badge variant="destructive">
        {student.absent_type === 'leave' ? '외출' : student.absent_type === 'early_leave' ? '조퇴' : '미접속'}
      </Badge>
    )
  }
  
  // 카메라 상태 (미접속자가 아닌 경우만)
  if (student.is_cam_on) {
    return <Badge variant="default" className="bg-green-600">카메라 ON</Badge>
  } else {
    return <Badge variant="warning">카메라 OFF</Badge>
  }
}

export function StudentList({ students, isLoading, onRefresh, pagination }: Props) {
  const totalPages = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.limit)) : 1
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null)
  const [isDMModalOpen, setIsDMModalOpen] = useState(false)

  const handleStudentClick = (student: Student) => {
    setSelectedStudent(student)
    setIsDMModalOpen(true)
  }

  return (
    <>
      <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>학생 목록</CardTitle>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          새로고침
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            데이터를 불러오는 중입니다...
          </p>
        )}
        {!isLoading && students.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            등록된 사용자가 없습니다.
          </p>
        ) : (
          <ScrollArea className="max-h-[520px] pr-2">
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
        {pagination && (
          <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              페이지 {pagination.page} / {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => pagination.onPageChange(Math.max(1, pagination.page - 1))}
                disabled={pagination.page === 1}
              >
                이전
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => pagination.onPageChange(Math.min(totalPages, pagination.page + 1))}
                disabled={pagination.page === totalPages}
              >
                다음
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
    <SendDMModal
      open={isDMModalOpen}
      onOpenChange={setIsDMModalOpen}
      student={selectedStudent}
    />
    </>
  )
}

