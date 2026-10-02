import React, { useEffect, useState } from 'react'
import { get, patch, post } from '../api'
import { Alert, Empty, Modal } from '../ui'

const TIERS = ['Sprout', 'Roots', 'Bloom', 'Summit']

export default function Approvals() {
  const [rows, setRows] = useState(null)
  const [selected, setSelected] = useState(null) // detail payload
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const load = () =>
    get('/onboarding/approvals/')
      .then(d => setRows(Array.isArray(d) ? d : d.results || []))
      .catch(e => setError(e.message))

  useEffect(() => { load() }, [])

  const openDetail = row =>
    get(`/onboarding/approvals/${row.id}/`).then(setSelected).catch(e => setError(e.message))

  const act = async (pk, action, body = {}) => {
    const r = await post(`/onboarding/approvals/${pk}/${action}/`, body)
    setSelected(null)
    setMsg(r.detail || 'Done.')
    load()
  }

  if (error) return <div className="alert">{error}</div>
  if (!rows) return <div className="loading">Loading requests…</div>

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Onboarding approvals</h1>
          <p>Review, correct, approve or reject school signup requests.</p>
        </div>
      </div>
      {msg && <Alert kind="success">{msg}</Alert>}
      {rows.length === 0 ? (
        <Empty title="All caught up"
          hint="New school signups from the onboarding page will appear here for review." />
      ) : (
        <div className="panel table-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>School</th><th>Admin</th><th>Contact</th><th>Tier</th><th>Requested</th><th></th></tr>
              </thead>
              <tbody>
                {rows.map(s => (
                  <tr key={s.id} style={{ cursor: 'pointer' }} onClick={() => openDetail(s)}>
                    <td><strong>{s.name}</strong><br /><small className="muted">{s.subdomain}.tabsforge.com</small></td>
                    <td>{s.admin?.name || '—'}<br /><small className="muted">{s.admin?.email}</small></td>
                    <td>{s.contact_info?.email || '—'}<br /><small className="muted">{s.contact_info?.phone || ''}</small></td>
                    <td><span className="badge">{s.tier}</span></td>
                    <td>{new Date(s.created_at).toLocaleDateString()}</td>
                    <td><button className="ghost sm">Review →</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selected && (
        <ReviewModal
          school={selected}
          close={() => setSelected(null)}
          onSaved={s => { setSelected(s); setMsg('Changes saved.'); load() }}
          onAct={act}
        />
      )}
    </div>
  )
}

function ReviewModal({ school, close, onSaved, onAct }) {
  const [f, setF] = useState({
    name: school.name || '',
    subdomain: school.subdomain || '',
    tier: school.tier || 'Sprout',
    address: school.address || '',
    custom_domain: school.custom_domain || '',
    contact_email: school.contact_info?.email || '',
    contact_phone: school.contact_info?.phone || '',
    admin_name: school.admin?.name || '',
    admin_email: school.admin?.email || '',
    admin_notes: school.admin_notes || '',
  })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')
  const [flagReason, setFlagReason] = useState('')
  const [showFlag, setShowFlag] = useState(false)
  const [showReject, setShowReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  // Which of the school's requested above-tier modules to grant.
  const [grants, setGrants] = useState(
    () => new Set(school.enabled_modules?.length
      ? school.enabled_modules.filter(m => !(school.tier_modules || []).includes(m))
      : []))

  const set = (k, v) => setF({ ...f, [k]: v })
  const toggleGrant = key => {
    const next = new Set(grants)
    next.has(key) ? next.delete(key) : next.add(key)
    setGrants(next)
  }
  // enabled_modules = tier base + granted extras ([] keeps "all by tier" semantics
  // only when nothing extra is granted).
  const effectiveModules = grants.size
    ? [...(school.tier_modules || []), ...grants]
    : []

  const save = async () => {
    setBusy('save'); setErr('')
    try {
      const data = await patch(`/onboarding/approvals/${school.id}/`,
        { ...f, enabled_modules: effectiveModules })
      onSaved(data)
    } catch (e) { setErr(e.message) } finally { setBusy('') }
  }

  const run = (action, body) => async () => {
    setBusy(action); setErr('')
    try {
      if (grants.size) {
        await patch(`/onboarding/approvals/${school.id}/`,
          { enabled_modules: effectiveModules })
      }
      await onAct(school.id, action, body)
    } catch (e) { setErr(e.message); setBusy('') }
  }

  return (
    <Modal title={`Review — ${school.name}`} close={close} wide>
      {err && <Alert>{err}</Alert>}

      <h4 className="review-sec">School details</h4>
      <div className="form-grid">
        <label>School name
          <input value={f.name} onChange={e => set('name', e.target.value)} />
        </label>
        <label>Subdomain
          <input value={f.subdomain} onChange={e => set('subdomain', e.target.value.toLowerCase())} />
        </label>
        <label>Tier
          <select value={f.tier} onChange={e => set('tier', e.target.value)}>
            {TIERS.map(t => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label>Custom domain
          <input value={f.custom_domain} onChange={e => set('custom_domain', e.target.value)}
            placeholder="portal.school.edu" />
        </label>
        <label className="span-2">Address
          <textarea rows={2} value={f.address} onChange={e => set('address', e.target.value)} />
        </label>
        <label>Contact email
          <input type="email" value={f.contact_email} onChange={e => set('contact_email', e.target.value)} />
        </label>
        <label>Contact phone
          <input value={f.contact_phone} onChange={e => set('contact_phone', e.target.value)} />
        </label>
      </div>

      <h4 className="review-sec">Applicant admin account</h4>
      <div className="form-grid">
        <label>Admin name
          <input value={f.admin_name} onChange={e => set('admin_name', e.target.value)} />
        </label>
        <label>Admin email (their login)
          <input type="email" value={f.admin_email} onChange={e => set('admin_email', e.target.value)} />
        </label>
      </div>
      {school.subscription && (
        <p className="muted" style={{ marginTop: 8 }}>
          Trial subscription: {school.subscription.tier} · {school.subscription.billing_cycle} · ₦{school.subscription.amount} · {school.subscription.status}
        </p>
      )}

      {(school.requested_modules || []).length > 0 && (
        <>
          <h4 className="review-sec">Requested modules <small className="muted">(outside the {school.tier} plan — tick to grant)</small></h4>
          <div className="module-grid" style={{ marginBottom: 8 }}>
            {school.requested_modules.map(key => (
              <label key={key} className="check">
                <input type="checkbox" checked={grants.has(key)}
                  onChange={() => toggleGrant(key)} />
                {school.module_labels?.[key] || key}
              </label>
            ))}
          </div>
          <p className="muted" style={{ margin: '4px 0 10px' }}>
            {grants.size
              ? `${grants.size} extra module${grants.size > 1 ? 's' : ''} will be enabled alongside the ${school.tier} plan.`
              : 'No extras granted — the school gets the standard plan modules.'}
          </p>
        </>
      )}

      <h4 className="review-sec">Internal notes <small className="muted">(never shown to the school)</small></h4>
      <textarea rows={2} value={f.admin_notes} onChange={e => set('admin_notes', e.target.value)}
        placeholder="Verification notes, call-backs, concerns…" style={{ width: '100%' }} />

      <div className="modal-actions" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="ghost danger" disabled={!!busy} onClick={() => setShowReject(true)}>Reject</button>
          <button className="ghost" disabled={!!busy} onClick={() => setShowFlag(true)}>Flag for review</button>
          <button className="ghost" disabled={!!busy} onClick={run('resend-welcome')}>
            {busy === 'resend-welcome' ? 'Sending…' : 'Resend welcome email'}
          </button>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="secondary" disabled={!!busy} onClick={save}>
            {busy === 'save' ? 'Saving…' : 'Save changes'}
          </button>
          <button className="primary" disabled={!!busy} onClick={run('approve')}>
            {busy === 'approve' ? 'Approving…' : '✓ Approve & activate'}
          </button>
        </div>
      </div>

      {showFlag && (
        <div className="alert warn" style={{ marginTop: 14 }}>
          <strong>Flag this request?</strong> The school will be suspended pending review.
          <textarea rows={2} style={{ width: '100%', marginTop: 8 }} placeholder="Reason (optional)"
            value={flagReason} onChange={e => setFlagReason(e.target.value)} />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button className="ghost sm" onClick={() => setShowFlag(false)}>Cancel</button>
            <button className="primary sm" onClick={run('flag', { reason: flagReason })}>Confirm flag</button>
          </div>
        </div>
      )}

      {showReject && (
        <div className="alert" style={{ marginTop: 14 }}>
          <strong>Reject & delete this request?</strong> This permanently removes the school
          record, its admin account, and trial subscription. This cannot be undone.
          <textarea rows={2} style={{ width: '100%', marginTop: 8 }} placeholder="Reason (recorded in audit log)"
            value={rejectReason} onChange={e => setRejectReason(e.target.value)} />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button className="ghost sm" onClick={() => setShowReject(false)}>Cancel</button>
            <button className="primary sm" style={{ background: '#b91c1c' }}
              onClick={run('reject', { reason: rejectReason })}>Reject permanently</button>
          </div>
        </div>
      )}
    </Modal>
  )
}
