import React, { useCallback, useEffect, useState } from 'react'
import { get } from '../api'
import { Alert, Empty, PageHead, fmtDate } from '../ui'

const ACTIONS = [
  'user.create', 'user.update', 'user.suspend', 'user.activate', 'user.create_admin',
  'school.suspend', 'school.activate', 'school.update',
  'invoice.create', 'invoice.bulk_create', 'payment.record',
  'report_card.publish', 'report_card.unpublish', 'report_card.release_class',
  'grade.bulk_enter', 'submission.grade', 'session.rollover',
  'record.archive', 'record.restore', 'record.delete_permanent',
]

export default function AuditLog() {
  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [f, setF] = useState({ action: '', object_type: '', actor: '', date_from: '', date_to: '' })

  const load = useCallback(async (pg = 1, filters = f) => {
    setLoading(true)
    setError('')
    try {
      const qs = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => v && qs.set(k, v))
      qs.set('page', pg)
      const d = await get(`/audit-logs/?${qs}`)
      const batch = d.results || d
      setRows(prev => (pg === 1 ? batch : [...prev, ...batch]))
      setCount(d.count ?? batch.length)
      setPage(pg)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [f])

  useEffect(() => { load(1) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <PageHead title="Audit log"
        subtitle="Who did what, when — sensitive actions are recorded here and cannot be edited." />
      {error && <Alert kind="error">{error}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <select value={f.action} onChange={e => setF({ ...f, action: e.target.value })}>
            <option value="">All actions</option>
            {ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <input placeholder="Object type (e.g. invoice)" value={f.object_type}
            onChange={e => setF({ ...f, object_type: e.target.value })} />
          <input placeholder="Actor email" value={f.actor}
            onChange={e => setF({ ...f, actor: e.target.value })} />
          <input type="date" value={f.date_from} onChange={e => setF({ ...f, date_from: e.target.value })} />
          <input type="date" value={f.date_to} onChange={e => setF({ ...f, date_to: e.target.value })} />
          <button className="secondary" onClick={() => load(1)}>Filter</button>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>When</th><th>Actor</th><th>Action</th><th>Object</th><th>Details</th><th>IP</th>
            </tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="6">Loading…</td></tr>
              ) : rows.length ? rows.map(r => (
                <tr key={r.id}>
                  <td>{fmtDate(r.created_at)}</td>
                  <td><strong>{r.actor_email || '—'}</strong><br /><small className="muted">{r.actor_role}</small></td>
                  <td><code>{r.action}</code></td>
                  <td>{r.object_type ? `${r.object_type.split('.').pop()} #${r.object_id}` : '—'}
                    {r.object_repr && <><br /><small className="muted">{r.object_repr}</small></>}</td>
                  <td style={{ maxWidth: 280 }}>
                    {Object.keys(r.changes || {}).length
                      ? <small>{Object.entries(r.changes).map(([k, v]) =>
                          `${k}: ${Array.isArray(v) ? v.join(' → ') : typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ')}</small>
                      : '—'}
                  </td>
                  <td><small className="muted">{r.ip || '—'}</small></td>
                </tr>
              )) : (
                <tr><td colSpan="6">
                  <Empty title="No audit events"
                    hint="Actions like suspending users, recording payments, releasing report cards and archiving records are logged automatically." />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {count > rows.length && (
          <div className="table-tools" style={{ justifyContent: 'center' }}>
            <button className="secondary" onClick={() => load(page + 1)}>Load more</button>
            <small className="muted">Showing {rows.length} of {count}</small>
          </div>
        )}
      </section>
    </>
  )
}
