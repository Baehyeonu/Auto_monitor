import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { getSettings, updateSettings } from '@/services/settingsService'
import type { SettingsResponse } from '@/types/settings'

export function StatusParsingSettings() {
  const [enabled, setEnabled] = useState(false)
  const [campFilter, setCampFilter] = useState('')
  const [channelConfigured, setChannelConfigured] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    setIsLoading(true)
    try {
      const data: SettingsResponse = await getSettings()
      setEnabled(data.status_parsing_enabled || false)
      setCampFilter(data.status_camp_filter || '')
      setChannelConfigured(data.slack_status_channel_configured || false)
    } catch (error) {
      setMessage({ type: 'error', text: '설정을 불러오는데 실패했습니다.' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    setMessage(null)
    try {
      await updateSettings({
        status_parsing_enabled: enabled,
        status_camp_filter: campFilter.trim() || null,
      })
      setMessage({ type: 'success', text: '상태 파싱 설정이 저장되었습니다.' })
    } catch (error) {
      setMessage({ type: 'error', text: '설정 저장에 실패했습니다.' })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>상태 자동 변경</CardTitle>
          <CardDescription>OZ헬프센터 슬랙 채널에서 상태 메시지를 자동으로 파싱합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>상태 자동 변경</CardTitle>
        <CardDescription>
          OZ헬프센터 슬랙 채널에서 조퇴/외출/결석/휴가 메시지를 자동으로 파싱하여 학생 상태를 변경합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 채널 설정 상태 */}
        <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
          {channelConfigured ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-sm">상태 채널이 설정되어 있습니다.</span>
            </>
          ) : (
            <>
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <span className="text-sm">
                상태 채널이 설정되지 않았습니다. .env 파일에서 SLACK_STATUS_CHANNEL_ID를 설정해주세요.
              </span>
            </>
          )}
        </div>

        {/* 활성화 스위치 */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="status-parsing-enabled">상태 파싱 활성화</Label>
            <p className="text-sm text-muted-foreground">
              슬랙 메시지를 자동으로 파싱하여 학생 상태를 변경합니다.
            </p>
          </div>
          <Switch
            id="status-parsing-enabled"
            checked={enabled}
            onCheckedChange={setEnabled}
            disabled={!channelConfigured || isSaving}
          />
        </div>

        {/* 캠프 필터 */}
        <div className="space-y-2">
          <Label htmlFor="camp-filter">캠프 필터</Label>
          <Input
            id="camp-filter"
            placeholder="예: 1인 창업가 1기"
            value={campFilter}
            onChange={(e) => setCampFilter(e.target.value)}
            disabled={!enabled || isSaving}
          />
          <p className="text-sm text-muted-foreground">
            해당 캠프의 메시지만 파싱합니다. 비어있으면 모든 캠프의 메시지를 파싱합니다.
          </p>
        </div>

        {/* 안내 메시지 */}
        <div className="p-4 rounded-lg border bg-card space-y-2">
          <p className="text-sm font-medium">파싱되는 상태:</p>
          <ul className="text-sm text-muted-foreground space-y-1 ml-4 list-disc">
            <li>조퇴 🟣 - 퇴실 시간에 상태 적용</li>
            <li>외출 🟠 - 외출 시작 시간에 상태 적용</li>
            <li>결석 🔴 - 기간 동안 상태 유지, 초기화 방지</li>
            <li>휴가 🌴 - 기간 동안 상태 유지, 초기화 방지</li>
          </ul>
          <p className="text-sm text-muted-foreground mt-3">
            * 상태 변경 시 웹 대시보드에 확인 팝업이 표시되며, 취소 버튼으로 롤백할 수 있습니다.
          </p>
        </div>

        {/* 메시지 */}
        {message && (
          <div
            className={`p-3 rounded-md text-sm ${
              message.type === 'success'
                ? 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                : 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* 저장 버튼 */}
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={!channelConfigured || isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                저장 중...
              </>
            ) : (
              '저장'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
