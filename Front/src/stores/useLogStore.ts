import { create } from 'zustand'
import { nanoid } from 'nanoid'
import type { LogEntry, LogFilter, LogStats } from '@/types/log'

interface LogState {
  logs: LogEntry[]
  filter: LogFilter
  stats: LogStats
  isConnected: boolean
  maxLogs: number
  addLog: (log: Omit<LogEntry, 'id'> & { id?: string }) => void
  clearLogs: () => void
  setFilter: (filter: LogFilter) => void
  updateStats: (stats: Partial<LogStats>) => void
  setConnectionState: (connected: boolean) => void
}

const initialStats: LogStats = {
  total: 0,
  camera_on: 0,
  camera_off: 0,
  user_join: 0,
  user_leave: 0,
  alerts_sent: 0,
  errors: 0,
}

export const useLogStore = create<LogState>((set) => ({
  logs: [],
  filter: {
    levels: [],
    sources: [],
    event_types: [],
    search: '',
  },
  stats: initialStats,
  isConnected: false,
  maxLogs: 1000,
  addLog: (log) =>
    set((state) => {
      const entry: LogEntry = {
        id: log.id ?? nanoid(),
        ...log,
      }
      const nextLogs = [...state.logs, entry]
      if (nextLogs.length > state.maxLogs) {
        nextLogs.splice(0, nextLogs.length - state.maxLogs)
      }
      return { logs: nextLogs }
    }),
  clearLogs: () => set({ logs: [] }),
  setFilter: (filter) => set({ filter }),
  updateStats: (stats) =>
    set((state) => {
      const newStats = { ...state.stats, ...stats }
      return { stats: newStats }
    }),
  setConnectionState: (connected) => set({ isConnected: connected }),
}))

