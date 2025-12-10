import { apiRequest } from './api'
import type { DiscordMember, RegistrationResult } from '@/types/discord'

/**
 * Discord 서버의 모든 멤버 가져오기
 */
export async function fetchDiscordMembers(): Promise<DiscordMember[]> {
  return apiRequest<DiscordMember[]>('/api/v1/discord/members')
}

/**
 * 선택한 Discord 멤버들을 학생으로 일괄 등록
 */
export async function registerDiscordMembers(
  members: Array<{ discord_id: string; display_name: string }>
): Promise<RegistrationResult> {
  return apiRequest<RegistrationResult>('/api/v1/discord/members/register', {
    method: 'POST',
    body: JSON.stringify({ members }),
  })
}
