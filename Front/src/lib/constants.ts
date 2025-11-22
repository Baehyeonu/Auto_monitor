// API URL 설정 (빌드 시 환경변수 또는 상대 경로)
const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  if (envUrl) return envUrl
  // 프로덕션에서는 상대 경로 사용 (같은 서버에서 서빙)
  if (import.meta.env.PROD) return ''
  // 개발 모드에서는 localhost 사용
  return 'http://localhost:8000'
}

const getWsUrl = () => {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) return envUrl
  // 프로덕션에서는 상대 경로 사용
  if (import.meta.env.PROD) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws`
  }
  // 개발 모드에서는 localhost 사용
  return 'ws://localhost:8000/ws'
}

export const API_BASE_URL = getApiBaseUrl()
export const WS_URL = getWsUrl()

export const API_ROUTES = {
  students: `${API_BASE_URL}/api/v1/students`,
  dashboard: `${API_BASE_URL}/api/v1/dashboard`,
  settings: `${API_BASE_URL}/api/v1/settings`,
} as const

