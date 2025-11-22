import { useEffect, useState } from 'react'
import { StudentForm } from '@/components/students/StudentForm'
import { StudentList } from '@/components/students/StudentList'
import { BulkImport } from '@/components/students/BulkImport'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { fetchStudents, createStudent, deleteStudent } from '@/services/studentService'
import type { Student } from '@/types/student'

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [admins, setAdmins] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<'students' | 'admins'>('students')

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

  return (
    <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
      <div className="space-y-4">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'students' | 'admins')}>
          <TabsList>
            <TabsTrigger value="students">학생 ({students.length})</TabsTrigger>
            <TabsTrigger value="admins">관리자 ({admins.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="students" className="mt-4">
            <StudentList
              students={students}
              isLoading={isLoading}
              onRefresh={loadStudents}
              onDelete={handleDelete}
            />
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
      <div className="space-y-4">
        <StudentForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
        <BulkImport />
      </div>
    </div>
  )
}

