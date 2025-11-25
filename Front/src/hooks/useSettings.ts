import { useEffect, useState } from 'react'
import { getSettings, updateSettings } from '@/services/settingsService'
import { useSettingsStore } from '@/stores/useSettingsStore'
import type { SettingsUpdatePayload } from '@/types/settings'

export function useSettings() {
  const { settings, setSettings, isLoading, setLoading, error, setError } =
    useSettingsStore()
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (settings) return
    setLoading(true)
    getSettings()
      .then((data) => {
        setSettings(data)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [setError, setLoading, setSettings, settings])

  const saveSettings = async (payload: SettingsUpdatePayload) => {
    setIsSaving(true)
    try {
      const data = await updateSettings(payload)
      // 업데이트된 설정으로 상태 업데이트
      setSettings(data)
      return data
    } catch (err) {
      setError((err as Error).message)
      // 에러 발생 시 설정 다시 불러오기
      try {
        const freshData = await getSettings()
        setSettings(freshData)
      } catch {
      }
      throw err
    } finally {
      setIsSaving(false)
    }
  }

  return {
    settings,
    isLoading,
    error,
    isSaving,
    saveSettings,
  }
}

