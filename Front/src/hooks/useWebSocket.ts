import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL } from '@/lib/constants'
import type { WebSocketMessage } from '@/types/websocket'

interface UseWebSocketOptions {
  url?: string
  onMessage?: (data: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
}

export function useWebSocket({
  url = WS_URL,
  onMessage,
  onConnect,
  onDisconnect,
  reconnectInterval = 3000,
}: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<number | undefined>(undefined)

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current)
    }
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const checkHealthAndConnect = useCallback(async () => {
    // 백엔드 health check 후 연결 시도
    try {
      const healthUrl = (url ?? WS_URL).replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '/health')
      const response = await fetch(healthUrl, { method: 'GET' })

      if (response.ok) {
        // 백엔드 준비 완료, WebSocket 연결 시도
        connect()
      } else {
        // 아직 준비 안 됨, 재시도
        scheduleReconnect()
      }
    } catch (error) {
      // Health check 실패, 재시도
      scheduleReconnect()
    }
  }, [url])

  const scheduleReconnect = useCallback(() => {
    reconnectAttemptsRef.current += 1
    const backoffDelay = Math.min(
      reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1),
      30000
    )
    reconnectTimeoutRef.current = window.setTimeout(checkHealthAndConnect, backoffDelay)
  }, [reconnectInterval, checkHealthAndConnect])

  const connect = useCallback(() => {
    cleanup()
    const endpoint = url ?? WS_URL

    try {
      wsRef.current = new WebSocket(endpoint)
    } catch (error) {
      // WebSocket 생성 실패 시 재연결 시도
      scheduleReconnect()
      return
    }

    wsRef.current.onopen = () => {
      setIsConnected(true)
      reconnectAttemptsRef.current = 0
      onConnect?.()
      // WebSocket이 열린 직후 구독 메시지 전송
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'SUBSCRIBE_DASHBOARD',
          payload: {},
          timestamp: new Date().toISOString(),
        }))
      }
    }

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage
        setLastMessage(data)
        onMessage?.(data)
      } catch (error) {
      }
    }

    wsRef.current.onclose = () => {
      setIsConnected(false)
      onDisconnect?.()

      // health check 후 재연결 시도
      scheduleReconnect()
    }

    wsRef.current.onerror = () => {
      wsRef.current?.close()
    }
  }, [
    cleanup,
    onConnect,
    onDisconnect,
    onMessage,
    scheduleReconnect,
    url,
  ])

  useEffect(() => {
    // 초기 연결 시도 (health check 사용)
    checkHealthAndConnect()

    // 페이지가 다시 보일 때 재연결 시도 (카운터 리셋)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        reconnectAttemptsRef.current = 0
        checkHealthAndConnect()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      cleanup()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    isConnected,
    lastMessage,
    send,
    reconnect: connect,
  }
}

