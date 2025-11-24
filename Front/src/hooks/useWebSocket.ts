import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_URL } from '@/lib/constants'
import type { WebSocketMessage } from '@/types/websocket'

interface UseWebSocketOptions {
  url?: string
  onMessage?: (data: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket({
  url = WS_URL,
  onMessage,
  onConnect,
  onDisconnect,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
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

  const connect = useCallback(() => {
    cleanup()
    const endpoint = url ?? WS_URL
    console.log(`[WebSocket] 연결 시도: ${endpoint}`)
    
    try {
      wsRef.current = new WebSocket(endpoint)
    } catch (error) {
      console.error('[WebSocket] 연결 생성 실패:', error)
      return
    }

    wsRef.current.onopen = () => {
      console.log(`[WebSocket] 연결 성공: ${endpoint}`)
      setIsConnected(true)
      reconnectAttemptsRef.current = 0
      onConnect?.()
      send({
        type: 'SUBSCRIBE_DASHBOARD',
        payload: {},
        timestamp: new Date().toISOString(),
      })
    }

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage
        setLastMessage(data)
        onMessage?.(data)
      } catch (error) {
        console.error('[WebSocket] 메시지 파싱 실패:', error)
      }
    }

    wsRef.current.onclose = (event) => {
      console.log(`[WebSocket] 연결 종료: code=${event.code}, reason=${event.reason || 'none'}`)
      setIsConnected(false)
      onDisconnect?.()
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1
        console.log(`[WebSocket] 재연결 시도 ${reconnectAttemptsRef.current}/${maxReconnectAttempts}...`)
        reconnectTimeoutRef.current = window.setTimeout(
          connect,
          reconnectInterval,
        )
      } else {
        console.error(`[WebSocket] 최대 재연결 시도 횟수(${maxReconnectAttempts}) 초과`)
      }
    }

    wsRef.current.onerror = (error) => {
      console.error('[WebSocket] 연결 오류:', error)
      console.error(`[WebSocket] 엔드포인트: ${endpoint}`)
      wsRef.current?.close()
    }
  }, [
    cleanup,
    maxReconnectAttempts,
    onConnect,
    onDisconnect,
    onMessage,
    reconnectInterval,
    url,
  ])

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      cleanup()
    }
  }, [cleanup, connect])

  return {
    isConnected,
    lastMessage,
    send,
    reconnect: connect,
  }
}

