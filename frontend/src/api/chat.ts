import api from './client'

export const getAIInsight = (params: {
  municipality_id?: number | null
  region_id?: number | null
  year?: number | null
}) => api.post<{ insight: string }>('/chat/insight', params).then(r => r.data)

export async function* streamChat(message: string, threadId?: string) {
  const baseUrl = import.meta.env.VITE_API_URL || ''
  const response = await fetch(`${baseUrl}/api/v1/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
  })

  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (data === '[DONE]') return
        try {
          const parsed = JSON.parse(data)
          if (parsed.content) yield parsed.content
        } catch {
          // skip
        }
      }
    }
  }
}
