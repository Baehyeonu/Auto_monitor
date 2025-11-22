import { NavLink } from 'react-router-dom'
import { Activity, Users, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

const links = [
  { to: '/logs', label: '실시간 로그', icon: Activity },
  { to: '/students', label: '학생 관리', icon: Users },
  { to: '/settings', label: '설정', icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="glass-panel flex h-full w-64 flex-col border border-border/60 p-4">
      <div className="flex flex-col gap-6">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
                isActive
                  ? 'bg-primary text-primary-foreground shadow'
                  : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
              )
            }
          >
            <link.icon className="h-4 w-4" />
            {link.label}
          </NavLink>
        ))}
      </div>
    </aside>
  )
}

