import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatKoreanTime(date: string | number | Date) {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date instanceof Date ? date : new Date(date)

    // 유효하지 않은 날짜 체크
    if (isNaN(dateObj.getTime())) {
      return '정보 없음'
    }

    // 서울 시간대로 변환
    const formatted = new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).format(dateObj)

    // 잘못된 시간 형식 감지 (예: 60분, 60초)
    // "오후 09:60:00" 같은 형식을 감지하고 수정
    const timeMatch = formatted.match(/(\d{2}):(\d{2}):(\d{2})/)
    if (timeMatch) {
      const minute = timeMatch[2]
      const second = timeMatch[3]
      const min = parseInt(minute)
      const sec = parseInt(second)

      // 60분 또는 60초가 있으면 재계산
      if (min >= 60 || sec >= 60) {
        // 수동으로 시간 포맷팅
        const seoulDate = new Date(dateObj.toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
        const hours = seoulDate.getHours()
        const minutes = seoulDate.getMinutes()
        const seconds = seoulDate.getSeconds()
        const period = hours >= 12 ? '오후' : '오전'
        const displayHour = hours % 12 || 12

        return `${period} ${String(displayHour).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      }
    }

    return formatted
  } catch (error) {
    return '정보 없음'
  }
}

export function formatRelativeMinutes(minutes: number) {
  if (minutes < 60) {
    return `${minutes}분`
  }
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}시간 ${mins}분`
}

