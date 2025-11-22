import { API_ROUTES } from '@/lib/constants'
import { apiRequest } from './api'
import type {
  SettingsResponse,
  SettingsUpdatePayload,
} from '@/types/settings'

export const getSettings = () =>
  apiRequest<SettingsResponse>(API_ROUTES.settings)

export const updateSettings = (data: SettingsUpdatePayload) =>
  apiRequest<SettingsResponse>(API_ROUTES.settings, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

