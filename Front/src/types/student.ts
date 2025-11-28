export interface Student {
  id: number
  zep_name: string
  discord_id?: string | null  // 문자열로 변경 (JavaScript Number 정밀도 손실 방지)
  is_admin: boolean
  is_cam_on: boolean
  last_status_change?: string | null
  last_leave_time?: string | null
  is_absent: boolean
  absent_type?: 'leave' | 'early_leave' | null
  status_type?: 'late' | 'leave' | 'early_leave' | 'vacation' | 'absence' | null
  status_set_at?: string | null
  alarm_blocked_until?: string | null
  status_auto_reset_date?: string | null
  alert_count: number
  not_joined?: boolean
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
}

