import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { nanoid } from 'nanoid'
import type { LogEntry, LogFilter, LogStats } from '@/types/log'

const STORAGE_KEY = 'zep-monitor-logs'
const MAX_STORED_LOGS = 500

interface LogState {
  logs: LogEntry[]
  filter: LogFilter
  stats: LogStats
  isConnected: boolean
  maxLogs: number
  filteredLogs: LogEntry[]
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

const filterLogs = (logs: LogEntry[], filter: LogFilter): LogEntry[] => {
  return logs.filter((log) => {
    if (filter.levels.length > 0 && !filter.levels.includes(log.level)) {
      return false
    }
    if (filter.sources.length > 0 && !filter.sources.includes(log.source)) {
      return false
    }
    if (filter.event_types.length > 0 && !filter.event_types.includes(log.event_type)) {
      return false
    }
    if (filter.search && !log.message.toLowerCase().includes(filter.search.toLowerCase()) &&
        !log.student_name?.toLowerCase().includes(filter.search.toLowerCase())) {
      return false
    }
    return true
  })
}

export const useLogStore = create<LogState>()(
  persist(
    (set, get) => {
      const initialState = {
        logs: [] as LogEntry[],
        filter: {
          levels: [],
          sources: [],
          event_types: [],
          search: '',
        },
        stats: initialStats,
        isConnected: false,
        maxLogs: MAX_STORED_LOGS,
      }
      
      return {
        ...initialState,
        filteredLogs: filterLogs(initialState.logs, initialState.filter),
        addLog: (log) =>
          set((state) => {
            const entry: LogEntry = {
              id: log.id ?? nanoid(),
              ...log,
            }
            const nextLogs = state.logs.length >= state.maxLogs
              ? [...state.logs.slice(1), entry]
              : [...state.logs, entry]
            const filteredLogs = filterLogs(nextLogs, state.filter)
            return { logs: nextLogs, filteredLogs }
          }),
        clearLogs: () => set({ logs: [], filteredLogs: [] }),
        setFilter: (filter) => {
          const state = get()
          const filteredLogs = filterLogs(state.logs, filter)
          set({ filter, filteredLogs })
        },
        updateStats: (stats) =>
          set((state) => {
            const newStats = { ...state.stats, ...stats }
            return { stats: newStats }
          }),
        setConnectionState: (connected) => set({ isConnected: connected }),
      }
    },
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        logs: state.logs.slice(-MAX_STORED_LOGS),
        filter: state.filter,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.filteredLogs = filterLogs(state.logs, state.filter)
        }
      },
    }
  )
)

