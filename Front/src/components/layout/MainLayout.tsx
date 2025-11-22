import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

interface Props {
  isConnected: boolean
}

export function MainLayout({ isConnected }: Props) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4 text-foreground">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <Header isConnected={isConnected} />
        <div className="flex gap-4">
          <Sidebar />
          <main className="flex-1">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}

