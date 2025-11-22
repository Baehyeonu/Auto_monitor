import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SettingsResponse } from '@/types/settings'
import { Switch } from '@/components/ui/switch'

interface Props {
  settings: SettingsResponse
}

export function ScreenMonitorSettings({ settings }: Props) {
  const enabled = Boolean(settings.screen_monitor_enabled)
  return (
    <Card>
      <CardHeader>
        <CardTitle>화면 모니터링</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span>OCR 기반 화면 체크</span>
          <Switch checked={enabled} disabled />
        </div>
        <p className="text-xs text-muted-foreground">
          현재 백엔드 설정값 ({enabled ? '활성화' : '비활성화'})에 따라 동작합니다.
          프론트에서는 상태만 표시합니다.
        </p>
      </CardContent>
    </Card>
  )
}

