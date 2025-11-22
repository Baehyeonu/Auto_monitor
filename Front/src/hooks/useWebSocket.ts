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
    try {
      wsRef.current = new WebSocket(endpoint)
    } catch (error) {
      console.error('WebSocket connection error', error)
      return
    }

    wsRef.current.onopen = () => {
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
        console.error('Failed to parse WebSocket message', error)
      }
    }

    wsRef.current.onclose = () => {
      setIsConnected(false)
      onDisconnect?.()
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1
        reconnectTimeoutRef.current = window.setTimeout(
          connect,
          reconnectInterval,
        )
      }
    }

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error', error)
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

