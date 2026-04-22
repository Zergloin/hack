import api from './client'

export interface ReportOut {
  id: number
  title: string
  report_type: string
  content_markdown: string
  content_html: string | null
  created_at: string
}

export const generateReport = (params: {
  report_type?: string
  region_id?: number | null
  municipality_id?: number | null
  year_from?: number | null
  year_to?: number | null
}) => api.post<ReportOut>('/reports/generate', params).then(r => r.data)

export const getReport = (id: number) =>
  api.get<ReportOut>(`/reports/${id}`).then(r => r.data)

export const exportReport = (id: number, format: 'pdf' | 'docx') =>
  api.get(`/reports/${id}/export`, {
    params: { format },
    responseType: 'blob',
  }).then(r => {
    const url = window.URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `report_${id}.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  })
