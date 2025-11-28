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
  discord_id?: string
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

export async function updateAdminStatus(id: number, isAdmin: boolean) {
  return apiRequest(
    `${API_ROUTES.students}/${id}/admin`,
    {
      method: 'POST',
      body: JSON.stringify({ is_admin: isAdmin }),
    },
  )
}

export async function bulkCreateStudents(
  students: Array<{ zep_name: string; discord_id?: string }>
) {
  return apiRequest<{ created: number; failed: number; errors: string[] }>(
    `${API_ROUTES.students}/bulk`,
    {
      method: 'POST',
      body: JSON.stringify(students),
    },
  )
}

export async function deleteAllStudents() {
  return apiRequest<{ success: boolean; deleted: number; failed: number; message: string }>(
    `${API_ROUTES.students}/bulk/all`,
    {
      method: 'DELETE',
    },
  )
}

export async function updateStudentStatus(
  id: number,
  statusType: 'late' | 'leave' | 'early_leave' | 'vacation' | 'absence' | null
) {
  return apiRequest<Student>(`${API_ROUTES.students}/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status_type: statusType }),
  })
}

