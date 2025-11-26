import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Camera, LogIn, User, ArrowLeft } from 'lucide-react'
import type { Student } from '@/types/student'

interface SendDMModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  student: Student | null
  onBack?: () => void
}

export function SendDMModal({ open, onOpenChange, student, onBack }: SendDMModalProps) {
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendDM = async (dmType: 'camera_alert' | 'join_request' | 'face_not_visible') => {
    if (!student) return

    setIsSending(true)
    setError(null)

    try {
      const response = await fetch(
        `/api/v1/students/${student.id}/send-dm`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ dm_type: dmType }),
        }
      )

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'DM 전송 실패')
      }

      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'DM 전송 중 오류가 발생했습니다.')
    } finally {
      setIsSending(false)
    }
  }

  if (!student) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            {onBack && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onBack}
                className="h-8 w-8"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}
            <DialogTitle>DM 발신</DialogTitle>
          </div>
          <DialogDescription>
            {student.zep_name}님에게 DM을 전송합니다.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-4">
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={() => sendDM('camera_alert')}
            disabled={isSending || !student.discord_id}
          >
            <Camera className="mr-2 h-4 w-4" />
            카메라 켜주세요
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={() => sendDM('join_request')}
            disabled={isSending || !student.discord_id}
          >
            <LogIn className="mr-2 h-4 w-4" />
            접속해 주세요
          </Button>
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={() => sendDM('face_not_visible')}
            disabled={isSending || !student.discord_id}
          >
            <User className="mr-2 h-4 w-4" />
            화면에 얼굴이 안보여요
          </Button>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          {!student.discord_id && (
            <p className="text-sm text-muted-foreground">
              Discord ID가 등록되지 않은 학생입니다.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

