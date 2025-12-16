import { useSettings } from '@/hooks/useSettings'
import { MonitoringSettings } from '@/components/settings/MonitoringSettings'
import { DiscordSettings } from '@/components/settings/DiscordSettings'
import { DiscordSyncSettings } from '@/components/settings/DiscordSyncSettings'
import { SlackSettings } from '@/components/settings/SlackSettings'
import { ScheduleSettings } from '@/components/settings/ScheduleSettings'
import { ScreenMonitorSettings } from '@/components/settings/ScreenMonitorSettings'
import { DatabaseSettings } from '@/components/settings/DatabaseSettings'
import { ResetSettings } from '@/components/settings/ResetSettings'
import { IgnoreKeywordsSettings } from '@/components/settings/IgnoreKeywordsSettings'
import { StatusParsingSettings } from '@/components/settings/StatusParsingSettings'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'

export default function SettingsPage() {
  const { settings, isLoading, isSaving, error, saveSettings } = useSettings()
  const handleSave = async (payload: Parameters<typeof saveSettings>[0]) => {
    await saveSettings(payload)
  }

  if (isLoading || !settings) {
    return <LoadingSpinner label="설정을 불러오는 중입니다..." />
  }

  if (error) {
    return (
      <EmptyState
        title="설정을 불러오지 못했습니다."
        description={error}
        action={
          <button onClick={() => window.location.reload()} className="text-primary underline">
            다시 시도
          </button>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      <MonitoringSettings settings={settings} isSaving={isSaving} onSave={handleSave} />
      <div className="grid gap-4 md:grid-cols-2">
        <DiscordSettings settings={settings} />
        <SlackSettings settings={settings} />
        <ScheduleSettings settings={settings} isSaving={isSaving} onSave={handleSave} />
        <ScreenMonitorSettings settings={settings} isSaving={isSaving} onSave={handleSave} />
        <ResetSettings settings={settings} />
        <DatabaseSettings />
        <IgnoreKeywordsSettings />
        <StatusParsingSettings />
      </div>
      <DiscordSyncSettings />
    </div>
  )
}

