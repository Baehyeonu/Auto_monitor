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
  reconnectInterval = 1000,
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

  const connect = useCallback(() => {
    cleanup()
    const endpoint = url ?? WS_URL

    try {
      wsRef.current = new WebSocket(endpoint)
    } catch (error) {
      // WebSocket 생성 실패 시 재연결 시도
      reconnectAttemptsRef.current += 1
      const backoffDelay = Math.min(
        reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1),
        30000
      )
      reconnectTimeoutRef.current = window.setTimeout(connect, backoffDelay)
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

      // 재연결 시도
      reconnectAttemptsRef.current += 1
      const backoffDelay = Math.min(
        reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1),
        30000
      )
      reconnectTimeoutRef.current = window.setTimeout(connect, backoffDelay)
    }

    wsRef.current.onerror = () => {
      wsRef.current?.close()
    }
  }, [
    cleanup,
    onConnect,
    onDisconnect,
    onMessage,
    reconnectInterval,
    url,
  ])

  useEffect(() => {
    // 초기 연결 시도 (즉시)
    connect()

    // 페이지가 다시 보일 때 재연결 시도 (카운터 리셋)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        reconnectAttemptsRef.current = 0
        connect()
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

