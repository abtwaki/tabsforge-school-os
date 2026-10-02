import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get, post, chatSocketUrl } from '../api'
import { useAuth, title, roleLabel } from '../auth'
import { PageHead, Modal, Empty, Alert } from '../ui'

export default function Messages({ onRead }) {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const [convs, setConvs] = useState([])
  const [active, setActive] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [users, setUsers] = useState([])
  const [canClassBroadcast, setCanClassBroadcast] = useState(false)
  const [classes, setClasses] = useState([])
  const [showClassParents, setShowClassParents] = useState(false)
  const [showDm, setShowDm] = useState(false)
  const [showGroup, setShowGroup] = useState(false)
  const [msg, setMsg] = useState(null)
  const [wsState, setWsState] = useState('offline')
  const bottomRef = useRef(null)
  const wsRef = useRef(null)
  const activeRef = useRef(null)
  activeRef.current = active

  const convName = c => {
    if (c.is_group) return c.name || `Group ${c.id}`
    const other = (c.participants_detail || []).find(p => p.user !== user.id)
    return other?.user_name || 'Direct message'
  }

  const loadConvs = useCallback(() => {
    get('/conversations/?page_size=100')
      .then(d => setConvs(d.results || d))
      .catch(() => {})
  }, [])

  const loadMessages = useCallback(conv => {
    get(`/messages/?conversation=${conv.id}&page_size=200`)
      .then(d => {
        setMessages(d.results || d)
        post(`/conversations/${conv.id}/mark-read/`, {}).catch(() => {})
        setConvs(cs => cs.map(c => c.id === conv.id ? { ...c, my_unread: 0 } : c))
        onRead && onRead()
      })
      .catch(() => {})
  }, [onRead])

  // WebSocket for live delivery.
  useEffect(() => {
    let ws
    let retry
    const connect = () => {
      try {
        ws = new WebSocket(chatSocketUrl())
        wsRef.current = ws
        ws.onopen = () => setWsState('live')
        ws.onclose = () => {
          setWsState('offline')
          retry = setTimeout(connect, 4000)
        }
        ws.onmessage = e => {
          try {
            const data = JSON.parse(e.data)
            if (data.type === 'chat.message' || data.type === 'chat.notify') {
              const m = data.message
              if (activeRef.current && m?.conversation === activeRef.current.id) {
                setMessages(ms => (ms.some(x => x.id === m.id) ? ms : [...ms, m]))
                post(`/conversations/${activeRef.current.id}/mark-read/`, {}).catch(() => {})
              }
              loadConvs()
            }
          } catch {}
        }
      } catch {}
    }
    connect()
    return () => { clearTimeout(retry); try { ws && ws.close() } catch {} }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fallback poll while socket is offline.
  useEffect(() => {
    const t = setInterval(() => {
      if (wsState !== 'live') {
        loadConvs()
        if (activeRef.current) {
          get(`/messages/?conversation=${activeRef.current.id}&page_size=200`)
            .then(d => setMessages(d.results || d)).catch(() => {})
        }
      }
    }, 8000)
    return () => clearInterval(t)
  }, [wsState, loadConvs])

  useEffect(() => {
    loadConvs()
    // Only contacts the caller is permitted to message (role-pair enforced server-side).
    get('/conversations/contacts/')
      .then(d => {
        setUsers(d.contacts || [])
        setCanClassBroadcast(!!d.can_class_broadcast)
      })
      .catch(() => {})
    get('/classes/?page_size=200')
      .then(d => setClasses(d.results || d))
      .catch(() => {})
    if (searchParams.get('compose')) setShowDm(true)
  }, [loadConvs, user.id, searchParams])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const open = conv => {
    setActive(conv)
    setMessages([])
    loadMessages(conv)
    try { wsRef.current?.send(JSON.stringify({ action: 'join', conversation: conv.id })) } catch {}
  }

  const send = async e => {
    e.preventDefault()
    if (!draft.trim() || !active) return
    const content = draft.trim()
    setDraft('')
    try {
      const m = await post('/messages/', { conversation: active.id, content })
      setMessages(ms => (ms.some(x => x.id === m.id) ? ms : [...ms, m]))
      loadConvs()
    } catch (e2) {
      setDraft(content)
      setMsg({ kind: 'error', text: e2.message })
    }
  }

  const startDm = async userId => {
    try {
      const conv = await post('/conversations/start-dm/', { user_id: userId })
      setShowDm(false)
      loadConvs()
      open(conv)
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const createGroup = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    const name = fd.get('name')
    const members = users.filter(u => fd.get(`m_${u.id}`)).map(u => u.id)
    try {
      const conv = await post('/conversations/', { name, is_group: true })
      for (const uid of members) {
        await post(`/conversations/${conv.id}/add-member/`, { user_id: uid }).catch(() => {})
      }
      setShowGroup(false)
      loadConvs()
      open(conv)
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
  }

  return (
    <>
      <PageHead
        title="Messages"
        subtitle="Direct messages and group chats — delivered in real time."
        action={<div className="head-actions">
          <button className="secondary" onClick={() => setShowDm(true)}>＋ Direct</button>
          <button className="primary" onClick={() => setShowGroup(true)}>＋ Group chat</button>
          {canClassBroadcast && (
            <button className="secondary" onClick={() => setShowClassParents(true)}>＋ Class parents</button>
          )}
        </div>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="chat-layout">
        <aside className="chat-list">
          <div className="chat-list-head">
            <strong>Conversations</strong>
            <span className={wsState === 'live' ? 'sync-dot on' : 'sync-dot off'} title={wsState === 'live' ? 'Live' : 'Reconnecting'} />
          </div>
          {convs.map(c => (
            <button key={c.id} className={active?.id === c.id ? 'chat-item active' : 'chat-item'} onClick={() => open(c)}>
              <span className="chat-avatar">{convName(c).slice(0, 2).toUpperCase()}</span>
              <span className="chat-meta">
                <strong>{convName(c)}</strong>
                <small>{c.last_message ? c.last_message.content.slice(0, 40) : 'No messages yet'}</small>
              </span>
              {c.my_unread > 0 && <span className="nav-badge">{c.my_unread}</span>}
            </button>
          ))}
          {!convs.length && (
            <Empty title="No conversations"
              hint="Start one with “＋ New message” or click here — you can message staff, admins, and (for teachers) parents of your classes."
              onAdd={() => setShowDm(true)} />
          )}
        </aside>
        <section className="chat-window">
          {active ? (
            <>
              <header className="chat-head">
                <strong>{convName(active)}</strong>
                <small>{active.is_group ? `${active.participants_detail?.length || 0} members` : 'Direct message'}</small>
              </header>
              <div className="chat-scroll">
                {messages.map(m => (
                  <div key={m.id} className={m.sender === user.id ? 'bubble mine' : 'bubble'}>
                    <small>{m.sender_name || 'You'} · {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small>
                    <p>{m.content}</p>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
              <form className="chat-input" onSubmit={send}>
                <input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Type a message…" />
                <button className="primary" type="submit">Send</button>
              </form>
            </>
          ) : (
            <Empty title="Pick a conversation"
              hint="Choose a conversation on the left, or click here to start a new one."
              onAdd={() => setShowDm(true)} />
          )}
        </section>
      </div>

      {showDm && (
        <Modal title="New direct message" close={() => setShowDm(false)}>
          {!users.length && (
            <Alert kind="error">No one is available to message yet — users appear here once your admin adds staff or parent accounts.</Alert>
          )}
          <div className="user-pick">
            {users.map(u => (
              <button key={u.id} className="chat-item" onClick={() => startDm(u.id)}>
                <span className="chat-avatar">{(u.name || u.email).slice(0, 2).toUpperCase()}</span>
                <span className="chat-meta"><strong>{u.name || u.email}</strong><small>{roleLabel(u.role)}</small></span>
              </button>
            ))}
          </div>
        </Modal>
      )}

      {showGroup && (
        <Modal title="New group chat" close={() => setShowGroup(false)} wide>
          <form className="stack" onSubmit={createGroup}>
            <label>Group name<input name="name" required placeholder="e.g. JSS2 Teachers" /></label>
            <fieldset className="audience">
              <legend>Members</legend>
              <div className="user-pick">
                {users.map(u => (
                  <label key={u.id} className="check">
                    <input type="checkbox" name={`m_${u.id}`} /> {u.name || u.email} <small>({roleLabel(u.role)})</small>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowGroup(false)}>Cancel</button>
              <button className="primary">Create group</button>
            </div>
          </form>
        </Modal>
      )}

      {showClassParents && (
        <Modal title="Message class parents" close={() => setShowClassParents(false)}>
          <form className="stack" onSubmit={async e => {
            e.preventDefault()
            const classId = new FormData(e.target).get('class_id')
            try {
              const conv = await post('/conversations/message-class-parents/',
                classId ? { class_id: classId } : {})
              setShowClassParents(false)
              loadConvs()
              open(conv)
            } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
          }}>
            <label>Class
              <select name="class_id">
                <option value="">All my classes</option>
                {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            {!classes.length && (
              <Alert kind="error">No classes exist yet — an admin must create classes and assign them to you first (Academics → Classes &amp; Arms, then Staff → assign classes).</Alert>
            )}
            <p className="muted" style={{ fontSize: 12 }}>
              Creates a group chat with every parent/guardian account linked to
              pupils in the selected class(es). Teachers can only broadcast to
              classes assigned to them; parents need accounts linked to their
              pupils before they appear.
            </p>
            <button className="primary">Create parents group</button>
          </form>
        </Modal>
      )}
    </>
  )
}
