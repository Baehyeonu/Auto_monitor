import { useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Upload, FileText, AlertCircle } from 'lucide-react'
import { bulkCreateStudents } from '@/services/studentService'

interface BulkImportProps {
  onUpdated?: () => Promise<void> | void
}

export function BulkImport({ onUpdated }: BulkImportProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<{ created: number; failed: number; errors: string[] } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setSelectedFile(file)
        setResult(null)
      } else {
        alert('CSV 파일만 업로드 가능합니다.')
      }
    }
  }

  const handleFileClick = () => {
    fileInputRef.current?.click()
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) {
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setSelectedFile(file)
        setResult(null)
      } else {
        alert('CSV 파일만 업로드 가능합니다.')
      }
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }

  const parseCSV = (text: string): Array<{ zep_name: string; discord_id?: number }> => {
    const lines = text.split('\n').filter(line => line.trim())
    if (lines.length === 0) return []

    const header = lines[0].toLowerCase().trim()
    const hasHeader = header.includes('zep_name') || header.includes('discord_id')
    const dataLines = hasHeader ? lines.slice(1) : lines

    const students: Array<{ zep_name: string; discord_id?: number }> = []

    for (const line of dataLines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      const parts = trimmed.split(',').map(p => p.trim())
      if (parts.length < 1) continue

      const zep_name = parts[0]
      const discord_id_str = parts[1]

      if (!zep_name) continue

      const student: { zep_name: string; discord_id?: number } = { zep_name }

      if (discord_id_str) {
        const discord_id = parseInt(discord_id_str, 10)
        if (!isNaN(discord_id)) {
          student.discord_id = discord_id
        }
      }

      students.push(student)
    }

    return students
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setIsUploading(true)
    setResult(null)

    try {
      const text = await selectedFile.text()
      const students = parseCSV(text)

      if (students.length === 0) {
        alert('CSV 파일에 유효한 데이터가 없습니다.')
        setIsUploading(false)
        return
      }

      const response = await bulkCreateStudents(students)

      setResult(response)
      
      if (response.created > 0 && response.failed === 0) {
        alert(`${response.created}명의 학생이 등록되었습니다.`)
      } else if (response.failed > 0) {
        alert(`${response.created}명 등록 성공, ${response.failed}명 등록 실패`)
      }

      if (response.created > 0) {
        await onUpdated?.()
        setSelectedFile(null)
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    } catch (error) {
      alert('파일 업로드 중 오류가 발생했습니다.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>일괄 등록 (CSV)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          CSV 파일을 업로드해 여러 명의 학생을 한 번에 등록할 수 있습니다.
        </p>
        <p className="text-xs text-muted-foreground">
          형식: zep_name,discord_id (한 줄에 하나씩, 헤더는 선택사항)
        </p>
        
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div
          className="rounded-lg border border-dashed border-border/80 p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onClick={handleFileClick}
        >
          {selectedFile ? (
            <div className="space-y-2">
              <FileText className="mx-auto h-8 w-8 text-primary" />
              <p className="text-sm font-medium">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">
                {(selectedFile.size / 1024).toFixed(2)} KB
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                드래그 앤 드롭 또는 클릭하여 파일을 선택하세요
              </p>
            </div>
          )}
        </div>

        {selectedFile && (
          <div className="flex gap-2">
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              className="flex-1"
            >
              {isUploading ? '업로드 중...' : '업로드'}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setSelectedFile(null)
                setResult(null)
                if (fileInputRef.current) {
                  fileInputRef.current.value = ''
                }
              }}
              disabled={isUploading}
            >
              취소
            </Button>
          </div>
        )}

        {result && (
          <div className="rounded-lg border border-border/60 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm font-semibold">업로드 결과</p>
            </div>
            <div className="text-sm space-y-1">
              <p className="text-green-600">✅ 성공: {result.created}명</p>
              {result.failed > 0 && (
                <p className="text-red-600">❌ 실패: {result.failed}명</p>
              )}
            </div>
            {result.errors.length > 0 && (
              <div className="mt-2 max-h-32 overflow-y-auto">
                <p className="text-xs font-semibold text-muted-foreground mb-1">오류 목록:</p>
                <ul className="text-xs text-muted-foreground space-y-1">
                  {result.errors.map((error, index) => (
                    <li key={index}>• {error}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

