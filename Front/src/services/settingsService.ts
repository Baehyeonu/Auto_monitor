import { API_ROUTES } from '@/lib/constants'
import { apiRequest } from './api'
import type {
  SettingsResponse,
  SettingsUpdatePayload,
  IgnoreKeywordsResponse,
  IgnoreKeywordsUpdate,
} from '@/types/settings'

export const getSettings = () =>
  apiRequest<SettingsResponse>(API_ROUTES.settings)

export const updateSettings = (data: SettingsUpdatePayload) =>
  apiRequest<SettingsResponse>(API_ROUTES.settings, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const getIgnoreKeywords = () =>
  apiRequest<IgnoreKeywordsResponse>(`${API_ROUTES.settings}/ignore-keywords`)

export const updateIgnoreKeywords = (data: IgnoreKeywordsUpdate) =>
  apiRequest<IgnoreKeywordsResponse>(`${API_ROUTES.settings}/ignore-keywords`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

