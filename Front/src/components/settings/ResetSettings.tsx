import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Play, Pause, RotateCcw } from 'lucide-react'
import type { SettingsResponse } from '@/types/settings'

interface Props {
  settings: SettingsResponse
}

export function ResetSettings({ settings }: Props) {
  const [isResetting, setIsResetting] = useState(false)
  const [isPausing, setIsPausing] = useState(false)
  const [isResuming, setIsResuming] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const handleReset = async () => {
    if (!confirm('모든 학생의 상태를 초기화하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      return
    }

    setIsResetting(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/settings/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '초기화 실패')
      }

      setMessage({ type: 'success', text: '초기화가 완료되었습니다.' })
      // 페이지 새로고침하여 최신 상태 반영
      setTimeout(() => {
        window.location.reload()
      }, 1000)
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '초기화 중 오류가 발생했습니다.',
      })
    } finally {
      setIsResetting(false)
    }
  }

  const handlePause = async () => {
    setIsPausing(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/settings/pause-alerts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '알람 중지 실패')
      }

      setMessage({ type: 'success', text: '알람이 중지되었습니다.' })
      setTimeout(() => {
        window.location.reload()
      }, 1000)
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '알람 중지 중 오류가 발생했습니다.',
      })
    } finally {
      setIsPausing(false)
    }
  }

  const handleResume = async () => {
    setIsResuming(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/settings/resume-alerts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '알람 시작 실패')
      }

      setMessage({ type: 'success', text: '알람이 시작되었습니다.' })
      setTimeout(() => {
        window.location.reload()
      }, 1000)
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '알람 시작 중 오류가 발생했습니다.',
      })
    } finally {
      setIsResuming(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>초기화 및 제어</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {message && (
          <div
            className={`rounded-md p-3 text-sm ${
              message.type === 'error'
                ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                : 'bg-green-500/10 text-green-500 border border-green-500/20'
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">일일 초기화 시간</label>
            <Input
              type="time"
              value={settings.daily_reset_time || ''}
              disabled
              className="bg-muted"
            />
            <p className="text-xs text-muted-foreground">
              초기화 시간은 스케줄 설정에서 변경할 수 있습니다.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Button
              onClick={handleReset}
              disabled={isResetting}
              variant="destructive"
              className="w-full"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              {isResetting ? '초기화 중...' : '상태 초기화'}
            </Button>
            <p className="text-xs text-muted-foreground">
              모든 학생의 카메라 상태 및 알림 기록을 초기화합니다.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <Button
                onClick={handlePause}
                disabled={isPausing || isResuming}
                variant="outline"
                className="flex-1"
              >
                <Pause className="mr-2 h-4 w-4" />
                {isPausing ? '중지 중...' : '알람 중지'}
              </Button>
              <Button
                onClick={handleResume}
                disabled={isPausing || isResuming}
                variant="outline"
                className="flex-1"
              >
                <Play className="mr-2 h-4 w-4" />
                {isResuming ? '시작 중...' : '알람 시작'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              알람 발송을 일시 중지하거나 재개합니다.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

