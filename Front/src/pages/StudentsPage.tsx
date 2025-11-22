import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import { StudentForm } from '@/components/students/StudentForm'
import { StudentList } from '@/components/students/StudentList'
import { BulkImport } from '@/components/students/BulkImport'
import { AdminRegistration } from '@/components/students/AdminRegistration'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { fetchStudents, createStudent, deleteStudent } from '@/services/studentService'
import type { Student } from '@/types/student'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Trash2 } from 'lucide-react'

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [admins, setAdmins] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<'students' | 'admins'>('students')
  const [actionTab, setActionTab] = useState<'create' | 'bulk' | 'delete' | 'admin'>('create')
  const [studentPage, setStudentPage] = useState(1)
  const [adminPage, setAdminPage] = useState(1)
  const [studentsTotal, setStudentsTotal] = useState(0)
  const [adminsTotal, setAdminsTotal] = useState(0)

  const PER_PAGE = 7

  const loadStudents = useCallback(async () => {
    setIsLoading(true)
    try {
      const [studentsData, adminsData] = await Promise.all([
        fetchStudents({ page: studentPage, limit: PER_PAGE, is_admin: false }),
        fetchStudents({ page: adminPage, limit: PER_PAGE, is_admin: true }),
      ])
      setStudents(studentsData.data)
      setStudentsTotal(studentsData.total)
      setAdmins(adminsData.data)
      setAdminsTotal(adminsData.total)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }, [adminPage, studentPage])

  useEffect(() => {
    loadStudents()
  }, [loadStudents])

  const handleSubmit = async (values: {
    zep_name: string
    discord_id?: number
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
    } catch (error) {
      console.error('삭제 실패:', error)
      alert('삭제에 실패했습니다.')
    }
  }

  const managementTabs = useMemo(
    () => [
      { value: 'create', label: '학생 등록', content: <StudentForm onSubmit={handleSubmit} isSubmitting={isSubmitting} /> },
      { value: 'bulk', label: '일괄 등록', content: <BulkImport /> },
      {
        value: 'delete',
        label: '학생 삭제',
        content: <StudentDeletePanel onDelete={handleDelete} onUpdated={loadStudents} />,
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
            onDelete={handleDelete}
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
            onDelete={handleDelete}
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
  onUpdated?: () => Promise<void> | void
}

function StudentDeletePanel({ onDelete, onUpdated }: DeletePanelProps) {
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

  // 검색어에 따른 자동완성 필터링
  const filteredSuggestions = useMemo(() => {
    if (!searchTerm || searchTerm.trim().length === 0) {
      return []
    }
    return allStudents.filter((student) =>
      student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
    )
  }, [searchTerm, allStudents])

  // 검색어나 필터링 결과가 변경될 때 자동완성 표시 여부 업데이트
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
    // 검색어가 변경되면 선택 해제
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

  const handleDeleteClick = async () => {
    if (!selectedId) return
    const student = allStudents.find((s) => s.id === selectedId)
    if (!student) return
    if (!confirm(`${student.zep_name} 학생을 삭제하시겠습니까?`)) return
    setIsDeleting(true)
    try {
      await onDelete(selectedId)
      await loadAllStudents()
      await onUpdated?.()
      setSelectedId(null)
      setSearchTerm('')
    } catch (error) {
      console.error('삭제 실패:', error)
      alert('삭제에 실패했습니다.')
    } finally {
      setIsDeleting(false)
    }
  }

  // 외부 클릭 시 자동완성 닫기
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
                        <div>
                          <p className="font-medium">{student.zep_name}</p>
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

            <Button
              variant="destructive"
              className="w-full"
              onClick={handleDeleteClick}
              disabled={!selectedId || isDeleting}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {isDeleting ? '삭제 중...' : '학생 삭제'}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}

