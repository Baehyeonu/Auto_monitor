import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { nanoid } from 'nanoid'
import type { Notification, StatusNotificationData } from '@/types/notification'

const STORAGE_KEY = 'zep-monitor-notifications'
const MAX_NOTIFICATIONS = 100
const READ_NOTIFICATION_RETENTION_DAYS = 7

interface NotificationState {
  notifications: Notification[]
  addNotification: (data: StatusNotificationData, timestamp: string) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  removeNotification: (id: string) => void
  clearAll: () => void
  getUnreadCount: () => number
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set, get) => ({
      notifications: [],

      addNotification: (data, timestamp) => {
        const notification: Notification = {
          id: nanoid(),
          type: 'status_notification',
          data,
          timestamp,
          read: false,
          createdAt: Date.now(),
        }

        console.log('[Store] 알림 추가됨:', notification)

        set((state) => {
          const nextNotifications = [notification, ...state.notifications]

          console.log('[Store] 전체 알림 개수:', nextNotifications.length)

          // 최대 개수 제한
          if (nextNotifications.length > MAX_NOTIFICATIONS) {
            return { notifications: nextNotifications.slice(0, MAX_NOTIFICATIONS) }
          }

          return { notifications: nextNotifications }
        })
      },

      markAsRead: (id) => {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        }))
      },

      markAllAsRead: () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        }))
      },

      removeNotification: (id) => {
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        }))
      },

      clearAll: () => {
        set({ notifications: [] })
      },

      getUnreadCount: () => {
        return get().notifications.filter((n) => !n.read).length
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => {
        const now = Date.now()
        const retentionMs = READ_NOTIFICATION_RETENTION_DAYS * 24 * 60 * 60 * 1000

        // 읽지 않은 알림 + 7일 이내 읽은 알림만 저장
        const filteredNotifications = state.notifications.filter((n) => {
          if (!n.read) return true
          return now - n.createdAt < retentionMs
        })

        return {
          notifications: filteredNotifications.slice(0, MAX_NOTIFICATIONS),
        }
      },
    }
  )
)
