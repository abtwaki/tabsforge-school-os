import React, { useEffect, useState } from 'react'
import { get, post, patch, remove } from '../api'
import { useAuth, title, roleLabel } from '../auth'
import { PageHead, Modal, Empty, Alert, fmtDate, statusBadge } from '../ui'

const WRITERS = new Set([
  'super_admin', 'school_admin', 'principal', 'vice_principal',
  'teacher', 'form_teacher', 'exam_officer', 'hr_admin',
  'admissions_officer', 'librarian', 'staff',
])
const AUDIENCES = [
  ['everyone', 'Everyone'], ['staff', 'All staff'], ['teacher', 'Teachers'],
  ['parent', 'Parents'], ['student', 'Students'], ['accountant', 'Accountants'],
]

export default function Announcements() {
  const { user } = useAuth()
  const canWrite = WRITERS.has(user.role) && !user.is_guest
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState(null)
  const [show, setShow] = useState(false)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState('')

  const load = () => {
    setLoading(true)
    get(`/announcements/?page_size=100${filter ? `&status=${filter}` : ''}`)
      .then(d => setRows(d.results || d))
      .catch(e => setMsg({ kind: 'error', text: e.message }))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [filter])

  const save = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    const targets = AUDIENCES.map(([v]) => v).filter(v => fd.get(`aud_${v}`))
    const body = {
      title: fd.get('title'),
      content: fd.get('content'),
      target_roles: targets.includes('everyone') || !targets.length ? [] : targets,
      status: fd.get('publish') ? 'published' : 'draft',
      publish_at: fd.get('publish') ? new Date().toISOString() : null,
    }
    setBusy(true)
    try {
      if (editing) {
        await patch(`/announcements/${editing.id}/`, body)
      } else {
        await post('/announcements/', body)
      }
      setShow(false)
      setEditing(null)
      setMsg({ kind: 'success', text: body.status === 'published' ? 'Announcement published.' : 'Draft saved.' })
      load()
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const setStatus = async (row, status) => {
    try {
      await patch(`/announcements/${row.id}/`, {
        status,
        ...(status === 'published' ? { publish_at: new Date().toISOString() } : {}),
      })
      setRows(rows.map(r => r.id === row.id ? { ...r, status } : r))
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const del = async row => {
    if (!window.confirm(`Delete announcement “${row.title}”?`)) return
    try {
      await remove(`/announcements/${row.id}/`)
      setRows(rows.filter(r => r.id !== row.id))
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const audienceText = row =>
    !row.target_roles?.length ? 'Everyone' : row.target_roles.map(roleLabel).join(', ')

  return (
    <>
      <PageHead
        title="Announcements"
        subtitle="Share news and notices with your school community."
        action={canWrite && <button className="primary" onClick={() => { setEditing(null); setShow(true) }}>＋ New announcement</button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="table-tools" style={{ marginBottom: '1rem' }}>
        <select value={filter} onChange={e => setFilter(e.target.value)} style={{ maxWidth: '180px' }}>
          <option value="">All statuses</option>
          <option value="published">Published</option>
          <option value="draft">Drafts</option>
          <option value="archived">Archived</option>
        </select>
      </div>
      {loading ? <div className="loading">Loading announcements…</div> : (
        <div className="notice-grid">
          {rows.map(n => (
            <article className="notice" key={n.id}>
              <span className={`notice-pin st-${n.status}`}>{title(n.status)}</span>
              <h3>{n.title}</h3>
              <p>{n.content}</p>
              <footer>
                <span>{audienceText(n)}</span>
                <small>{n.author_name || '—'} · {fmtDate(n.publish_at || n.created_at)}</small>
              </footer>
              {canWrite && (
                <div className="row-actions">
                  {n.status !== 'published' && <button className="secondary" onClick={() => setStatus(n, 'published')}>Publish</button>}
                  {n.status === 'published' && <button className="secondary" onClick={() => setStatus(n, 'archived')}>Archive</button>}
                  <button className="secondary" onClick={() => { setEditing(n); setShow(true) }}>Edit</button>
                  <button className="secondary" onClick={() => del(n)}>Delete</button>
                </div>
              )}
            </article>
          ))}
          {!rows.length && (
            <Empty title="No announcements"
              hint={canWrite ? 'Create one with “＋ New announcement” or click here — drafts stay hidden until you publish.' : 'Announcements from the school will appear here.'}
              onAdd={canWrite ? () => { setEditing(null); setShow(true) } : undefined} />
          )}
        </div>
      )}

      {show && (
        <Modal title={editing ? 'Edit announcement' : 'New announcement'} close={() => { setShow(false); setEditing(null) }} wide>
          <form className="stack" onSubmit={save}>
            <label>Title<input name="title" required defaultValue={editing?.title || ''} /></label>
            <fieldset className="audience">
              <legend>Audience</legend>
              {AUDIENCES.map(([v, l]) => (
                <label key={v} className="check">
                  <input type="checkbox" name={`aud_${v}`}
                    defaultChecked={editing ? (!editing.target_roles?.length ? v === 'everyone' : editing.target_roles.includes(v)) : v === 'everyone'} />
                  {l}
                </label>
              ))}
            </fieldset>
            <label>Message<textarea name="content" rows="7" required defaultValue={editing?.content || ''} /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => { setShow(false); setEditing(null) }}>Cancel</button>
              <button className="secondary" name="publish" value="" disabled={busy}>Save draft</button>
              <button className="primary" name="publish" value="1" disabled={busy}>{busy ? 'Publishing…' : 'Publish'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
