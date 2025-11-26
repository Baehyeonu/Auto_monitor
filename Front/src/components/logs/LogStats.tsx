import { useState } from 'react'
import type { LogStats as LogStatsType } from '@/types/log'
import { StudentStatusModal } from './StudentStatusModal'

interface LogStatsProps {
  stats: LogStatsType
}

export function LogStats({ stats }: LogStatsProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null)
  const [selectedStatusLabel, setSelectedStatusLabel] = useState('')

  const handleCardClick = (status: string | null, label: string) => {
    setSelectedStatus(status)
    setSelectedStatusLabel(label)
    setModalOpen(true)
  }

  return (
    <>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
      <div className="glass-panel rounded-lg border border-border/60 p-4">
        <p className="text-sm text-muted-foreground">전체 로그</p>
        <p className="text-2xl font-semibold">{stats?.total ?? 0}</p>
      </div>
        <div 
          className="glass-panel rounded-lg border border-border/60 p-4 cursor-pointer hover:bg-muted/20 transition-colors"
          onClick={() => handleCardClick('camera_on', '카메라 ON')}
          title="카메라 ON 학생 목록 보기"
        >
        <p className="text-sm text-muted-foreground">카메라 ON</p>
        <p className="text-2xl font-semibold text-green-500">
          {stats?.camera_on ?? 0}
        </p>
      </div>
        <div 
          className="glass-panel rounded-lg border border-border/60 p-4 cursor-pointer hover:bg-muted/20 transition-colors"
          onClick={() => handleCardClick('camera_off', '카메라 OFF')}
          title="카메라 OFF 학생 목록 보기"
        >
        <p className="text-sm text-muted-foreground">카메라 OFF</p>
        <p className="text-2xl font-semibold text-yellow-500">
          {stats?.camera_off ?? 0}
        </p>
      </div>
        <div 
          className="glass-panel rounded-lg border border-border/60 p-4 cursor-pointer hover:bg-muted/20 transition-colors"
          onClick={() => handleCardClick(null, '입장')}
          title="입장한 학생 목록 보기 (카메라 ON + OFF)"
        >
        <p className="text-sm text-muted-foreground">입장</p>
        <p className="text-2xl font-semibold text-blue-500">
          {stats?.user_join ?? 0}
        </p>
      </div>
        <div 
          className="glass-panel rounded-lg border border-border/60 p-4 cursor-pointer hover:bg-muted/20 transition-colors"
          onClick={() => handleCardClick('left', '퇴장')}
          title="퇴장한 학생 목록 보기"
        >
        <p className="text-sm text-muted-foreground">퇴장</p>
        <p className="text-2xl font-semibold text-orange-500">
          {stats?.user_leave ?? 0}
        </p>
      </div>
        <div 
          className="glass-panel rounded-lg border border-border/60 p-4 cursor-pointer hover:bg-muted/20 transition-colors"
          onClick={() => handleCardClick('not_joined', '미접속')}
          title="미접속 학생 목록 보기"
        >
        <p className="text-sm text-muted-foreground">미접속</p>
        <p className="text-2xl font-semibold text-gray-500">
          {stats?.not_joined ?? 0}
        </p>
      </div>
    </div>
      <StudentStatusModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        status={selectedStatus}
        statusLabel={selectedStatusLabel}
      />
    </>
  )
}

