import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function BulkImport() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>일괄 등록 (CSV)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          CSV 파일을 업로드해 여러 명의 학생을 한 번에 등록할 수 있습니다.
          (zep_name, discord_id 컬럼 필요)
        </p>
        <div className="rounded-lg border border-dashed border-border/80 p-6 text-center">
          <p className="text-sm text-muted-foreground">
            드래그 앤 드롭 또는 버튼을 눌러 파일을 선택하세요.
          </p>
          <Button className="mt-3">파일 선택</Button>
        </div>
      </CardContent>
    </Card>
  )
}

