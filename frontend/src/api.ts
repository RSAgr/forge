import type { Dashboard, Department, Grievance } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  dashboard: () => request<Dashboard>('/api/dashboard'),
  grievances: (query = '') => request<Grievance[]>(`/api/grievances${query}`),
  grievance: (id: string) => request<Grievance>(`/api/grievances/${encodeURIComponent(id)}`),
  departments: () => request<Department[]>('/api/departments'),
  submit: (data: FormData) => request<Grievance>('/api/grievances', { method: 'POST', body: data }),
  status: (id: string, status: string, remarks: string, token: string) =>
    request<Grievance>(`/api/admin/grievances/${encodeURIComponent(id)}/status`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, remarks }),
    }),
  addDepartment: (data: Omit<Department, 'id'>, token: string) =>
    request<Department>('/api/admin/departments', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  login: (email: string, password: string) => {
    const data = new FormData()
    data.set('email', email)
    data.set('password', password)
    return request<{ access_token: string; role: string; name: string }>('/api/auth/login', {
      method: 'POST',
      body: data,
    })
  },
  geocode: (latitude: number, longitude: number) =>
    request<{ display_name: string }>(`/api/geospatial/reverse?latitude=${latitude}&longitude=${longitude}`),
  nearby: (latitude: number, longitude: number) =>
    request<{ elements?: unknown[] }>(`/api/geospatial/nearby?latitude=${latitude}&longitude=${longitude}`),
  weather: (latitude: number, longitude: number) =>
    request<{ current?: { rain?: number; precipitation?: number } }>(
      `/api/weather?latitude=${latitude}&longitude=${longitude}`,
    ),
}
