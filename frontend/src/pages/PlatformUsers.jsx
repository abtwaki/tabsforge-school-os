import React, { useEffect, useState } from 'react'
import { get, post } from '../api'
import { roleLabel } from '../auth'
import { Alert, Empty, Modal, PageHead } from '../ui'

export default function PlatformUsers() {
  const [rows, setRows] = useState(null)
  const [schools, setSchools] = useState([])
  const [query, setQuery] = useState('')
  const [schoolId, setSchoolId] = useState('')
  const [role, setRole] = useState('')
  const [msg, setMsg] = useState(null)
  const [resetFor, setResetFor] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    const qs = schoolId ? `?school_id=${schoolId}&page_size=500` : '?page_size=500'
    get(`/users/${qs}`).then(d => setRows(d.results || d)).catch(e => setMsg({ kind: 'error', text: e.message }))
  }
  useEffect(() => { load() }, [schoolId])
  useEffect(() => { get('/schools/?page_size=200').then(d => setSchools(d.results || d)).catch(() => {}) }, [])

  const filtered = (rows || []).filter(u => {
    if (role && u.role !== role) return false
    const q = query.toLowerCase()
    return !q || [u.name, u.email, u.school_name].join(' ').toLowerCase().includes(q)
  })

  const act = async (u, action) => {
    try {
      const r = await post(`/users/${u.id}/${action}/`, {})
      setRows(rows.map(x => x.id === u.id ? { ...x, is_active: r.is_active } : x))
      setMsg({ kind: 'success', text: r.detail })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const resetPassword = async e => {
    e.preventDefault()
    const password = new FormData(e.target).get('password')
    setBusy(true)
    try {
      const r = await post(`/users/${resetFor.id}/set-password/`, { password })
      setMsg({ kind: 'success', text: r.detail })
      setResetFor(null)
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  return (
    <>
      <PageHead title="Users" subtitle="Every account across the platform — suspend, reactivate, or reset access." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools" style={{ flexWrap: 'wrap' }}>
          <div className="search">⌕ <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search name, email, school…" /></div>
          <select value={schoolId} onChange={e => setSchoolId(e.target.value)}>
            <option value="">All schools</option>
            {schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select value={role} onChange={e => setRole(e.target.value)}>
            <option value="">All roles</option>
            {[...new Set((rows || []).map(u => u.role))].map(r =>
              <option key={r} value={r}>{roleLabel(r)}</option>)}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Role</th><th>School</th><th>Status</th><th /></tr></thead>
            <tbody>
              {!rows ? <tr><td colSpan="5">Loading users…</td></tr>
                : filtered.length ? filtered.map(u => (
                  <tr key={u.id} className={u.is_active ? '' : 'muted-row'}>
                    <td><strong>{u.name || u.email}</strong><br /><small className="muted">{u.email}</small></td>
                    <td>{roleLabel(u.role)}</td>
                    <td>{u.school_name || '—'}</td>
                    <td>{u.is_active ? <span className="badge">Active</span> : <span className="badge" style={{ background: '#fdecec', color: '#b91c1c' }}>Suspended</span>}</td>
                    <td>
                      <div className="row-actions">
                        <button className="ghost sm" onClick={() => setResetFor(u)}>Reset password</button>
                        {u.is_active
                          ? <button className="ghost sm danger" onClick={() => act(u, 'suspend')}>Suspend</button>
                          : <button className="ghost sm" onClick={() => act(u, 'activate')}>Activate</button>}
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="5"><Empty title="No users match" hint="Adjust the filters above." /></td></tr>
                )}
            </tbody>
          </table>
        </div>
      </section>

      {resetFor && (
        <Modal title={`Reset password — ${resetFor.email}`} close={() => setResetFor(null)}>
          <form className="stack" onSubmit={resetPassword}>
            <p className="muted">Set a temporary password for this account. All their existing
              sessions will be signed out. Share the new password with them securely.</p>
            <label>New temporary password
              <input name="password" required minLength="8" autoFocus placeholder="At least 8 characters" />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setResetFor(null)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Resetting…' : 'Reset password'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
