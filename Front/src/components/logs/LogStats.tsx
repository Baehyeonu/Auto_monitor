import type { LogStats as LogStatsType } from '@/types/log'

interface LogStatsProps {
  stats: LogStatsType
}

export function LogStats({ stats }: LogStatsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">전체 로그</p>
        <p className="text-2xl font-semibold">{stats?.total ?? 0}</p>
      </div>
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">카메라 ON</p>
        <p className="text-2xl font-semibold text-green-500">
          {stats?.camera_on ?? 0}
        </p>
      </div>
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">카메라 OFF</p>
        <p className="text-2xl font-semibold text-yellow-500">
          {stats?.camera_off ?? 0}
        </p>
      </div>
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">입장</p>
        <p className="text-2xl font-semibold text-blue-500">
          {stats?.user_join ?? 0}
        </p>
      </div>
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">퇴장</p>
        <p className="text-2xl font-semibold text-orange-500">
          {stats?.user_leave ?? 0}
        </p>
      </div>
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">에러</p>
        <p className="text-2xl font-semibold text-red-500">
          {stats?.errors ?? 0}
        </p>
      </div>
    </div>
  )
}

