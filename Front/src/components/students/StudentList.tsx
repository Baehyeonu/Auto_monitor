import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { Student } from '@/types/student'
import { formatKoreanTime } from '@/lib/utils'
import { Trash2 } from 'lucide-react'

interface Props {
  students: Student[]
  isLoading: boolean
  onRefresh: () => void
  onDelete?: (id: number) => void
}

function getStatusBadge(student: Student) {
  // 접속 종료 상태
  if (student.last_leave_time) {
    return <Badge variant="destructive">접속 종료</Badge>
  }
  
  // 미접속 상태 (외출/조퇴)
  if (student.is_absent) {
    return (
      <Badge variant="destructive">
        {student.absent_type === 'leave' ? '외출' : student.absent_type === 'early_leave' ? '조퇴' : '미접속'}
      </Badge>
    )
  }
  
  // 카메라 상태
  if (student.is_cam_on) {
    return <Badge variant="default" className="bg-green-600">카메라 ON</Badge>
  } else {
    return <Badge variant="warning">카메라 OFF</Badge>
  }
}

export function StudentList({ students, isLoading, onRefresh, onDelete }: Props) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>등록된 사용자 ({students.length})</CardTitle>
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
        {!isLoading && students.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            등록된 사용자가 없습니다.
          </p>
        )}
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
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (confirm(`${student.zep_name}을(를) 삭제하시겠습니까?`)) {
                        onDelete(student.id)
                      }
                    }}
                    className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

