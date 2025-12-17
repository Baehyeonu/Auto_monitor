export interface StatusNotificationData {
  student_id: number
  student_name: string
  camp: string
  status_type: string
  reason?: string
  start_date?: string
  end_date?: string
  time?: string
  is_future_date?: boolean
}

export interface Notification {
  id: string
  type: 'status_notification'
  data: StatusNotificationData
  timestamp: string
  read: boolean
  createdAt: number
}
