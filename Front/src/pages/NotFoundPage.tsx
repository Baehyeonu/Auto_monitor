import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="glass-panel flex flex-col items-center gap-4 py-16 text-center">
      <h2 className="text-3xl font-semibold">404</h2>
      <p className="text-muted-foreground">페이지를 찾을 수 없습니다.</p>
      <Link to="/logs" className="text-primary underline">
        대시보드로 돌아가기
      </Link>
    </div>
  )
}

