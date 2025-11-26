import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import { StudentForm } from '@/components/students/StudentForm'
import { StudentList } from '@/components/students/StudentList'
import { BulkImport } from '@/components/students/BulkImport'
import { AdminRegistration } from '@/components/students/AdminRegistration'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { fetchStudents, createStudent, deleteStudent, deleteAllStudents, updateAdminStatus } from '@/services/studentService'
import type { Student } from '@/types/student'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Trash2, AlertCircle } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WebSocketMessage } from '@/types/websocket'

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [admins, setAdmins] = useState<Student[]>([])
  const [allStudents, setAllStudents] = useState<Student[]>([])
  const [allAdmins, setAllAdmins] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<'students' | 'admins'>('students')
  const [actionTab, setActionTab] = useState<'create' | 'bulk' | 'delete' | 'admin'>('create')
  const [studentPage, setStudentPage] = useState(1)
  const [adminPage, setAdminPage] = useState(1)
  const [studentsTotal, setStudentsTotal] = useState(0)
  const [adminsTotal, setAdminsTotal] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const [isSelectingStudent, setIsSelectingStudent] = useState(false)

  const PER_PAGE = 7

  const loadStudents = useCallback(async () => {
    setIsLoading(true)
    try {
      if (activeTab === 'students') {
        const studentsData = await fetchStudents({ 
          page: studentPage, 
          limit: PER_PAGE, 
          is_admin: false,
          search: searchTerm || undefined
        })
        setStudents(studentsData.data)
        setStudentsTotal(studentsData.total)
      } else {
        const adminsData = await fetchStudents({ 
          page: adminPage, 
          limit: PER_PAGE, 
          is_admin: true,
          search: searchTerm || undefined
        })
        setAdmins(adminsData.data)
        setAdminsTotal(adminsData.total)
      }
    } catch {
    } finally {
      setIsLoading(false)
    }
  }, [activeTab, adminPage, studentPage, searchTerm])
  
  const loadAllStudentsForAutocomplete = useCallback(async () => {
    try {
      // limit이 100으로 제한되어 있으므로 여러 번 요청
      const [studentsData, adminsData] = await Promise.all([
        fetchStudents({ limit: 100, is_admin: false }),
        fetchStudents({ limit: 100, is_admin: true }),
      ])
      setAllStudents(studentsData.data)
      setAllAdmins(adminsData.data)
      
      // 학생이 100명 이상일 경우 추가 페이지 로드
      if (studentsData.total > 100) {
        const additionalPages = Math.ceil(studentsData.total / 100) - 1
        const additionalRequests = []
        for (let page = 2; page <= additionalPages + 1; page++) {
          additionalRequests.push(fetchStudents({ page, limit: 100, is_admin: false }))
        }
        const additionalResults = await Promise.all(additionalRequests)
        const allStudentsData = [
          ...studentsData.data,
          ...additionalResults.flatMap(result => result.data)
        ]
        setAllStudents(allStudentsData)
      }
      
      // 관리자가 100명 이상일 경우 추가 페이지 로드
      if (adminsData.total > 100) {
        const additionalPages = Math.ceil(adminsData.total / 100) - 1
        const additionalRequests = []
        for (let page = 2; page <= additionalPages + 1; page++) {
          additionalRequests.push(fetchStudents({ page, limit: 100, is_admin: true }))
        }
        const additionalResults = await Promise.all(additionalRequests)
        const allAdminsData = [
          ...adminsData.data,
          ...additionalResults.flatMap(result => result.data)
        ]
        setAllAdmins(allAdminsData)
      }
    } catch {
    }
  }, [])
  
  const loadInitialData = useCallback(async () => {
    // 처음 로드할 때 두 탭의 총 개수와 첫 페이지 데이터를 모두 불러오기
    setIsLoading(true)
    try {
      const [studentsData, adminsData] = await Promise.all([
        fetchStudents({ page: 1, limit: PER_PAGE, is_admin: false }),
        fetchStudents({ page: 1, limit: PER_PAGE, is_admin: true }),
      ])
      setStudents(studentsData.data)
      setStudentsTotal(studentsData.total)
      setAdmins(adminsData.data)
      setAdminsTotal(adminsData.total)
      setStudentPage(1)
      setAdminPage(1)
    } catch {
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // 처음 마운트될 때만 초기 데이터 로드
    loadInitialData()
    loadAllStudentsForAutocomplete()
  }, [])
  
  useEffect(() => {
    // 탭이나 페이지가 변경될 때 해당 탭의 데이터만 불러오기
    // 단, 학생 선택 중일 때는 제외 (handleSelectStudent에서 직접 로드)
    if (!isSelectingStudent) {
      loadStudents()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, adminPage, studentPage, searchTerm, isSelectingStudent])
  
  const handleSelectStudent = useCallback(async (student: Student) => {
    // 전체 목록에서 해당 학생이 있는 페이지를 찾아서 이동
    setIsSelectingStudent(true)
    try {
      // 전체 목록이 로드되지 않았으면 먼저 로드
      if ((activeTab === 'students' && allStudents.length === 0) || 
          (activeTab === 'admins' && allAdmins.length === 0)) {
        await loadAllStudentsForAutocomplete()
      }
      
      // 전체 목록에서 해당 학생의 인덱스 찾기
      const targetList = activeTab === 'students' ? allStudents : allAdmins
      
      if (targetList.length === 0) {
        setIsSelectingStudent(false)
        return
      }
      
      const studentIndex = targetList.findIndex(s => s.id === student.id)
      
      if (studentIndex === -1) {
        setIsSelectingStudent(false)
        return
      }
      
      // 전체 목록에서 해당 학생이 있는 페이지 계산
      const targetPage = Math.floor(studentIndex / PER_PAGE) + 1
      
      // 검색어 먼저 초기화 (loadStudents 재생성 방지)
      setSearchTerm('')
      
      // 페이지 설정 (검색어 초기화 후)
      if (activeTab === 'students') {
        setStudentPage(targetPage)
      } else {
        setAdminPage(targetPage)
      }
      
      // 상태 업데이트가 완료될 때까지 약간의 지연
      await new Promise(resolve => setTimeout(resolve, 0))
      
      // 직접 데이터 로드 (검색어 없이)
      setIsLoading(true)
      try {
        if (activeTab === 'students') {
          const studentsData = await fetchStudents({ 
            page: targetPage, 
            limit: PER_PAGE, 
            is_admin: false
          })
          setStudents(studentsData.data)
          setStudentsTotal(studentsData.total)
        } else {
          const adminsData = await fetchStudents({ 
            page: targetPage, 
            limit: PER_PAGE, 
            is_admin: true
          })
          setAdmins(adminsData.data)
          setAdminsTotal(adminsData.total)
        }
      } finally {
        setIsLoading(false)
        // 플래그는 나중에 리셋 (useEffect가 다시 실행되지 않도록)
        setTimeout(() => {
          setIsSelectingStudent(false)
        }, 200)
      }
    } catch (error) {
      console.error('Error selecting student:', error)
      setIsSelectingStudent(false)
    }
  }, [activeTab, allStudents, allAdmins, loadAllStudentsForAutocomplete])
  
  const handleSearch = useCallback(async (term: string) => {
    // 1. 검색어가 비어있으면 초기화 및 현재 페이지 새로고침
    if (!term.trim()) {
      setSearchTerm('')
      loadStudents()
      return
    }
    
    // 2. 현재 탭에 맞는 전체 목록 가져오기 (이미 loadAllStudentsForAutocomplete로 로드되어 있음)
    const targetList = activeTab === 'students' ? allStudents : allAdmins
    
    // 3. 로컬 데이터에서 학생 찾기 (정확 일치 우선, 없으면 포함 검색)
    let student = targetList.find(s => s.zep_name === term)
    
    if (!student) {
      // 정확히 일치하는 이름이 없으면 포함된 이름 검색 (가장 첫 번째 결과)
      student = targetList.find(s => s.zep_name.includes(term))
    }
    
    if (student) {
      // 4. 학생을 찾았으면 handleSelectStudent를 재사용하여 해당 페이지로 이동
      await handleSelectStudent(student)
    } else {
      // 5. 로컬 목록에 없으면 기존 방식대로 필터링 시도
      setSearchTerm(term)
      if (activeTab === 'students') {
        setStudentPage(1)
      } else {
        setAdminPage(1)
      }
    }
  }, [activeTab, allStudents, allAdmins, handleSelectStudent, loadStudents])

  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'STUDENT_STATUS_CHANGED') {
      const payload = message.payload as {
        student_id: number
        zep_name: string
        event_type: string
        is_cam_on: boolean
      }
      
      const updateStudentStatus = (studentList: Student[]) => {
        return studentList.map((student) => {
          if (student.id === payload.student_id) {
            return {
              ...student,
              is_cam_on: payload.is_cam_on,
              last_status_change: new Date().toISOString(),
              last_leave_time: payload.event_type === 'user_leave' ? new Date().toISOString() : student.last_leave_time,
              is_absent: payload.event_type === 'user_leave' ? false : student.is_absent,
            }
          }
          return student
        })
      }
      
      setStudents((prev) => updateStudentStatus(prev))
      setAdmins((prev) => updateStudentStatus(prev))
    }
  }, [])

  useWebSocket({
    onMessage: handleWebSocketMessage,
  })

  const handleSubmit = async (values: {
    zep_name: string
    discord_id?: string
  }) => {
    setIsSubmitting(true)
    try {
      await createStudent(values)
      await loadStudents()
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteStudent(id)
      await loadStudents()
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || error?.message || '삭제에 실패했습니다.'
      alert(errorMessage)
    }
  }

  const handleDeleteAll = async () => {
    const studentCount = studentsTotal
    if (studentCount === 0) {
      alert('삭제할 학생이 없습니다.')
      return
    }
    
    if (!confirm(`모든 학생(${studentCount}명)을 삭제하시겠습니까?\n관리자는 삭제되지 않습니다.`)) {
      return
    }
    
    try {
      const response = await deleteAllStudents()
      alert(response.message)
      await loadStudents()
    } catch (error) {
      alert('전체 삭제에 실패했습니다.')
    }
  }

  const managementTabs = useMemo(
    () => [
      { value: 'create', label: '학생 등록', content: <StudentForm onSubmit={handleSubmit} isSubmitting={isSubmitting} /> },
      { value: 'bulk', label: '일괄 등록', content: <BulkImport onUpdated={loadStudents} /> },
      {
        value: 'delete',
        label: '학생 삭제',
        content: <StudentDeletePanel onDelete={handleDelete} onDeleteAll={handleDeleteAll} onUpdated={loadStudents} />,
      },
      {
        value: 'admin',
        label: '관리자 등록',
        content: <AdminRegistration onUpdated={loadStudents} />,
      },
    ],
    [handleDelete, handleSubmit, isSubmitting, loadStudents, students],
  )

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'students' | 'admins')}>
        <TabsList>
          <TabsTrigger value="students">학생 ({studentsTotal})</TabsTrigger>
          <TabsTrigger value="admins">관리자 ({adminsTotal})</TabsTrigger>
        </TabsList>
        <TabsContent value="students" className="mt-4 space-y-4">
          <StudentList
            students={students}
            isLoading={isLoading}
            onRefresh={loadStudents}
            onSearch={handleSearch}
            onSelectStudent={handleSelectStudent}
            allStudents={allStudents}
            pagination={{
              page: studentPage,
              total: studentsTotal,
              limit: PER_PAGE,
              onPageChange: setStudentPage,
            }}
          />
          <Tabs value={actionTab} onValueChange={(v) => setActionTab(v as typeof actionTab)} className="space-y-4">
            <TabsList className="grid w-full grid-cols-2 gap-2 md:grid-cols-4">
              {managementTabs.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {managementTabs.map((tab) => (
              <TabsContent key={tab.value} value={tab.value}>
                {tab.content}
              </TabsContent>
            ))}
          </Tabs>
        </TabsContent>
        <TabsContent value="admins" className="mt-4">
          <StudentList
            students={admins}
            isLoading={isLoading}
            onRefresh={loadStudents}
            onSearch={handleSearch}
            onSelectStudent={handleSelectStudent}
            allStudents={allAdmins}
            pagination={{
              page: adminPage,
              total: adminsTotal,
              limit: PER_PAGE,
              onPageChange: setAdminPage,
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

type DeletePanelProps = {
  onDelete: (id: number) => Promise<void>
  onDeleteAll: () => Promise<void>
  onUpdated?: () => Promise<void> | void
}

function StudentDeletePanel({ onDelete, onDeleteAll, onUpdated }: DeletePanelProps) {
  const [allStudents, setAllStudents] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  const loadAllStudents = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetchStudents({ limit: 100 })
      setAllStudents(response.data)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAllStudents()
  }, [loadAllStudents])

  const filteredSuggestions = useMemo(() => {
    if (!searchTerm || searchTerm.trim().length === 0) {
      return []
    }
    return allStudents.filter((student) =>
      student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
    )
  }, [searchTerm, allStudents])

  useEffect(() => {
    if (searchTerm && searchTerm.trim().length > 0 && filteredSuggestions.length > 0) {
      setShowSuggestions(true)
    } else {
      setShowSuggestions(false)
    }
  }, [searchTerm, filteredSuggestions.length])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setSearchTerm(value)
    setFocusedIndex(-1)
    const currentStudent = allStudents.find(s => s.id === selectedId)
    if (!currentStudent || value !== currentStudent.zep_name) {
      setSelectedId(null)
    }
  }

  const handleSelectStudent = (student: Student) => {
    setSearchTerm(student.zep_name)
    setSelectedId(student.id)
    setShowSuggestions(false)
    setFocusedIndex(-1)
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

  const selectedStudent = useMemo(() => {
    return allStudents.find((s) => s.id === selectedId) || null
  }, [selectedId, allStudents])

  const handleDeleteClick = async () => {
    if (!selectedId || !selectedStudent) return
    
    if (selectedStudent.is_admin) {
      alert('관리자는 삭제할 수 없습니다. 먼저 학생 상태로 변경해주세요.')
      return
    }
    
    if (!confirm(`${selectedStudent.zep_name} 학생을 삭제하시겠습니까?`)) return
    setIsDeleting(true)
    try {
      await onDelete(selectedId)
      await loadAllStudents()
      await onUpdated?.()
      setSelectedId(null)
      setSearchTerm('')
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || error?.message || '삭제에 실패했습니다.'
      alert(errorMessage)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleConvertToStudent = async () => {
    if (!selectedId || !selectedStudent || !selectedStudent.is_admin) return
    
    if (!confirm(`${selectedStudent.zep_name} 관리자를 학생 상태로 변경하시겠습니까?`)) return
    
    try {
      await updateAdminStatus(selectedId, false)
      await loadAllStudents()
      await onUpdated?.()
      alert('학생 상태로 변경되었습니다. 이제 삭제할 수 있습니다.')
      setSelectedId(null)
      setSearchTerm('')
    } catch (error) {
      alert('상태 변경에 실패했습니다.')
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(event.target as Node) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trash2 className="h-5 w-5" />
          학생 삭제
        </CardTitle>
        <CardDescription>이름으로 검색하여 학생을 선택하고 삭제할 수 있습니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground py-4 text-center">학생 목록을 불러오는 중입니다...</p>
        ) : (
          <>
            <div className="relative">
              <Input
                ref={inputRef}
                placeholder="이름으로 검색..."
                value={searchTerm}
                onChange={handleSearchChange}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  if (searchTerm && searchTerm.trim().length > 0 && filteredSuggestions.length > 0) {
                    setShowSuggestions(true)
                  }
                }}
                className="w-full"
              />
              {showSuggestions && searchTerm && searchTerm.trim().length > 0 && filteredSuggestions.length > 0 && (
                <div
                  ref={suggestionsRef}
                  className="absolute z-[100] w-full mt-1 bg-background border border-border rounded-md shadow-lg max-h-60 overflow-auto"
                  style={{ top: '100%' }}
                >
                  {filteredSuggestions.map((student, index) => (
                    <div
                      key={student.id}
                      className={`px-3 py-2 cursor-pointer transition-colors ${
                        index === focusedIndex
                          ? 'bg-primary/10 text-primary-foreground'
                          : 'hover:bg-muted/20'
                      }`}
                      onClick={() => handleSelectStudent(student)}
                      onMouseEnter={() => setFocusedIndex(index)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{student.zep_name}</p>
                            {student.is_admin && (
                              <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-700 dark:text-yellow-400">
                                관리자
                              </span>
                            )}
                          </div>
                          {student.discord_id && (
                            <p className="text-xs text-muted-foreground">Discord: {student.discord_id}</p>
                          )}
                        </div>
                        {selectedId === student.id && (
                          <Trash2 className="h-4 w-4 text-destructive" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {selectedStudent && selectedStudent.is_admin && (
              <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-3 space-y-2">
                <div className="flex items-center gap-2 text-yellow-700 dark:text-yellow-400">
                  <AlertCircle className="h-4 w-4" />
                  <p className="text-sm font-semibold">관리자는 삭제할 수 없습니다</p>
                </div>
                <p className="text-xs text-muted-foreground">
                  삭제하려면 먼저 학생 상태로 변경해주세요.
                </p>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleConvertToStudent}
                >
                  학생 상태로 변경
                </Button>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                variant="destructive"
                className="flex-1"
                onClick={handleDeleteClick}
                disabled={!selectedId || isDeleting || (selectedStudent?.is_admin ?? false)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {isDeleting ? '삭제 중...' : '학생 삭제'}
              </Button>
              <Button
                variant="destructive"
                onClick={onDeleteAll}
                className="flex-1"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                전체 삭제
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

