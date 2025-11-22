import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SettingsResponse } from '@/types/settings'

interface Props {
  settings: SettingsResponse
}

export function SlackSettings({ settings }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Slack 연동</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span>봇 연결 상태</span>
          <Badge variant={settings.slack_connected ? 'success' : 'destructive'}>
            {settings.slack_connected ? '연결됨' : '연결 안 됨'}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Slack Socket Mode를 통해 ZEP 이벤트를 수신합니다.
        </p>
        <p className="text-xs text-muted-foreground pt-2 border-t border-border/60">
          ⚠️ Slack 설정은 Railway 환경변수로 관리됩니다. 변경은 Railway 대시보드에서만 가능합니다.
        </p>
      </CardContent>
    </Card>
  )
}
