import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

export function ScheduleSettings({ settings, isSaving, onSave }: Props) {
  const [isEditing, setIsEditing] = useState(false)
  const [formData, setFormData] = useState({
    class_start_time: settings.class_start_time,
    class_end_time: settings.class_end_time,
    lunch_start_time: settings.lunch_start_time,
    lunch_end_time: settings.lunch_end_time,
  })

  const handleEdit = () => {
    setIsEditing(true)
    setFormData({
      class_start_time: settings.class_start_time,
      class_end_time: settings.class_end_time,
      lunch_start_time: settings.lunch_start_time,
      lunch_end_time: settings.lunch_end_time,
    })
  }

  const handleCancel = () => {
    setIsEditing(false)
    setFormData({
      class_start_time: settings.class_start_time,
      class_end_time: settings.class_end_time,
      lunch_start_time: settings.lunch_start_time,
      lunch_end_time: settings.lunch_end_time,
    })
  }

  const handleSave = async () => {
    await onSave({
      class_start_time: formData.class_start_time,
      class_end_time: formData.class_end_time,
      lunch_start_time: formData.lunch_start_time,
      lunch_end_time: formData.lunch_end_time,
    })
    setIsEditing(false)
  }

  const items = [
    { 
      label: '수업 시간', 
      value: `${settings.class_start_time} ~ ${settings.class_end_time}`,
      fields: ['class_start_time', 'class_end_time']
    },
    { 
      label: '점심 시간', 
      value: `${settings.lunch_start_time} ~ ${settings.lunch_end_time}`,
      fields: ['lunch_start_time', 'lunch_end_time']
    },
  ]

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>스케줄</CardTitle>
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
      <CardContent className="space-y-4">
        {!isEditing ? (
          <div className="space-y-2 text-sm">
            {items.map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <span className="text-muted-foreground">{item.label}</span>
                <span className="font-medium">{item.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">수업 시작 시간</label>
              <Input
                type="time"
                value={formData.class_start_time}
                onChange={(e) => setFormData({ ...formData, class_start_time: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">수업 종료 시간</label>
              <Input
                type="time"
                value={formData.class_end_time}
                onChange={(e) => setFormData({ ...formData, class_end_time: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">점심 시작 시간</label>
              <Input
                type="time"
                value={formData.lunch_start_time}
                onChange={(e) => setFormData({ ...formData, lunch_start_time: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">점심 종료 시간</label>
              <Input
                type="time"
                value={formData.lunch_end_time}
                onChange={(e) => setFormData({ ...formData, lunch_end_time: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={isSaving} className="flex-1">
                <Check className="mr-2 h-4 w-4" />
                {isSaving ? '저장 중...' : '저장'}
              </Button>
              <Button variant="outline" onClick={handleCancel} disabled={isSaving} className="flex-1">
                <X className="mr-2 h-4 w-4" />
                취소
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
