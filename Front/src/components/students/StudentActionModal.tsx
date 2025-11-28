import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { MessageSquare, History, UserCog } from 'lucide-react'
import type { Student } from '@/types/student'

interface StudentActionModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  student: Student | null
  onSelectDM: () => void
  onSelectLog: () => void
  onSelectStatus: () => void
}

export function StudentActionModal({ open, onOpenChange, student, onSelectDM, onSelectLog, onSelectStatus }: StudentActionModalProps) {
  if (!student) return null

  const handleDMClick = () => {
    onOpenChange(false)
    onSelectDM()
  }

  const handleLogClick = () => {
    onOpenChange(false)
    onSelectLog()
  }

  const handleStatusClick = () => {
    onOpenChange(false)
    onSelectStatus()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>학생 선택</DialogTitle>
          <DialogDescription>
            {student.zep_name}님에 대한 작업을 선택하세요.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-4">
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={handleLogClick}
          >
            <History className="mr-2 h-4 w-4" />
            학생 로그 기록
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={handleDMClick}
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            DM 발신
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={handleStatusClick}
          >
            <UserCog className="mr-2 h-4 w-4" />
            학생 상태 관리
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

