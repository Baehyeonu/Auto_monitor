import { useEffect, useMemo, useState } from 'react'
import { StudentForm } from '@/components/students/StudentForm'
import { StudentList } from '@/components/students/StudentList'
import { BulkImport } from '@/components/students/BulkImport'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { fetchStudents, createStudent, deleteStudent } from '@/services/studentService'
import type { Student } from '@/types/student'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [admins, setAdmins] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<'students' | 'admins'>('students')
  const [actionTab, setActionTab] = useState<'create' | 'bulk' | 'delete' | 'admin'>('create')

  const loadStudents = async () => {
    setIsLoading(true)
    try {
      const [studentsData, adminsData] = await Promise.all([
        fetchStudents({ limit: 100, is_admin: false }),
        fetchStudents({ limit: 100, is_admin: true }),
      ])
      setStudents(studentsData.data)
      setAdmins(adminsData.data)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadStudents()
  }, [])

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
        content: (
          <StudentDeletePanel students={students} onDelete={handleDelete} isLoading={isLoading} />
        ),
      },
      {
        value: 'admin',
        label: '관리자 등록',
        content: <AdminRegistrationPanel admins={admins} />,
      },
    ],
    [admins, handleDelete, handleSubmit, isLoading, isSubmitting, students],
  )

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'students' | 'admins')}>
        <TabsList>
          <TabsTrigger value="students">학생 ({students.length})</TabsTrigger>
          <TabsTrigger value="admins">관리자 ({admins.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="students" className="mt-4 space-y-4">
          <StudentList
            students={students}
            isLoading={isLoading}
            onRefresh={loadStudents}
            onDelete={handleDelete}
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
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

type DeletePanelProps = {
  students: Student[]
  onDelete: (id: number) => Promise<void>
  isLoading: boolean
}

function StudentDeletePanel({ students, onDelete, isLoading }: DeletePanelProps) {
  const [selectedId, setSelectedId] = useState<number | ''>('')
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDeleteClick = async () => {
    if (!selectedId) return
    const student = students.find((s) => s.id === Number(selectedId))
    if (!student) return
    if (!confirm(`${student.zep_name} 학생을 삭제하시겠습니까?`)) return
    setIsDeleting(true)
    try {
      await onDelete(Number(selectedId))
      setSelectedId('')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>학생 삭제</CardTitle>
        <CardDescription>삭제할 학생을 선택 후 삭제 버튼을 눌러주세요.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <select
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          value={selectedId}
          onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : '')}
          disabled={isLoading}
        >
          <option value="">삭제할 학생 선택</option>
          {students.map((student) => (
            <option key={student.id} value={student.id}>
              {student.zep_name} (ID: {student.id})
            </option>
          ))}
        </select>
        <Button
          variant="destructive"
          className="w-full"
          onClick={handleDeleteClick}
          disabled={!selectedId || isDeleting}
        >
          {isDeleting ? '삭제 중...' : '학생 삭제'}
        </Button>
      </CardContent>
    </Card>
  )
}

function AdminRegistrationPanel({ admins }: { admins: Student[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>관리자 등록</CardTitle>
        <CardDescription>
          관리자 권한은 환경변수 <code className="rounded bg-muted px-1">ADMIN_USER_IDS</code> 로 관리됩니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Railway 대시보드 &gt; Variables 에서 <code>ADMIN_USER_IDS</code> 에 Discord ID를 추가하면 관리자 목록에
          반영됩니다. 여러 명을 등록할 때는 쉼표로 구분하세요. (예: <code>1234567890,9876543210</code>)
        </p>
        <div className="rounded-lg border border-border/60 p-4">
          <p className="text-sm font-semibold">현재 등록된 관리자</p>
          {admins.length === 0 ? (
            <p className="text-sm text-muted-foreground">등록된 관리자가 없습니다.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {admins.map((admin) => (
                <li key={admin.id} className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-1.5">
                  <span>{admin.zep_name}</span>
                  {admin.discord_id && <span className="text-xs text-muted-foreground">ID: {admin.discord_id}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <Button variant="outline" asChild>
          <a
            href="https://railway.app"
            target="_blank"
            rel="noreferrer"
          >
            Railway Variables 열기
          </a>
        </Button>
      </CardContent>
    </Card>
  )
}

