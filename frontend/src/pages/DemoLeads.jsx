import React, { useEffect, useState } from 'react'
import { get, post, remove } from '../api'
import { Alert, Empty, PageHead } from '../ui'

export default function DemoLeads() {
  const [rows, setRows] = useState(null)
  const [showContacted, setShowContacted] = useState(true)
  const [msg, setMsg] = useState(null)

  const load = () =>
    get('/marketing/demo-leads/')
      .then(d => setRows(d.results || []))
      .catch(e => setMsg({ kind: 'error', text: e.message }))
  useEffect(() => { load() }, [])

  const toggle = async lead => {
    try {
      const r = await post(`/marketing/demo-leads/${lead.id}/contact/`, {})
      setRows(rows.map(l => l.id === lead.id ? { ...l, contacted: r.contacted } : l))
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const del = async lead => {
    if (!window.confirm(`Remove the demo request from ${lead.school_name}?`)) return
    try {
      await remove(`/marketing/demo-leads/${lead.id}/`)
      setRows(rows.filter(l => l.id !== lead.id))
      setMsg({ kind: 'success', text: 'Lead removed.' })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const visible = (rows || []).filter(l => showContacted || !l.contacted)
  const pending = (rows || []).filter(l => !l.contacted).length

  return (
    <>
      <PageHead title="Demo leads"
        subtitle={`${pending} waiting for follow-up — schools that booked a demo from the marketing site.`} />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <label className="check-line" style={{ marginLeft: 'auto' }}>
            <input type="checkbox" checked={showContacted}
              onChange={e => setShowContacted(e.target.checked)} />
            <span>Show contacted</span>
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>School</th><th>Contact</th><th>Students</th><th>Message</th><th>Received</th><th /></tr></thead>
            <tbody>
              {!rows ? <tr><td colSpan="6">Loading leads…</td></tr>
                : visible.length ? visible.map(l => (
                  <tr key={l.id} className={l.contacted ? 'muted-row' : ''}>
                    <td><strong>{l.school_name}</strong></td>
                    <td>{l.contact_name}<br />
                      <small className="muted"><a href={`mailto:${l.email}`}>{l.email}</a> · {l.phone}</small></td>
                    <td>{l.student_count_range || '—'}</td>
                    <td style={{ whiteSpace: 'normal', maxWidth: 260 }}>{l.message || '—'}</td>
                    <td>{new Date(l.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="row-actions">
                        <button className="ghost sm" onClick={() => toggle(l)}>
                          {l.contacted ? 'Reopen' : '✓ Mark contacted'}
                        </button>
                        <button className="ghost sm danger" onClick={() => del(l)}>Remove</button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="6">
                    <Empty title="No leads to show"
                      hint={pending ? 'Enable “Show contacted” to see handled leads.' : 'Demo requests from the marketing site will appear here.'} />
                  </td></tr>
                )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
