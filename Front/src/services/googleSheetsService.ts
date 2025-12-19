const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface SyncResult {
  success: boolean
  processed?: number
  updated?: number
  skipped?: number
  errors?: number
  error_details?: string[]
  synced_at?: string
  error?: string
}

export async function syncGoogleSheets(): Promise<SyncResult> {
  const response = await fetch(`${API_BASE_URL}/api/v1/settings/sync-google-sheets`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '동기화에 실패했습니다.')
  }

  return response.json()
}
