import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SettingsResponse } from '@/types/settings'

export function ScheduleSettings({ settings }: { settings: SettingsResponse }) {
  const items = [
    { label: '수업 시간', value: `${settings.class_start_time} ~ ${settings.class_end_time}` },
    { label: '점심 시간', value: `${settings.lunch_start_time} ~ ${settings.lunch_end_time}` },
    {
      label: '일일 초기화',
      value: settings.daily_reset_time ? `${settings.daily_reset_time} 실행` : '비활성화',
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>스케줄</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-muted-foreground">{item.label}</span>
            <span className="font-medium">{item.value}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

