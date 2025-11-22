import { create } from 'zustand'
import type { SettingsResponse } from '@/types/settings'

interface SettingsState {
  settings: SettingsResponse | null
  isLoading: boolean
  error?: string
  setSettings: (data: SettingsResponse) => void
  setLoading: (loading: boolean) => void
  setError: (message?: string) => void
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  isLoading: false,
  error: undefined,
  setSettings: (data) => set({ settings: data }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))

