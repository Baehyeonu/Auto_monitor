import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { API_BASE_URL } from '@/lib/constants'

export function DatabaseSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>데이터베이스/엔드포인트</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">API Endpoint</span>
          <span className="font-mono text-xs">{API_BASE_URL}</span>
        </div>
        <p className="text-xs text-muted-foreground">
          API URL은 .env 설정 (VITE_API_URL) 로 변경할 수 있습니다.
        </p>
      </CardContent>
    </Card>
  )
}

