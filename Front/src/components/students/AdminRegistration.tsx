import { useCallback, useEffect, useState, useRef, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { fetchStudents, updateAdminStatus } from '@/services/studentService'
import type { Student } from '@/types/student'
import { UserPlus, UserMinus, Shield } from 'lucide-react'

interface AdminRegistrationProps {
  onUpdated?: () => Promise<void> | void
}

export function AdminRegistration({ onUpdated }: AdminRegistrationProps) {
  const [allNonAdminStudents, setAllNonAdminStudents] = useState<Student[]>([])
  const [allAdminStudents, setAllAdminStudents] = useState<Student[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionsRef = useRef<HTMLDivElement>(null)

  // 관리자 삭제용 state
  const [deleteSearchTerm, setDeleteSearchTerm] = useState('')
  const [deleteSelectedId, setDeleteSelectedId] = useState<number | null>(null)
  const [deleteShowSuggestions, setDeleteShowSuggestions] = useState(false)
  const [deleteFocusedIndex, setDeleteFocusedIndex] = useState(-1)
  const deleteInputRef = useRef<HTMLInputElement>(null)
  const deleteSuggestionsRef = useRef<HTMLDivElement>(null)

  const loadAllStudents = useCallback(async () => {
    setIsLoading(true)
    try {
      const [nonAdminResponse, adminResponse] = await Promise.all([
        fetchStudents({ limit: 100, is_admin: false }),
        fetchStudents({ limit: 100, is_admin: true }),
      ])
      setAllNonAdminStudents(nonAdminResponse.data)
      setAllAdminStudents(adminResponse.data)
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
    return allNonAdminStudents.filter((student) =>
      student.zep_name.toLowerCase().includes(searchTerm.toLowerCase())
    )
  }, [searchTerm, allNonAdminStudents])

  const filteredAdminSuggestions = useMemo(() => {
    if (!deleteSearchTerm || deleteSearchTerm.trim().length === 0) {
      return []
    }
    return allAdminStudents.filter((admin) =>
      admin.zep_name.toLowerCase().includes(deleteSearchTerm.toLowerCase())
    )
  }, [deleteSearchTerm, allAdminStudents])

  useEffect(() => {
    if (searchTerm && searchTerm.trim().length > 0 && filteredSuggestions.length > 0) {
      setShowSuggestions(true)
    } else {
      setShowSuggestions(false)
    }
  }, [searchTerm, filteredSuggestions.length])

  useEffect(() => {
    if (deleteSearchTerm && deleteSearchTerm.trim().length > 0 && filteredAdminSuggestions.length > 0) {
      setDeleteShowSuggestions(true)
    } else {
      setDeleteShowSuggestions(false)
    }
  }, [deleteSearchTerm, filteredAdminSuggestions.length])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setSearchTerm(value)
    setFocusedIndex(-1)
    const currentStudent = allNonAdminStudents.find(s => s.id === selectedId)
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

  const handlePromote = async () => {
    if (!selectedId) return

    const student = allNonAdminStudents.find((s) => s.id === selectedId)
    if (!student) return

    if (!confirm(`${student.zep_name}님을 관리자로 지정하시겠습니까?`)) {
      return
    }

    setIsSubmitting(true)
    try {
      await updateAdminStatus(selectedId, true)
      await loadAllStudents()
      await onUpdated?.()
      setSelectedId(null)
      setSearchTerm('')
    } catch {
      alert('관리자 권한 부여에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setDeleteSearchTerm(value)
    setDeleteFocusedIndex(-1)
    const currentAdmin = allAdminStudents.find(s => s.id === deleteSelectedId)
    if (!currentAdmin || value !== currentAdmin.zep_name) {
      setDeleteSelectedId(null)
    }
  }

  const handleSelectAdmin = (admin: Student) => {
    setDeleteSearchTerm(admin.zep_name)
    setDeleteSelectedId(admin.id)
    setDeleteShowSuggestions(false)
    setDeleteFocusedIndex(-1)
  }

  const handleDeleteKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!deleteShowSuggestions || filteredAdminSuggestions.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setDeleteFocusedIndex((prev) =>
        prev < filteredAdminSuggestions.length - 1 ? prev + 1 : prev
      )
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setDeleteFocusedIndex((prev) => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Enter' && deleteFocusedIndex >= 0) {
      e.preventDefault()
      handleSelectAdmin(filteredAdminSuggestions[deleteFocusedIndex])
    } else if (e.key === 'Escape') {
      setDeleteShowSuggestions(false)
    }
  }

  const handleDemote = async () => {
    if (!deleteSelectedId) return

    const admin = allAdminStudents.find((s) => s.id === deleteSelectedId)
    if (!admin) return

    if (!confirm(`${admin.zep_name}님의 관리자 권한을 해제하시겠습니까?`)) {
      return
    }

    setIsSubmitting(true)
    try {
      await updateAdminStatus(deleteSelectedId, false)
      await loadAllStudents()
      await onUpdated?.()
      setDeleteSelectedId(null)
      setDeleteSearchTerm('')
    } catch {
      alert('관리자 권한 해제에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 외부 클릭 시 자동완성 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node
      
      if (
        inputRef.current &&
        !inputRef.current.contains(target) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(target)
      ) {
        setShowSuggestions(false)
      }
      
      if (
        deleteInputRef.current &&
        !deleteInputRef.current.contains(target) &&
        deleteSuggestionsRef.current &&
        !deleteSuggestionsRef.current.contains(target)
      ) {
        setDeleteShowSuggestions(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            관리자 등록
          </CardTitle>
          <CardDescription>이름으로 검색하여 학생을 선택하고 관리자 권한을 부여할 수 있습니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
                        <Shield className="h-4 w-4 text-primary" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Button
            className="w-full"
            onClick={handlePromote}
            disabled={!selectedId || isSubmitting}
          >
            <UserPlus className="mr-2 h-4 w-4" />
            {isSubmitting ? '적용 중...' : '관리자 지정'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserMinus className="h-5 w-5 text-destructive" />
            관리자 삭제
          </CardTitle>
          <CardDescription>이름으로 검색하여 관리자를 선택하고 권한을 해제할 수 있습니다.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">관리자 목록을 불러오는 중입니다...</p>
          ) : allAdminStudents.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">등록된 관리자가 없습니다.</p>
          ) : (
            <>
              <div className="relative">
                <Input
                  ref={deleteInputRef}
                  placeholder="이름으로 검색..."
                  value={deleteSearchTerm}
                  onChange={handleDeleteSearchChange}
                  onKeyDown={handleDeleteKeyDown}
                  onFocus={() => {
                    if (deleteSearchTerm && deleteSearchTerm.trim().length > 0 && filteredAdminSuggestions.length > 0) {
                      setDeleteShowSuggestions(true)
                    }
                  }}
                  className="w-full"
                />
                {deleteShowSuggestions && deleteSearchTerm && deleteSearchTerm.trim().length > 0 && filteredAdminSuggestions.length > 0 && (
                  <div
                    ref={deleteSuggestionsRef}
                    className="absolute z-[100] w-full mt-1 bg-background border border-border rounded-md shadow-lg max-h-60 overflow-auto"
                    style={{ top: '100%' }}
                  >
                    {filteredAdminSuggestions.map((admin, index) => (
                      <div
                        key={admin.id}
                        className={`px-3 py-2 cursor-pointer transition-colors ${
                          index === deleteFocusedIndex
                            ? 'bg-primary/10 text-primary-foreground'
                            : 'hover:bg-muted/20'
                        }`}
                        onClick={() => handleSelectAdmin(admin)}
                        onMouseEnter={() => setDeleteFocusedIndex(index)}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{admin.zep_name}</p>
                            {admin.discord_id && (
                              <p className="text-xs text-muted-foreground">Discord: {admin.discord_id}</p>
                            )}
                          </div>
                          {deleteSelectedId === admin.id && (
                            <Shield className="h-4 w-4 text-primary" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Button
                variant="outline"
                className="w-full border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
                onClick={handleDemote}
                disabled={!deleteSelectedId || isSubmitting}
              >
                <UserMinus className="mr-2 h-4 w-4" />
                {isSubmitting ? '적용 중...' : '관리자 권한 해제'}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
