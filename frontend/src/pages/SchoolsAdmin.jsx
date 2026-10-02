import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, post, patch } from '../api'
import { title } from '../auth'
import { PageHead, Modal, Empty, Alert, statusBadge } from '../ui'

// Modules a platform admin can grant/revoke per school. Empty list = all
// modules allowed by the school's tier.
export const MODULE_KEYS = [
  ['applications', 'Admissions'], ['students', 'Students'], ['guardians', 'Guardians'],
  ['classes', 'Classes & Arms'], ['sections', 'Sections'], ['subjects', 'Subjects'],
  ['academic-sessions', 'Sessions'], ['terms', 'Terms'], ['grades', 'Results & Grades'],
  ['report-cards', 'Report Cards'], ['grading-schemes', 'Grading Schemes'],
  ['timetable', 'Timetable'], ['assignments', 'Assignments'], ['attendance', 'Attendance'],
  ['fees', 'Finance Overview'], ['fee-categories', 'Fee Categories'],
  ['fee-structures', 'Fee Structures'], ['invoices', 'Invoices'], ['payments', 'Payments'],
  ['expenses', 'Expenses'], ['staff', 'Staff'], ['announcements', 'Announcements'],
  ['library', 'Library'], ['transport', 'Transport'], ['hostel', 'Hostel'],
  ['branding', 'Branding'], ['users-roles', 'Users & Roles'], ['csv-import', 'Data Import'],
  ['live-lessons', 'Live Lessons'],
]
const TIERS = ['Sprout', 'Roots', 'Bloom', 'Summit']

export default function SchoolsAdmin() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [msg, setMsg] = useState(null)
  const [managing, setManaging] = useState(null)
  const [modules, setModules] = useState([])
  const [tier, setTier] = useState('Sprout')
  const [adminForm, setAdminForm] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    get('/schools/?page_size=200')
      .then(d => setRows(d.results || d))
      .catch(e => setMsg({ kind: 'error', text: e.message }))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const filtered = rows.filter(r =>
    JSON.stringify(r).toLowerCase().includes(query.toLowerCase()))

  const act = async (school, action) => {
    const verb = action === 'suspend' ? 'suspend' : 'activate'
    if (action === 'suspend' && !window.confirm(`Suspend ${school.name}? All its users will be unable to sign in until reactivated.`)) return
    try {
      const res = await post(`/schools/${school.id}/${verb}/`, {})
      setRows(rows.map(r => r.id === school.id ? { ...r, status: res.status } : r))
      setMsg({ kind: 'success', text: res.detail })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const openManage = school => {
    setManaging(school)
    setModules(school.enabled_modules || [])
    setTier(school.tier)
  }

  const saveManage = async () => {
    setBusy(true)
    try {
      const res = await patch(`/schools/${managing.id}/`, {
        tier, enabled_modules: modules,
      })
      setRows(rows.map(r => r.id === managing.id ? { ...r, ...res } : r))
      setMsg({ kind: 'success', text: `${managing.name} updated.` })
      setManaging(null)
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
    finally { setBusy(false) }
  }

  const createAdmin = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    try {
      const res = await post(`/schools/${adminForm.id}/create-admin/`, {
        email: fd.get('email'), password: fd.get('password'),
        first_name: fd.get('first_name'), last_name: fd.get('last_name'),
      })
      setMsg({ kind: 'success', text: `School admin ${res.email} created for ${adminForm.name}.` })
      setAdminForm(null)
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  return (
    <>
      <PageHead title="Schools" subtitle="Manage every school on the platform." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <div className="search">⌕ <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search schools…" /></div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>School</th><th>Subdomain</th><th>Tier</th><th>Status</th><th>Students</th><th>Users</th><th /></tr>
            </thead>
            <tbody>
              {loading ? <tr><td colSpan="7">Loading schools…</td></tr>
                : filtered.length ? filtered.map(s => (
                  <tr key={s.id}>
                    <td><strong>{s.name}</strong></td>
                    <td>{s.subdomain}</td>
                    <td>{s.tier}</td>
                    <td>{statusBadge(s.status)}</td>
                    <td>{s.student_count}</td>
                    <td>{s.user_count}</td>
                    <td>
                      <div className="row-actions">
                        <button className="ghost sm" onClick={() => openManage(s)}>Modules & tier</button>
                        <button className="ghost sm" onClick={() => setAdminForm(s)}>＋ Admin</button>
                        {s.status !== 'suspended'
                          ? <button className="ghost sm danger" onClick={() => act(s, 'suspend')}>Suspend</button>
                          : <button className="ghost sm" onClick={() => act(s, 'activate')}>Activate</button>}
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="7">
                    <Empty title="No schools"
                      hint="Onboard a school first — click here or use “＋ Add school” in the top bar."
                      onAdd={() => navigate('/onboarding')} />
                  </td></tr>
                )}
            </tbody>
          </table>
        </div>
      </section>

      {managing && (
        <Modal title={`${managing.name} — modules & tier`} close={() => setManaging(null)} wide>
          <div className="stack">
            <label>Tier
              <select value={tier} onChange={e => setTier(e.target.value)}>
                {TIERS.map(t => <option key={t}>{t}</option>)}
              </select>
            </label>
            <fieldset className="audience">
              <legend>Enabled modules <small>(none selected = all allowed by tier)</small></legend>
              <div className="module-grid">
                {MODULE_KEYS.map(([key, label]) => (
                  <label key={key} className="check">
                    <input type="checkbox" checked={modules.includes(key)}
                      onChange={e => setModules(
                        e.target.checked ? [...modules, key] : modules.filter(m => m !== key)
                      )} />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setManaging(null)}>Cancel</button>
              <button className="primary" onClick={saveManage} disabled={busy}>
                {busy ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {adminForm && (
        <Modal title={`Create admin for ${adminForm.name}`} close={() => setAdminForm(null)}>
          <form className="stack" onSubmit={createAdmin}>
            <div className="form-grid">
              <label>First name<input name="first_name" required /></label>
              <label>Last name<input name="last_name" required /></label>
            </div>
            <label>Email<input name="email" type="email" required /></label>
            <label>Temporary password<input name="password" required minLength="8" /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setAdminForm(null)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Create school admin'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
