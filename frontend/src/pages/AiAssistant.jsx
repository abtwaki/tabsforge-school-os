import React, { useRef, useState } from 'react'
import { post } from '../api'
import { PageHead, Alert } from '../ui'

const SUGGESTIONS = [
  'Write a mid-term report comment for a student who improved steadily in mathematics.',
  'Draft a friendly fee-reminder message to parents with outstanding balances.',
  'Give me a 40-minute lesson plan outline on photosynthesis for JSS2.',
  'List warning signs that a student may be falling behind academically.',
]

export default function AiAssistant() {
  const [prompt, setPrompt] = useState('')
  const [thread, setThread] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)

  const ask = async text => {
    const p = (text ?? prompt).trim()
    if (!p || busy) return
    setBusy(true)
    setError('')
    setPrompt('')
    setThread(t => [...t, { role: 'user', text: p }])
    try {
      const res = await post('/ai/chat/', { prompt: p })
      setThread(t => [...t, { role: 'ai', text: res.text }])
    } catch (e) {
      setError(e.message)
      setThread(t => t.slice(0, -1))
    } finally {
      setBusy(false)
      setTimeout(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight }), 50)
    }
  }

  return (
    <>
      <PageHead title="AI Assistant" subtitle="Ask the school assistant — report comments, lesson plans, fee reminders and more." />
      {error && <Alert kind="error">{error}</Alert>}
      <section className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 420 }}>
        <div ref={listRef} style={{ flex: 1, overflowY: 'auto', maxHeight: '55vh', padding: '4px 0' }}>
          {!thread.length && (
            <div className="muted" style={{ padding: 16, textAlign: 'center' }}>
              <p style={{ marginBottom: 12 }}>Try one of these:</p>
              <div style={{ display: 'grid', gap: 8, maxWidth: 560, margin: '0 auto' }}>
                {SUGGESTIONS.map(s => (
                  <button key={s} className="ghost" style={{ textAlign: 'left' }} onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}
          {thread.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role === 'user' ? 'chat-user' : 'chat-ai'}`}>
              <div className="muted" style={{ fontSize: 11, marginBottom: 2 }}>{m.role === 'user' ? 'You' : 'Assistant'}</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
            </div>
          ))}
          {busy && <div className="chat-bubble chat-ai muted">Thinking…</div>}
        </div>
        <form
          onSubmit={e => { e.preventDefault(); ask() }}
          style={{ display: 'flex', gap: 8, marginTop: 12 }}
        >
          <input
            style={{ flex: 1 }}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="Ask anything — lesson ideas, comments, reminders…"
            disabled={busy}
          />
          <button className="primary" type="submit" disabled={busy || !prompt.trim()}>Send</button>
        </form>
      </section>
    </>
  )
}
