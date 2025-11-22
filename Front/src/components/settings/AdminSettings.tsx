import { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchStudents, updateAdminStatus } from '@/services/studentService'
import type { Student } from '@/types/student'
import { UserPlus, UserMinus, Shield } from 'lucide-react'

interface AdminSettingsProps {
  onUpdated?: () => Promise<void> | void
}

export function AdminSettings({ onUpdated }: AdminSettingsProps) {
  const [allStudents, setAllStudents] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [promoteId, setPromoteId] = useState<number | ''>('')
  const [demoteId, setDemoteId] = useState<number | ''>('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const loadAllStudents = useCallback(async () => {
    setIsLoading(true)
    try {
      // 충분히 큰 limit으로 전체 목록을 가져온다.
      const response = await fetchStudents({ limit: 500 })
      setAllStudents(response.data)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAllStudents()
  }, [loadAllStudents])

  const handleUpdate = async (targetId: number, nextState: boolean) => {
    if (!confirm(nextState ? '이 사용자를 관리자로 지정하시겠습니까?' : '이 사용자의 관리자 권한을 해제하시겠습니까?')) {
      return
    }

    setIsSubmitting(true)
    try {
      await updateAdminStatus(targetId, nextState)
      await loadAllStudents()
      await onUpdated?.()
      if (nextState) {
        setPromoteId('')
      } else {
        setDemoteId('')
      }
    } catch (error) {
      console.error(error)
      alert('관리자 권한 변경에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const adminStudents = allStudents.filter((student) => student.is_admin)
  const nonAdminStudents = allStudents.filter((student) => !student.is_admin)

  // 검색 필터링
  const filteredAdminStudents = adminStudents.filter((student) =>
    student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
  )
  const filteredNonAdminStudents = nonAdminStudents.filter((student) =>
    student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          관리자 권한 관리
        </CardTitle>
        <CardDescription>학생을 선택해 관리자 권한을 부여하거나 해제할 수 있습니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">학생 목록을 불러오는 중입니다...</p>
        ) : (
          <>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <UserPlus className="h-4 w-4 text-primary" />
                <p className="text-sm font-semibold">관리자 권한 부여</p>
              </div>
              <div className="space-y-2">
                <Input
                  placeholder="이름으로 검색..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full"
                />
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                  value={promoteId}
                  onChange={(event) => setPromoteId(event.target.value ? Number(event.target.value) : '')}
                >
                  <option value="">관리자로 지정할 학생 선택</option>
                  {filteredNonAdminStudents.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.zep_name} {student.discord_id ? `(Discord: ${student.discord_id})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                className="w-full"
                onClick={() => promoteId && handleUpdate(Number(promoteId), true)}
                disabled={!promoteId || isSubmitting}
              >
                <UserPlus className="mr-2 h-4 w-4" />
                {isSubmitting && promoteId ? '적용 중...' : '관리자 지정'}
              </Button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <UserMinus className="h-4 w-4 text-destructive" />
                <p className="text-sm font-semibold">관리자 권한 해제</p>
              </div>
              <select
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                value={demoteId}
                onChange={(event) => setDemoteId(event.target.value ? Number(event.target.value) : '')}
              >
                <option value="">권한을 해제할 관리자 선택</option>
                {filteredAdminStudents.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.zep_name} {student.discord_id ? `(Discord: ${student.discord_id})` : ''}
                  </option>
                ))}
              </select>
              <Button
                variant="outline"
                className="w-full border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
                onClick={() => demoteId && handleUpdate(Number(demoteId), false)}
                disabled={!demoteId || isSubmitting}
              >
                <UserMinus className="mr-2 h-4 w-4" />
                {isSubmitting && demoteId ? '적용 중...' : '관리자 해제'}
              </Button>
            </div>

            <div className="rounded-lg border border-border/60 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                <p className="text-sm font-semibold">현재 관리자 목록 ({adminStudents.length})</p>
              </div>
              {adminStudents.length === 0 ? (
                <p className="text-sm text-muted-foreground">등록된 관리자가 없습니다.</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {adminStudents.map((admin) => (
                    <div
                      key={admin.id}
                      className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <Shield className="h-3.5 w-3.5 text-primary" />
                        <span className="text-sm font-medium">{admin.zep_name}</span>
                      </div>
                      {admin.discord_id && (
                        <span className="text-xs text-muted-foreground">Discord: {admin.discord_id}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

