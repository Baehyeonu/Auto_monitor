import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const schema = z.object({
  zep_name: z.string().min(2, '이름을 입력하세요.'),
  discord_id: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

interface Props {
  onSubmit: (values: { zep_name: string; discord_id?: number }) => Promise<void>
  isSubmitting: boolean
}

export function StudentForm({ onSubmit, isSubmitting }: Props) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      zep_name: '',
      discord_id: undefined,
    },
  })

  const submit = async (values: FormValues) => {
    await onSubmit({
      zep_name: values.zep_name,
      discord_id: values.discord_id ? Number(values.discord_id) : undefined,
    })
    reset()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>학생 등록</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(submit)}>
          <div className="space-y-2">
            <label className="text-sm font-medium">ZEP 이름</label>
            <Input placeholder="예: 홍길동/IH01" {...register('zep_name')} />
            {errors.zep_name && (
              <p className="text-xs text-red-400">{errors.zep_name.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Discord ID (선택)</label>
            <Input placeholder="숫자 ID" {...register('discord_id')} />
            {errors.discord_id && (
              <p className="text-xs text-red-400">{errors.discord_id.message}</p>
            )}
          </div>
          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? '등록 중...' : '학생 등록'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

