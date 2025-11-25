export type LogLevel = 'info' | 'warning' | 'error' | 'success'

export type LogSource = 'slack' | 'discord' | 'system' | 'monitor'

export type EventType =
  | 'camera_on'
  | 'camera_off'
  | 'user_join'
  | 'user_leave'
  | 'alert_sent'
  | 'alert_admin'
  | 'status_change'
  | 'system_start'
  | 'system_stop'
  | 'daily_reset'
  | 'error'
  | 'dashboard_update'

export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  source: LogSource
  event_type: EventType
  message: string
  student_name?: string
  student_id?: number
  details?: Record<string, unknown>
}

export interface LogFilter {
  levels: LogLevel[]
  sources: LogSource[]
  event_types: EventType[]
  search: string
  student_name?: string
}

export interface LogStats {
  total: number
  camera_on: number
  camera_off: number
  user_join: number
  user_leave: number
  alerts_sent: number
  not_joined: number
}

