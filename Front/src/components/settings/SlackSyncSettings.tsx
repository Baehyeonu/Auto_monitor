import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Loader2, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react'

export function SlackSyncSettings() {
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSync = async () => {
    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('/api/v1/settings/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '동기화에 실패했습니다.')
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Slack 동기화에 실패했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Slack 상태 동기화</CardTitle>
        <CardDescription>
          Slack 히스토리에서 최신 상태 메시지를 가져와 학생 상태를 동기화합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Button
            onClick={handleSync}
            disabled={isLoading}
            className="gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                동기화 중...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" />
                Slack에서 상태 동기화
              </>
            )}
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded-md text-sm bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {result && result.success && (
          <div className="p-3 rounded-md text-sm bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              <span>{result.message}</span>
            </div>
          </div>
        )}

        <div className="text-xs text-muted-foreground space-y-1">
          <p>• 최근 24시간 이내의 상태 메시지를 가져옵니다</p>
          <p>• 조퇴, 외출, 결석, 휴가, 지각 상태가 동기화됩니다</p>
          <p>• 과거 날짜/시간 예약은 무시됩니다</p>
        </div>
      </CardContent>
    </Card>
  )
}
