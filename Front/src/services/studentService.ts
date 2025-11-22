import { API_ROUTES } from '@/lib/constants'
import { apiRequest } from './api'
import type { PaginatedResponse, Student } from '@/types/student'

export async function fetchStudents(params?: {
  page?: number
  limit?: number
  search?: string
  status?: string
  is_admin?: boolean
}) {
  return apiRequest<PaginatedResponse<Student>>(API_ROUTES.students, {
    params: {
      page: params?.page ?? 1,
      limit: params?.limit ?? 20,
      search: params?.search,
      status: params?.status,
      is_admin: params?.is_admin,
    },
  })
}

export async function createStudent(payload: {
  zep_name: string
  discord_id?: number
}) {
  return apiRequest<Student>(API_ROUTES.students, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteStudent(id: number) {
  return apiRequest<{ success: boolean; message: string }>(
    `${API_ROUTES.students}/${id}`,
    {
      method: 'DELETE',
    },
  )
}

