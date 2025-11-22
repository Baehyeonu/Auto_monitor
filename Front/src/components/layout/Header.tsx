import { useMemo } from 'react'
import { ConnectionStatus } from '@/components/logs/ConnectionStatus'

interface HeaderProps {
  isConnected: boolean
}

export function Header({ isConnected }: HeaderProps) {
  const today = useMemo(
    () =>
      new Intl.DateTimeFormat('ko-KR', {
        dateStyle: 'full',
        timeStyle: 'short',
      }).format(new Date()),
    [],
  )

  return (
    <header className="glass-panel flex items-center justify-between border border-border/60 px-6 py-4">
      <div>
        <p className="text-xs uppercase text-muted-foreground">ZEP Monitor</p>
        <h1 className="text-2xl font-semibold text-foreground">
          실시간 모니터링 대시보드
        </h1>
      </div>
      <div className="flex flex-col items-end gap-2 text-right text-sm text-muted-foreground">
        <ConnectionStatus isConnected={isConnected} />
        <span>{today}</span>
      </div>
    </header>
  )
}

