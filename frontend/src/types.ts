export type HistoryEntry = {
  previous_status: string | null
  new_status: string
  remarks: string
  created_at: string
}

export type Grievance = {
  id: number
  grievance_number: string
  category: string
  description: string
  image_url: string | null
  latitude: number
  longitude: number
  address: string
  severity: string
  severity_score: number
  severity_factors: string[]
  ai_analysis: Record<string, unknown>
  processing_error: string | null
  status: string
  report_count: number
  duplicate_of: number | null
  department_name?: string | null
  history?: HistoryEntry[]
  created_at: string
  updated_at: string
}

export type Dashboard = {
  total: number
  open: number
  resolved: number
  priority: number
  average_resolution_hours: number | null
  categories: [string, number][]
  severities: [string, number][]
  statuses: [string, number][]
  departments: [string, number][]
  trend: [string, number][]
}

export type Department = {
  id: number
  name: string
  jurisdiction: string
  contact_information: string
  official_source_url: string
  verification_status: string
}
