import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RefreshCw, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { syncGoogleSheets, type SyncResult } from '@/services/googleSheetsService'

export function GoogleSheetsSyncSettings() {
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null)

  const handleSync = async () => {
    setIsSyncing(true)
    setSyncResult(null)

    try {
      const response = await syncGoogleSheets()
      setSyncResult(response)

      if (response.synced_at) {
        setLastSyncTime(response.synced_at)
      }
    } catch (error: any) {
      setSyncResult({
        success: false,
        error: error.message || '동기화에 실패했습니다.'
      })
    } finally {
      setIsSyncing(false)
    }
  }

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>구글시트 상태 동기화</CardTitle>
        <CardDescription>
          Google Sheets에서 학생 상태 데이터를 가져와 시스템에 반영합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 동기화 버튼 */}
        <Button
          onClick={handleSync}
          disabled={isSyncing}
          className="w-full gap-2"
        >
          {isSyncing ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              동기화 중...
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4" />
              지금 동기화
            </>
          )}
        </Button>

        {/* 마지막 동기화 시간 */}
        {lastSyncTime && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>마지막 동기화: {formatDateTime(lastSyncTime)}</span>
          </div>
        )}

        {/* 동기화 결과 */}
        {syncResult && (
          <div className="space-y-3">
            {syncResult.success ? (
              <>
                <Alert className="border-green-200 bg-green-50">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-800">
                    동기화가 완료되었습니다.
                  </AlertDescription>
                </Alert>

                {/* 통계 */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg border p-3">
                    <div className="text-muted-foreground">처리됨</div>
                    <div className="text-2xl font-bold">{syncResult.processed || 0}</div>
                  </div>
                  <div className="rounded-lg border p-3">
                    <div className="text-muted-foreground">업데이트됨</div>
                    <div className="text-2xl font-bold text-green-600">{syncResult.updated || 0}</div>
                  </div>
                  <div className="rounded-lg border p-3">
                    <div className="text-muted-foreground">건너뜀</div>
                    <div className="text-2xl font-bold text-gray-500">{syncResult.skipped || 0}</div>
                  </div>
                  <div className="rounded-lg border p-3">
                    <div className="text-muted-foreground">오류</div>
                    <div className="text-2xl font-bold text-red-600">{syncResult.errors || 0}</div>
                  </div>
                </div>

                {/* 업데이트 상세 */}
                {syncResult.updated_details && syncResult.updated_details.length > 0 && (
                  <div className="rounded-lg border p-4 bg-blue-50 border-blue-200">
                    <div className="font-semibold mb-3 text-blue-900">업데이트된 학생 목록:</div>
                    <div className="space-y-2">
                      {syncResult.updated_details.map((detail, idx) => (
                        <div key={idx} className="flex items-start gap-3 text-sm bg-white rounded p-3 border">
                          <div className="flex-1">
                            <div className="font-medium text-gray-900">{detail.name}</div>
                            <div className="text-gray-600 space-y-1 mt-1">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-blue-600">{detail.status}</span>
                                {detail.time && <span className="text-xs">({detail.time})</span>}
                                {detail.protected && (
                                  <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded">
                                    보호됨
                                  </span>
                                )}
                              </div>
                              <div className="text-xs">
                                {detail.start_date}
                                {detail.end_date && detail.end_date !== detail.start_date && ` ~ ${detail.end_date}`}
                              </div>
                              {detail.reason && (
                                <div className="text-xs text-gray-500">사유: {detail.reason}</div>
                              )}
                              {!detail.is_immediate && (
                                <div className="text-xs text-purple-600">📅 예약됨</div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 오류 상세 */}
                {syncResult.error_details && syncResult.error_details.length > 0 && (
                  <Alert className="border-yellow-200 bg-yellow-50">
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800">
                      <div className="font-semibold mb-2">처리 중 오류 발생:</div>
                      <ul className="list-disc list-inside space-y-1 text-sm">
                        {syncResult.error_details.map((error, idx) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}
              </>
            ) : (
              <Alert className="border-red-200 bg-red-50">
                <AlertCircle className="h-4 w-4 text-red-600" />
                <AlertDescription className="text-red-800">
                  {syncResult.error || '동기화에 실패했습니다.'}
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* 안내 */}
        <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
          <p>• Google Sheets URL은 "연동 토큰 설정"에서 설정할 수 있습니다.</p>
          <p>• 오늘 날짜의 상태는 즉시 적용되고, 미래 날짜는 예약됩니다.</p>
          <p>• 지원하는 상태: 지각, 조퇴, 외출, 휴가, 결석</p>
        </div>
      </CardContent>
    </Card>
  )
}
