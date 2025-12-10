import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fetchDiscordMembers, registerDiscordMembers } from '@/services/discordService'
import type { DiscordMember, RegistrationResult } from '@/types/discord'
import { Loader2, Users, CheckCircle2, XCircle, AlertCircle, Check } from 'lucide-react'

export function DiscordSyncSettings() {
  const [members, setMembers] = useState<DiscordMember[]>([])
  const [selectedMembers, setSelectedMembers] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [result, setResult] = useState<RegistrationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFetchMembers = async () => {
    setIsLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await fetchDiscordMembers()
      setMembers(data)

      // 학생 패턴이 감지된 멤버를 자동 선택
      const studentIds = data
        .filter(m => m.is_student)
        .map(m => m.discord_id)
      setSelectedMembers(new Set(studentIds))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Discord 멤버를 가져오는 데 실패했습니다.')
      setMembers([])
      setSelectedMembers(new Set())
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggleMember = (discordId: string) => {
    const newSelected = new Set(selectedMembers)
    if (newSelected.has(discordId)) {
      newSelected.delete(discordId)
    } else {
      newSelected.add(discordId)
    }
    setSelectedMembers(newSelected)
  }

  const handleToggleAll = () => {
    if (selectedMembers.size === members.length) {
      setSelectedMembers(new Set())
    } else {
      setSelectedMembers(new Set(members.map(m => m.discord_id)))
    }
  }

  const handleRegister = async () => {
    if (selectedMembers.size === 0) {
      setError('등록할 멤버를 선택해주세요.')
      return
    }

    setIsRegistering(true)
    setError(null)
    try {
      const membersToRegister = members
        .filter(m => selectedMembers.has(m.discord_id))
        .map(m => ({
          discord_id: m.discord_id,
          display_name: m.display_name
        }))

      const data = await registerDiscordMembers(membersToRegister)
      setResult(data)

      // 등록 성공 후 목록 갱신
      if (data.created > 0) {
        await handleFetchMembers()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '멤버 등록에 실패했습니다.')
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Discord 멤버 동기화</CardTitle>
        <CardDescription>
          Discord 서버의 멤버를 가져와서 학생으로 일괄 등록합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Button
            onClick={handleFetchMembers}
            disabled={isLoading}
            className="gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                불러오는 중...
              </>
            ) : (
              <>
                <Users className="h-4 w-4" />
                Discord에서 멤버 가져오기
              </>
            )}
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded-md text-sm bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {result && (
          <div className="space-y-3">
            <div className="grid gap-2 grid-cols-3">
              <div className="rounded-lg border border-green-200 bg-green-50 dark:bg-green-900/20 p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-green-700 dark:text-green-400 mb-1">
                  <CheckCircle2 className="h-4 w-4" />
                  <span className="text-sm font-medium">신규 등록</span>
                </div>
                <div className="text-2xl font-bold text-green-900 dark:text-green-300">{result.created}</div>
              </div>
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20 p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-yellow-700 dark:text-yellow-400 mb-1">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">이미 등록됨</span>
                </div>
                <div className="text-2xl font-bold text-yellow-900 dark:text-yellow-300">{result.already_exists}</div>
              </div>
              <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-red-700 dark:text-red-400 mb-1">
                  <XCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">실패</span>
                </div>
                <div className="text-2xl font-bold text-red-900 dark:text-red-300">{result.failed}</div>
              </div>
            </div>

            {result.details.length > 0 && (
              <div className="rounded-lg border">
                <div className="px-3 py-2 bg-muted/50 border-b">
                  <h4 className="text-sm font-medium">상세 결과</h4>
                </div>
                <ScrollArea className="h-[200px]">
                  <div className="p-2 space-y-1">
                    {result.details.map((detail, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between px-2 py-1.5 text-sm rounded hover:bg-muted/50"
                      >
                        <span className="font-medium">{detail.name}</span>
                        <div className="flex items-center gap-2">
                          {detail.status === 'created' && (
                            <>
                              {detail.zep_name && (
                                <span className="text-xs text-muted-foreground">→ {detail.zep_name}</span>
                              )}
                              <Badge variant="default" className="bg-green-600">등록됨</Badge>
                            </>
                          )}
                          {detail.status === 'already_exists' && (
                            <>
                              <span className="text-xs text-muted-foreground">{detail.reason}</span>
                              <Badge variant="outline" className="border-yellow-500 text-yellow-600">중복</Badge>
                            </>
                          )}
                          {detail.status === 'failed' && (
                            <>
                              <span className="text-xs text-muted-foreground">{detail.reason}</span>
                              <Badge variant="destructive">실패</Badge>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        )}

        {members.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                총 {members.length}명 중 {selectedMembers.size}명 선택됨
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleToggleAll}
              >
                {selectedMembers.size === members.length ? '전체 해제' : '전체 선택'}
              </Button>
            </div>

            <div className="rounded-lg border">
              <ScrollArea className="h-[300px]">
                <div className="p-2 space-y-1">
                  {members.map((member) => {
                    const isSelected = selectedMembers.has(member.discord_id)
                    return (
                      <div
                        key={member.discord_id}
                        className="flex items-center gap-3 px-2 py-2 rounded hover:bg-muted/50 cursor-pointer"
                        onClick={() => handleToggleMember(member.discord_id)}
                      >
                        <div className={`flex items-center justify-center w-5 h-5 rounded border-2 transition-colors ${
                          isSelected
                            ? 'bg-primary border-primary'
                            : 'border-muted-foreground/30'
                        }`}>
                          {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm truncate">{member.display_name}</span>
                            {member.is_student && (
                              <Badge variant="outline" className="border-blue-500 text-blue-600 shrink-0">
                                학생 패턴
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground truncate">
                            @{member.discord_name}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            </div>

            <Button
              onClick={handleRegister}
              disabled={isRegistering || selectedMembers.size === 0}
              className="w-full gap-2"
            >
              {isRegistering ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  등록 중...
                </>
              ) : (
                `선택한 멤버 등록 (${selectedMembers.size}명)`
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
