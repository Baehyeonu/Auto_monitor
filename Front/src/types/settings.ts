export interface SettingsResponse {
  camera_off_threshold: number
  alert_cooldown: number
  check_interval: number
  leave_alert_threshold: number
  class_start_time: string
  class_end_time: string
  lunch_start_time: string
  lunch_end_time: string
  daily_reset_time: string | null
  discord_connected: boolean
  slack_connected: boolean
  admin_count: number
  screen_monitor_enabled?: boolean
}

export type SettingsUpdatePayload = Partial<
  Pick<
    SettingsResponse,
    | 'camera_off_threshold'
    | 'alert_cooldown'
    | 'check_interval'
    | 'leave_alert_threshold'
    | 'class_start_time'
    | 'class_end_time'
    | 'lunch_start_time'
    | 'lunch_end_time'
    | 'daily_reset_time'
  >
>

