import { useCallback, useEffect } from 'react'
import { nanoid } from 'nanoid'
import { useWebSocket } from './useWebSocket'
import { useLogStore } from '@/stores/useLogStore'
import { getDashboardOverview } from '@/services/dashboardService'
import type { WebSocketMessage } from '@/types/websocket'
import type { LogEntry } from '@/types/log'

export function useRealtimeLogs() {
  const { addLog, updateStats, setConnectionState } = useLogStore()

  const loadDashboardData = useCallback(() => {
    getDashboardOverview()
      .then((data) => {
        updateStats({
          total: data.total_students,
          camera_on: data.camera_on,
          camera_off: data.camera_off,
          user_join: data.camera_on + data.camera_off,
          user_leave: data.left,
          alerts_sent: data.threshold_exceeded,
        })
      })
      .catch(() => {})
  }, [updateStats])

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'CONNECTED':
          addLog(
            createSystemLog('system_start', '실시간 연결이 설정되었습니다.'),
          )
          loadDashboardData()
          break
        case 'STUDENT_STATUS_CHANGED': {
          const payload = message.payload as {
            student_id: number
            zep_name: string
            event_type: string
            is_cam_on: boolean
            elapsed_minutes?: number
          }
          addLog(createMonitorLog(payload))
          break
        }
        case 'NEW_ALERT': {
          const payload = message.payload as {
            student_id: number
            zep_name: string
            alert_type: string
            alert_message: string
          }
          addLog(createAlertLog(payload))
          break
        }
        case 'DASHBOARD_UPDATE': {
          const payload = message.payload as {
            camera_on: number
            camera_off: number
            left: number
            threshold_exceeded: number
            total_students: number
            not_joined_today?: number
          }
          const newStats = {
            total: payload.total_students,
            camera_on: payload.camera_on,
            camera_off: payload.camera_off,
            user_join: payload.camera_on + payload.camera_off,
            user_leave: payload.left,
            alerts_sent: payload.threshold_exceeded,
            errors: 0,
          }
          updateStats(newStats)
          break
        }
        case 'LOG':
          addLog(message.payload as LogEntry)
          break
        default:
          break
      }
    },
    [addLog, updateStats, loadDashboardData],
  )

  const { isConnected } = useWebSocket({
    onMessage: handleMessage,
  })

  useEffect(() => {
    setConnectionState(isConnected)
  }, [isConnected, setConnectionState])

  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData])

  function createSystemLog(eventType: string, message: string): LogEntry {
    return {
      id: nanoid(),
      timestamp: new Date().toISOString(),
      level: 'info',
      source: 'system',
      event_type: eventType as LogEntry['event_type'],
      message,
    }
  }

  function createMonitorLog(payload: {
    student_id: number
    zep_name: string
    event_type: string
    is_cam_on: boolean
    elapsed_minutes?: number
  }): LogEntry {
    const actionMap: Record<string, string> = {
      camera_on: '카메라 켬',
      camera_off: '카메라 끔',
      user_join: '입장',
      user_leave: '퇴장',
    }
    return {
      id: nanoid(),
      timestamp: new Date().toISOString(),
      level: payload.is_cam_on ? 'success' : 'warning',
      source: 'monitor',
      event_type: payload.event_type as LogEntry['event_type'],
      message: `${payload.zep_name} - ${actionMap[payload.event_type] || '상태 변경'}`,
      student_id: payload.student_id,
      student_name: payload.zep_name,
      details: payload,
    }
  }

  function createAlertLog(payload: {
    student_id: number
    zep_name: string
    alert_type: string
    alert_message: string
  }): LogEntry {
    return {
      id: nanoid(),
      timestamp: new Date().toISOString(),
      level: payload.alert_type === 'absent_alert' ? 'warning' : 'error',
      source: 'discord',
      event_type:
        payload.alert_type === 'camera_off_admin'
          ? 'alert_admin'
          : 'alert_sent',
      message: payload.alert_message,
      student_id: payload.student_id,
      student_name: payload.zep_name,
      details: payload,
    }
  }

  return { isConnected }
}

