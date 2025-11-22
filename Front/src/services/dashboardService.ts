import { API_ROUTES } from '@/lib/constants'
import { apiRequest } from './api'

export interface DashboardOverview {
  total_students: number
  camera_on: number
  camera_off: number
  left: number
  not_joined_today: number
  threshold_exceeded: number
  last_updated: string
}

export const getDashboardOverview = () =>
  apiRequest<DashboardOverview>(`${API_ROUTES.dashboard}/overview`)

