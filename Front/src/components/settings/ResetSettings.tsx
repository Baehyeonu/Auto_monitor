import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Play, Pause, RotateCcw, MoreVertical, Check, X } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { SettingsResponse } from '@/types/settings'

interface Props {
  settings: SettingsResponse
}

export function ResetSettings({ settings }: Props) {
  const [isResetting, setIsResetting] = useState(false)
  const [isPausing, setIsPausing] = useState(false)
  const [isResuming, setIsResuming] = useState(false)
  const [isEditingTime, setIsEditingTime] = useState(false)
  const [isSavingTime, setIsSavingTime] = useState(false)
  const [resetTime, setResetTime] = useState(settings.daily_reset_time || '')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const refreshPage = () => {
    setTimeout(() => {
      window.location.reload()
    }, 1000)
  }

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
      refreshPage()
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
      refreshPage()
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
      refreshPage()
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '알람 시작 중 오류가 발생했습니다.',
      })
    } finally {
      setIsResuming(false)
    }
  }

  const handleEditTime = () => {
    setIsEditingTime(true)
    setResetTime(settings.daily_reset_time || '')
    setMessage(null)
  }

  const handleCancelTime = () => {
    setIsEditingTime(false)
    setResetTime(settings.daily_reset_time || '')
    setMessage(null)
  }

  const handleSaveResetTime = async () => {
    setIsSavingTime(true)
    setMessage(null)

    try {
      const response = await fetch('/api/v1/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          daily_reset_time: resetTime || null,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '초기화 시간 저장 실패')
      }

      setMessage({ type: 'success', text: '초기화 시간이 저장되었습니다.' })
      setIsEditingTime(false)
      refreshPage()
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '초기화 시간 저장 중 오류가 발생했습니다.',
      })
    } finally {
      setIsSavingTime(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>초기화 및 제어</CardTitle>
        {!isEditingTime && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleEditTime}>초기화 시간 수정</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
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
            {!isEditingTime ? (
              <>
                <div className="flex items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <span className={settings.daily_reset_time ? '' : 'text-muted-foreground'}>
                    {settings.daily_reset_time || '설정 안 됨'}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  매일 지정된 시간에 모든 학생의 상태와 알림 기록을 초기화합니다.
                </p>
              </>
            ) : (
              <>
                <Input
                  type="time"
                  value={resetTime}
                  onChange={(e) => setResetTime(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  매일 지정된 시간에 모든 학생의 상태와 알림 기록을 초기화합니다.
                </p>
                <div className="flex gap-2">
                  <Button
                    onClick={handleSaveResetTime}
                    disabled={isSavingTime}
                    className="flex-1"
                  >
                    <Check className="mr-2 h-4 w-4" />
                    {isSavingTime ? '저장 중...' : '저장'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleCancelTime}
                    disabled={isSavingTime}
                    className="flex-1"
                  >
                    <X className="mr-2 h-4 w-4" />
                    취소
                  </Button>
                </div>
              </>
            )}
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

