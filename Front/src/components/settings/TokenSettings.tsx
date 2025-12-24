import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, Eye, EyeOff, Save } from 'lucide-react'
import { useSettings } from '@/hooks/useSettings'

export function TokenSettings() {
  const { settings, isSaving, saveSettings } = useSettings()
  const [showTokens, setShowTokens] = useState(false)
  const [formData, setFormData] = useState({
    discord_bot_token: '',
    discord_server_id: '',
    slack_bot_token: '',
    slack_app_token: '',
    slack_channel_id: '',
    google_sheets_url: '',
    camp_name: '',
    cohort_name: '',
  })

  // settings가 로드되면 초기값 설정
  useEffect(() => {
    if (settings) {
      setFormData({
        discord_bot_token: settings.discord_bot_token || '',
        discord_server_id: settings.discord_server_id || '',
        slack_bot_token: settings.slack_bot_token || '',
        slack_app_token: settings.slack_app_token || '',
        slack_channel_id: settings.slack_channel_id || '',
        google_sheets_url: settings.google_sheets_url || '',
        camp_name: settings.camp_name || '',
        cohort_name: settings.cohort_name || '',
      })
    }
  }, [settings])

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    await saveSettings(formData)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>연동 토큰 설정</CardTitle>
            <CardDescription>
              Discord, Slack, Google Sheets 연동에 필요한 토큰을 설정합니다.
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowTokens(!showTokens)}
            className="gap-2"
          >
            {showTokens ? (
              <>
                <EyeOff className="h-4 w-4" />
                숨기기
              </>
            ) : (
              <>
                <Eye className="h-4 w-4" />
                표시
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Discord 설정 */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Discord 설정</h4>
          <div className="space-y-2">
            <Label htmlFor="discord_bot_token">Bot Token</Label>
            <Input
              id="discord_bot_token"
              type={showTokens ? 'text' : 'password'}
              value={formData.discord_bot_token}
              onChange={(e) => handleChange('discord_bot_token', e.target.value)}
              placeholder="Discord Bot Token"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="discord_server_id">Server ID</Label>
            <Input
              id="discord_server_id"
              type="text"
              value={formData.discord_server_id}
              onChange={(e) => handleChange('discord_server_id', e.target.value)}
              placeholder="Discord Server ID"
            />
          </div>
        </div>

        {/* Slack 설정 */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Slack 설정</h4>
          <div className="space-y-2">
            <Label htmlFor="slack_bot_token">Bot Token</Label>
            <Input
              id="slack_bot_token"
              type={showTokens ? 'text' : 'password'}
              value={formData.slack_bot_token}
              onChange={(e) => handleChange('slack_bot_token', e.target.value)}
              placeholder="Slack Bot Token (xoxb-...)"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="slack_app_token">App Token</Label>
            <Input
              id="slack_app_token"
              type={showTokens ? 'text' : 'password'}
              value={formData.slack_app_token}
              onChange={(e) => handleChange('slack_app_token', e.target.value)}
              placeholder="Slack App Token (xapp-...)"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="slack_channel_id">Channel ID</Label>
            <Input
              id="slack_channel_id"
              type="text"
              value={formData.slack_channel_id}
              onChange={(e) => handleChange('slack_channel_id', e.target.value)}
              placeholder="Slack Channel ID (C...)"
            />
          </div>
        </div>

        {/* Google Sheets 설정 */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Google Sheets 설정</h4>
          <div className="space-y-2">
            <Label htmlFor="google_sheets_url">스프레드시트 URL</Label>
            <Input
              id="google_sheets_url"
              type="text"
              value={formData.google_sheets_url}
              onChange={(e) => handleChange('google_sheets_url', e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="camp_name">캠프</Label>
            <Input
              id="camp_name"
              type="text"
              value={formData.camp_name}
              onChange={(e) => handleChange('camp_name', e.target.value)}
              placeholder="예: 창업가"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cohort_name">기수</Label>
            <Input
              id="cohort_name"
              type="text"
              value={formData.cohort_name}
              onChange={(e) => handleChange('cohort_name', e.target.value)}
              placeholder="예: 2기"
            />
          </div>
        </div>

        {/* 저장 버튼 */}
        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full gap-2"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              저장 중...
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              설정 저장
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  )
}
