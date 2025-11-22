export interface Student {
  id: number
  zep_name: string
  discord_id?: number | null
  is_cam_on: boolean
  last_status_change?: string | null
  last_leave_time?: string | null
  is_absent: boolean
  absent_type?: 'leave' | 'early_leave' | null
  alert_count: number
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
}

