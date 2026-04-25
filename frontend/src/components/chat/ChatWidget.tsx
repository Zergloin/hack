import { useRef, useEffect, useState } from 'react'
import { Button, Input, Badge } from 'antd'
import { MessageOutlined, SendOutlined, CloseOutlined, DeleteOutlined } from '@ant-design/icons'
import { useChatStore } from '@/store/useChatStore'
import { streamChat } from '@/api/chat'

export default function ChatWidget() {
  const {
    messages,
    isOpen,
    isLoading,
    threadId,
    addMessage,
    appendToLast,
    setOpen,
    setLoading,
    clear,
  } = useChatStore()

  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isLoading) return

    setInput('')
    addMessage({ role: 'user', content: text, timestamp: Date.now() })
    addMessage({ role: 'assistant', content: '', timestamp: Date.now() })
    setLoading(true)

    try {
      for await (const chunk of streamChat(text, threadId)) {
        appendToLast(chunk)
      }
    } catch {
      appendToLast('Произошла ошибка. Попробуйте ещё раз.')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) {
    return (
      <div
        className="chat-widget-wrapper"
        style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1000 }}
      >
        <Badge count={0}>
          <Button
            type="primary"
            shape="circle"
            size="large"
            icon={<MessageOutlined />}
            onClick={() => setOpen(true)}
            style={{
              width: 56,
              height: 56,
              boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
              background: '#1a365d',
            }}
          />
        </Badge>
      </div>
    )
  }

  return (
    <div
      className="chat-widget-wrapper"
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        width: 400,
        height: 550,
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 1000,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          background: '#1a365d',
          color: '#fff',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>AI Ассистент</div>
          <div style={{ fontSize: 11, opacity: 0.8 }}>Демография России</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            onClick={clear}
            style={{ color: '#fff' }}
          />
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={() => setOpen(false)}
            style={{ color: '#fff' }}
          />
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: '#a0aec0', textAlign: 'center', marginTop: 40, fontSize: 13 }}>
            Задайте вопрос о демографии России.
            <br />
            <br />
            Примеры:
            <br />
            «Какое население было в Татарстане в 2017 году?»
            <br />
            «Как изменилось население Татарстана с 2010 по 2022 год?»
            <br />
            «Какие регионы росли быстрее всего?»
            <br />
            «Сравни Татарстан и Башкортостан по рождаемости за 2019-2022 годы»
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '80%',
                padding: '8px 14px',
                borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                background: msg.role === 'user' ? '#1a365d' : '#f7fafc',
                color: msg.role === 'user' ? '#fff' : '#1a202c',
                fontSize: 13,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
              }}
            >
              {msg.content || (isLoading && i === messages.length - 1 ? '...' : '')}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #e2e8f0' }}>
        <Input
          placeholder="Например: население Татарстана в 2017 году"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          disabled={isLoading}
          suffix={
            <Button
              type="text"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              style={{ color: '#1a365d' }}
            />
          }
        />
      </div>
    </div>
  )
}
