/**
 * Discord 멤버 정보
 */
export interface DiscordMember {
  // JS 숫자 정밀도 손실을 막기 위해 문자열 사용
  discord_id: string
  discord_name: string
  display_name: string
  is_student: boolean
}

/**
 * 멤버 등록 결과
 */
export interface RegistrationResult {
  created: number
  already_exists: number
  failed: number
  errors: string[]
  details: Array<{
    name: string
    status: 'created' | 'already_exists' | 'failed'
    zep_name?: string
    reason?: string
  }>
}
