import { create } from 'zustand'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

interface ChatState {
  messages: ChatMessage[]
  isOpen: boolean
  isLoading: boolean
  threadId: string
  addMessage: (msg: ChatMessage) => void
  appendToLast: (content: string) => void
  setOpen: (open: boolean) => void
  setLoading: (loading: boolean) => void
  clear: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isOpen: false,
  isLoading: false,
  threadId: `thread_${Date.now()}`,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLast: (content) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
        msgs[msgs.length - 1] = {
          ...msgs[msgs.length - 1],
          content: msgs[msgs.length - 1].content + content,
        }
      }
      return { messages: msgs }
    }),
  setOpen: (open) => set({ isOpen: open }),
  setLoading: (loading) => set({ isLoading: loading }),
  clear: () => set({ messages: [], threadId: `thread_${Date.now()}` }),
}))
