import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SettingsResponse } from '@/types/settings'

interface Props {
  settings: SettingsResponse
}

export function DiscordSettings({ settings }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Discord 연동</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span>봇 연결 상태</span>
          <Badge variant={settings.discord_connected ? 'success' : 'destructive'}>
            {settings.discord_connected ? '연결됨' : '연결 안 됨'}
          </Badge>
        </div>
        <div className="flex items-center justify-between">
          <span>관리자 등록 수</span>
          <span className="font-semibold">{settings.admin_count}명</span>
        </div>
        <p className="text-xs text-muted-foreground pt-2 border-t border-border/60">
          ⚠️ Discord 설정은 Railway 환경변수로 관리됩니다. 변경은 Railway 대시보드에서만 가능합니다.
        </p>
      </CardContent>
    </Card>
  )
}
