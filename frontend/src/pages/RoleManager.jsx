import React, { useEffect, useState } from 'react'
import { get, post, patch, remove } from '../api'
import { useAuth, title, roleLabel, ROLE_LABELS } from '../auth'
import { PageHead, Modal, Empty, Alert } from '../ui'

const ASSIGNABLE_ROLES = [
  'school_admin', 'principal', 'vice_principal', 'admissions_officer',
  'teacher', 'form_teacher', 'exam_officer', 'hr_admin', 'librarian',
  'staff', 'accountant', 'parent', 'student',
]

export default function RoleManager() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [msg, setMsg] = useState(null)
  const [show, setShow] = useState(false)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)
  const [byEmail, setByEmail] = useState(false)

  const load = () => {
    setLoading(true)
    get('/users/?page_size=300')
      .then(d => setRows(d.results || d))
      .catch(e => setMsg({ kind: 'error', text: e.message }))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const filtered = rows.filter(r =>
    JSON.stringify(r).toLowerCase().includes(query.toLowerCase()))

  const invite = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    setMsg(null)
    try {
      if (byEmail) {
        const res = await post('/auth/request-registration/', {
          email: fd.get('email'),
          name: `${fd.get('first_name')} ${fd.get('last_name')}`.trim(),
          role: fd.get('role'),
          school_id: user.school || undefined,
        })
        setShow(false)
        setMsg({ kind: 'success', text: res.detail || 'Registration link sent — the user sets their own password.' })
        load()
        return
      }
      const res = await post('/users/', {
        email: fd.get('email'),
        first_name: fd.get('first_name'),
        last_name: fd.get('last_name'),
        role: fd.get('role'),
        password: fd.get('password'),
        phone: fd.get('phone') || '',
      })
      setRows([...rows, res])
      setShow(false)
      setMsg({
        kind: 'success',
        text: `User ${res.email} created as ${roleLabel(res.role)}. Share the credentials securely — they should change the password on first login.`,
      })
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const changeRole = async (row, role) => {
    try {
      const res = await patch(`/users/${row.id}/`, { role })
      setRows(rows.map(r => r.id === row.id ? { ...r, role: res.role } : r))
      setMsg({ kind: 'success', text: `${row.email} is now ${roleLabel(res.role)}.` })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const setActive = async (row, active) => {
    try {
      await post(`/users/${row.id}/${active ? 'activate' : 'suspend'}/`, {})
      setRows(rows.map(r => r.id === row.id ? { ...r, is_active: active } : r))
      setMsg({ kind: 'success', text: `${row.email} ${active ? 'reactivated' : 'suspended — they can no longer sign in'}.` })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const saveEdit = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    try {
      const res = await patch(`/users/${editing.id}/`, {
        first_name: fd.get('first_name'),
        last_name: fd.get('last_name'),
        phone: fd.get('phone') || '',
      })
      setRows(rows.map(r => r.id === editing.id ? { ...r, ...res } : r))
      setEditing(null)
      setMsg({ kind: 'success', text: `${res.email} updated.` })
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const deleteUser = async row => {
    if (!window.confirm(`Permanently delete ${row.email}? This cannot be undone — prefer Suspend for temporary blocks.`)) return
    try {
      await remove(`/users/${row.id}/`)
      setRows(rows.filter(r => r.id !== row.id))
      setMsg({ kind: 'success', text: `${row.email} deleted.` })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  return (
    <>
      <PageHead
        title="Users & roles"
        subtitle="Control access to your school workspace."
        action={<button className="primary" onClick={() => setShow(true)}>＋ Invite user</button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <div className="search">⌕ <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search users…" /></div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan="5">Loading users…</td></tr>
                : filtered.length ? filtered.map(r => (
                  <tr key={r.id} className={r.is_active ? '' : 'muted-row'}>
                    <td><strong>{r.name || `${r.first_name} ${r.last_name}`}</strong></td>
                    <td>{r.email}</td>
                    <td>
                      <select
                        value={r.role}
                        disabled={r.id === user.id}
                        title={r.id === user.id ? 'You can’t change your own role — ask another admin' : 'Change this user’s role'}
                        onChange={e => changeRole(r, e.target.value)}>
                        {[r.role, ...ASSIGNABLE_ROLES.filter(x => x !== r.role)].map(x => (
                          <option key={x} value={x}>{roleLabel(x)}</option>
                        ))}
                        {['super_admin', 'group_owner', 'guest'].includes(r.role) && (
                          <option value={r.role} disabled>{roleLabel(r.role)}</option>
                        )}
                      </select>
                    </td>
                    <td><span className={r.is_active ? 'badge ok' : 'badge warn'}>{r.is_active ? 'Active' : 'Suspended'}</span></td>
                    <td>
                      <div className="row-actions">
                        <button className="ghost sm" onClick={() => setEditing(r)}>Edit</button>
                        {r.id !== user.id && (
                          <>
                            <button className="ghost sm" onClick={() => setActive(r, !r.is_active)}>
                              {r.is_active ? 'Suspend' : 'Activate'}
                            </button>
                            <button className="ghost sm danger" onClick={() => deleteUser(r)}>Delete</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="5">
                    <Empty title="No users"
                      hint="Create staff and parent accounts with “＋ New account” or click here."
                      onAdd={() => setShow(true)} />
                  </td></tr>
                )}
            </tbody>
          </table>
        </div>
      </section>

      {show && (
        <Modal title="Invite user" close={() => setShow(false)}>
          <form className="stack" onSubmit={invite}>
            <div className="form-grid">
              <label>First name<input name="first_name" required /></label>
              <label>Last name<input name="last_name" required /></label>
            </div>
            <label>Email<input name="email" type="email" required /></label>
            <label>Role
              <select name="role" required>
                {ASSIGNABLE_ROLES.map(r => <option key={r} value={r}>{roleLabel(r)}</option>)}
              </select>
            </label>
            <label className="check-line">
              <input type="checkbox" checked={byEmail} onChange={e => setByEmail(e.target.checked)} />
              <span>Email a secure invite link — the user sets their own password</span>
            </label>
            {!byEmail && (
              <>
                <label>Temporary password<input name="password" type="text" required={!byEmail} minLength="8" placeholder="Min. 8 characters" /></label>
                <label>Phone (optional)<input name="phone" /></label>
              </>
            )}
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShow(false)}>Cancel</button>
              <button className="primary" disabled={busy}>
                {busy ? (byEmail ? 'Sending…' : 'Creating…') : (byEmail ? 'Send invite link' : 'Create account')}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit ${editing.email}`} close={() => setEditing(null)}>
          <form className="stack" onSubmit={saveEdit}>
            <div className="form-grid">
              <label>First name<input name="first_name" defaultValue={editing.first_name} required /></label>
              <label>Last name<input name="last_name" defaultValue={editing.last_name} required /></label>
            </div>
            <label>Phone<input name="phone" defaultValue={editing.phone || ''} /></label>
            <p className="muted" style={{ fontSize: 12 }}>Email and school cannot be changed here — role is managed from the table.</p>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
