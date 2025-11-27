import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Plus, X, Loader2 } from 'lucide-react'
import { getIgnoreKeywords, updateIgnoreKeywords } from '@/services/settingsService'

export function IgnoreKeywordsSettings() {
  const [keywords, setKeywords] = useState<string[]>([])
  const [newKeyword, setNewKeyword] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    loadKeywords()
  }, [])

  const loadKeywords = async () => {
    setIsLoading(true)
    try {
      const data = await getIgnoreKeywords()
      setKeywords(data.keywords || [])
    } catch (error) {
      setMessage({ type: 'error', text: '키워드 목록을 불러오는데 실패했습니다.' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddKeyword = () => {
    const trimmed = newKeyword.trim().toLowerCase()
    if (!trimmed) {
      return
    }
    if (keywords.includes(trimmed)) {
      setMessage({ type: 'error', text: '이미 등록된 키워드입니다.' })
      return
    }
    setKeywords([...keywords, trimmed])
    setNewKeyword('')
  }

  const handleRemoveKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter((kw) => kw !== keywordToRemove))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setMessage(null)
    try {
      await updateIgnoreKeywords({ keywords })
      setMessage({ type: 'success', text: '키워드 목록이 저장되었습니다.' })
    } catch (error) {
      setMessage({ type: 'error', text: '키워드 목록 저장에 실패했습니다.' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleAddKeyword()
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>무시할 키워드 관리</CardTitle>
          <CardDescription>특정 키워드가 포함된 이름은 자동으로 무시됩니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>무시할 키워드 관리</CardTitle>
        <CardDescription>
          특정 키워드가 포함된 이름은 자동으로 무시됩니다.
          <br />
          예: "현우_조교_test", "현우_조교(monitor)" 등
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="키워드 입력 (예: test, monitor)"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isSaving}
          />
          <Button onClick={handleAddKeyword} disabled={isSaving || !newKeyword.trim()}>
            <Plus className="h-4 w-4 mr-2" />
            추가
          </Button>
        </div>

        {keywords.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">등록된 키워드 ({keywords.length}개)</p>
            <div className="flex flex-wrap gap-2">
              {keywords.map((keyword) => (
                <Badge key={keyword} variant="outline" className="px-3 py-1">
                  {keyword}
                  <button
                    onClick={() => handleRemoveKeyword(keyword)}
                    className="ml-2 hover:text-destructive"
                    disabled={isSaving}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        )}

        {keywords.length === 0 && (
          <p className="text-sm text-muted-foreground">등록된 키워드가 없습니다.</p>
        )}

        {message && (
          <div
            className={`p-3 rounded-md text-sm ${
              message.type === 'success'
                ? 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                : 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                저장 중...
              </>
            ) : (
              '저장'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

