import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Input } from '@/components/ui/input'
import type { Student } from '@/types/student'
import { formatKoreanTime } from '@/lib/utils'
import { SendDMModal } from './SendDMModal'
import { StudentActionModal } from './StudentActionModal'
import { StudentLogModal } from './StudentLogModal'
import { StudentStatusManagementModal } from './StudentStatusManagementModal'
import { useState, useMemo, useRef, useEffect } from 'react'
import { Search } from 'lucide-react'

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
  onSearch?: (searchTerm: string) => void
  allStudents?: Student[]
  onSelectStudent?: (student: Student) => void
}

function getStatusBadge(student: Student) {
  // 관리자는 "관리자"로 표시
  if (student.is_admin) {
    return <Badge variant="outline" className="border-yellow-500 text-yellow-600">관리자</Badge>
  }
  
  // 상태 관리 시스템에서 설정한 상태 우선 표시
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
  
  // 기존 외출/조퇴 상태 (하위 호환성)
  if (student.is_absent) {
    return (
      <Badge variant="destructive">
        {student.absent_type === 'leave' ? '외출' : student.absent_type === 'early_leave' ? '조퇴' : '미접속'}
      </Badge>
    )
  }
  
  // 카메라 상태 (특이사항이 아닌 경우만)
  if (student.is_cam_on) {
    return <Badge variant="default" className="bg-green-600">카메라 ON</Badge>
  } else {
    return <Badge variant="warning">카메라 OFF</Badge>
  }
}

export function StudentList({ students, isLoading, onRefresh, pagination, onSearch, allStudents = [], onSelectStudent }: Props) {
  const totalPages = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.limit)) : 1
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null)
  const [isActionModalOpen, setIsActionModalOpen] = useState(false)
  const [isDMModalOpen, setIsDMModalOpen] = useState(false)
  const [isLogModalOpen, setIsLogModalOpen] = useState(false)
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  const filteredSuggestions = useMemo(() => {
    if (!searchTerm || searchTerm.trim().length === 0 || !allStudents || allStudents.length === 0) {
      return []
    }
    const filtered = allStudents.filter((student) =>
      student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
    ).slice(0, 10)
    return filtered
  }, [searchTerm, allStudents])

  useEffect(() => {
    if (searchTerm && searchTerm.trim().length > 0) {
      if (filteredSuggestions.length > 0) {
        setShowSuggestions(true)
      } else {
        setShowSuggestions(false)
      }
    } else {
      setShowSuggestions(false)
    }
  }, [searchTerm, filteredSuggestions.length])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setSearchTerm(value)
    setFocusedIndex(-1)
    // 자동완성은 로컬 데이터로만 처리, API 호출은 하지 않음
  }

  const handleSelectStudent = (student: Student) => {
    setSearchTerm(student.zep_name)
    setShowSuggestions(false)
    setFocusedIndex(-1)
    // 자동완성에서 선택했을 때 해당 학생이 있는 페이지로 이동
    if (onSelectStudent) {
      onSelectStudent(student)
    } else if (onSearch) {
      // onSelectStudent가 없으면 검색만 실행
      onSearch(student.zep_name)
    }
  }
  
  const handleSearchSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setShowSuggestions(false)
      if (onSearch) {
        // 빈칸이면 1페이지로 이동 및 검색 초기화
        if (searchTerm.trim().length === 0) {
          onSearch('')
          if (pagination) {
            pagination.onPageChange(1)
          }
        } else {
          onSearch(searchTerm)
        }
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || filteredSuggestions.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusedIndex((prev) =>
        prev < filteredSuggestions.length - 1 ? prev + 1 : prev
      )
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusedIndex((prev) => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Enter' && focusedIndex >= 0) {
      e.preventDefault()
      handleSelectStudent(filteredSuggestions[focusedIndex])
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  useEffect(() => {
    if (focusedIndex >= 0 && suggestionsRef.current) {
      const focusedElement = suggestionsRef.current.children[focusedIndex] as HTMLElement
      if (focusedElement) {
        focusedElement.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [focusedIndex])

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
    setIsStatusModalOpen(true)
  }

  return (
    <>
      <Card className="overflow-visible">
      <CardHeader className="flex flex-row items-center justify-between relative overflow-visible">
        <CardTitle>학생 목록</CardTitle>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground z-10 pointer-events-none" />
            <Input
              ref={inputRef}
              placeholder="학생 검색..."
              value={searchTerm}
              onChange={handleSearchChange}
              onKeyDown={(e) => {
                handleKeyDown(e)
                handleSearchSubmit(e)
              }}
              onFocus={() => {
                if (searchTerm && searchTerm.trim().length > 0) {
                  setShowSuggestions(true)
                }
              }}
              onBlur={() => {
                setTimeout(() => setShowSuggestions(false), 200)
              }}
              className="w-64 pl-9"
            />
            {showSuggestions && searchTerm && searchTerm.trim().length > 0 && filteredSuggestions.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute z-[9999] w-64 left-0 bg-card border border-border rounded-md shadow-xl max-h-60 overflow-auto"
                style={{ 
                  top: '100%',
                  marginTop: '4px',
                  position: 'absolute'
                }}
              >
                {filteredSuggestions.map((student, index) => (
                  <div
                    key={student.id}
                    className={`px-4 py-2 cursor-pointer hover:bg-muted transition-colors ${
                      index === focusedIndex ? 'bg-muted' : ''
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      handleSelectStudent(student)
                    }}
                    onMouseEnter={() => setFocusedIndex(index)}
                  >
                    <p className="font-medium text-sm">{student.zep_name}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={onRefresh}>
            새로고침
          </Button>
        </div>
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
        open={isStatusModalOpen}
        onOpenChange={setIsStatusModalOpen}
        student={selectedStudent}
        onBack={() => {
          setIsStatusModalOpen(false)
          setIsActionModalOpen(true)
        }}
        onUpdated={onRefresh}
      />
    </>
  )
}
