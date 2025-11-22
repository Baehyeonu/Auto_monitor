export interface WebSocketMessage<T = unknown> {
  type: string
  payload: T
  timestamp: string
}

export type ServerMessageType =
  | 'CONNECTED'
  | 'STUDENT_STATUS_CHANGED'
  | 'NEW_ALERT'
  | 'DASHBOARD_UPDATE'
  | 'PONG'
  | 'LOG'

export type ClientMessageType =
  | 'SUBSCRIBE_DASHBOARD'
  | 'SUBSCRIBE_LOGS'
  | 'PING'
  | 'UNSUBSCRIBE_DASHBOARD'

