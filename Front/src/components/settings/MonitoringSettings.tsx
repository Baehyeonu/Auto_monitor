import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { MoreVertical, Check, X } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { SettingsResponse, SettingsUpdatePayload } from '@/types/settings'

interface Props {
  settings: SettingsResponse
  isSaving: boolean
  onSave: (payload: SettingsUpdatePayload) => Promise<void>
}

type FormValues = {
  camera_off_threshold: number
  alert_cooldown: number
  leave_alert_threshold: number
}

export function MonitoringSettings({ settings, isSaving, onSave }: Props) {
  const [isEditing, setIsEditing] = useState(false)
  const { register, handleSubmit, reset } = useForm<FormValues>({
    defaultValues: {
      camera_off_threshold: settings.camera_off_threshold,
      alert_cooldown: settings.alert_cooldown,
      leave_alert_threshold: settings.leave_alert_threshold,
    },
  })

  useEffect(() => {
    reset({
      camera_off_threshold: settings.camera_off_threshold,
      alert_cooldown: settings.alert_cooldown,
      leave_alert_threshold: settings.leave_alert_threshold,
    })
  }, [reset, settings])

  const handleEdit = () => {
    setIsEditing(true)
    reset({
      camera_off_threshold: settings.camera_off_threshold,
      alert_cooldown: settings.alert_cooldown,
      leave_alert_threshold: settings.leave_alert_threshold,
    })
  }

  const handleCancel = () => {
    setIsEditing(false)
    reset({
      camera_off_threshold: settings.camera_off_threshold,
      alert_cooldown: settings.alert_cooldown,
      leave_alert_threshold: settings.leave_alert_threshold,
    })
  }

  const submit = async (values: FormValues) => {
    await onSave(values)
    setIsEditing(false)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>모니터링 임계값</CardTitle>
        {!isEditing && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleEdit}>수정</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </CardHeader>
      <CardContent>
        {!isEditing ? (
          <div className="grid gap-4 md:grid-cols-3 text-sm">
            <div className="space-y-1">
              <span className="text-muted-foreground">카메라 OFF 임계값</span>
              <p className="font-medium">{settings.camera_off_threshold}분</p>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground">DM 쿨다운</span>
              <p className="font-medium">{settings.alert_cooldown}분</p>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground">접속 종료 알림</span>
              <p className="font-medium">{settings.leave_alert_threshold}분</p>
            </div>
          </div>
        ) : (
          <form className="grid gap-4 md:grid-cols-3" onSubmit={handleSubmit(submit)}>
            <div className="space-y-2">
              <label className="text-sm font-medium">카메라 OFF 임계값 (분)</label>
              <Input
                type="number"
                {...register('camera_off_threshold', { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">DM 쿨다운 (분)</label>
              <Input
                type="number"
                {...register('alert_cooldown', { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">접속 종료 알림 (분)</label>
              <Input
                type="number"
                {...register('leave_alert_threshold', { valueAsNumber: true })}
              />
            </div>
            <div className="md:col-span-3 flex gap-2">
              <Button type="submit" disabled={isSaving} className="flex-1">
                <Check className="mr-2 h-4 w-4" />
                {isSaving ? '저장 중...' : '저장'}
              </Button>
              <Button type="button" variant="outline" onClick={handleCancel} disabled={isSaving} className="flex-1">
                <X className="mr-2 h-4 w-4" />
                취소
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
