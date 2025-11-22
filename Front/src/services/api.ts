import { API_BASE_URL } from '@/lib/constants'

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

function buildUrl(path: string, params?: RequestOptions['params']) {
  const url = new URL(path, API_BASE_URL)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value))
      }
    })
  }
  return url.toString()
}

export async function apiRequest<T>(
  path: string,
  { params, headers, ...rest }: RequestOptions = {},
): Promise<T> {
  const url = buildUrl(path, params)
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    ...rest,
  })

  if (!response.ok) {
    const errorBody = await response.text()
    throw new Error(
      `API Error (${response.status}): ${errorBody || response.statusText}`,
    )
  }

  if (response.status === 204) {
    return {} as T
  }

  return response.json() as Promise<T>
}

