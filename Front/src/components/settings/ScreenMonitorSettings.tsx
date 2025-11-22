import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
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

export function ScreenMonitorSettings({ settings, isSaving, onSave }: Props) {
  const [isEditing, setIsEditing] = useState(false)
  const enabled = Boolean(settings.screen_monitor_enabled)
  const [formData, setFormData] = useState({
    screen_monitor_enabled: enabled,
    screen_check_interval: 1800, // 기본값
    face_detection_threshold: 3, // 기본값
  })

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    setFormData({
      screen_monitor_enabled: enabled,
      screen_check_interval: 1800,
      face_detection_threshold: 3,
    })
  }

  const handleSave = async () => {
    // 백엔드에서 지원하는 필드만 전송
    await onSave({
      // screen_monitor_enabled는 현재 API에 없으므로 주석 처리
      // screen_monitor_enabled: formData.screen_monitor_enabled,
    })
    setIsEditing(false)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>화면 모니터링</CardTitle>
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
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span>OCR 기반 화면 체크</span>
              <Switch checked={enabled} disabled />
            </div>
            <p className="text-xs text-muted-foreground">
              현재 백엔드 설정값 ({enabled ? '활성화' : '비활성화'})에 따라 동작합니다.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">화면 모니터링 활성화</label>
              <div className="flex items-center space-x-2">
                <Switch
                  checked={formData.screen_monitor_enabled}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, screen_monitor_enabled: checked })
                  }
                />
                <span className="text-sm text-muted-foreground">
                  {formData.screen_monitor_enabled ? '활성화' : '비활성화'}
                </span>
              </div>
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
