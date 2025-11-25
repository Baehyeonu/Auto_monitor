import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatKoreanTime(date: string | number | Date) {
  // UTC 시간을 한국 시간(KST, UTC+9)으로 변환하여 표시
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date instanceof Date ? date : new Date(date)
    
    // ISO 문자열에 'Z'가 있거나 '+00:00'이 있으면 UTC로 간주
    // 명시적으로 한국 시간대로 변환
    return new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true, // 오전/오후 표시
    }).format(dateObj)
  } catch (error) {
    // 파싱 실패 시 원본 반환
    return String(date)
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

