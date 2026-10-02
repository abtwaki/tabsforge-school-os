import React, { useEffect, useState } from 'react'
import { get, post } from '../api'
import { PageHead, Alert, Empty, fmtDate } from '../ui'

const FLAG_LABELS = {
  grade_decline: 'Grade decline',
  low_attendance: 'Low attendance',
  multiple: 'Multiple factors',
}

export default function AtRisk() {
  const [flags, setFlags] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [showResolved, setShowResolved] = useState(false)
  const [notifyParents, setNotifyParents] = useState(false)
  const [msg, setMsg] = useState(null)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    get(`/ai/at-risk-students/${showResolved ? '?resolved=true' : ''}`)
      .then(d => setFlags(d.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [showResolved]) // eslint-disable-line react-hooks/exhaustive-deps

  const runAnalysis = async () => {
    setRunning(true)
    setMsg(null)
    try {
      const res = await post('/ai/run-risk-analysis/', { notify_parents: notifyParents })
      setMsg({ kind: 'success', text: res.detail || 'Risk analysis complete.' })
      load()
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    } finally {
      setRunning(false)
    }
  }

  const resolve = async flag => {
    try {
      await post(`/ai/at-risk-students/${flag.id}/resolve/`, {})
      setFlags(f => f.filter(x => x.id !== flag.id))
      setMsg({ kind: 'success', text: `Flag for ${flag.student_name} resolved.` })
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    }
  }

  return (
    <>
      <PageHead
        title="At-risk Students"
        subtitle="Early-warning flags from attendance and grade trends — act before students fall behind."
        action={
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <label style={{ fontSize: 13 }} className="muted">
              <input type="checkbox" checked={notifyParents} onChange={e => setNotifyParents(e.target.checked)} /> Notify parents
            </label>
            <button className="primary" onClick={runAnalysis} disabled={running}>
              {running ? 'Analysing…' : 'Run analysis'}
            </button>
          </div>
        }
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {error && <Alert kind="error">Could not load flags: {error}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <button className="secondary" onClick={() => setShowResolved(v => !v)}>
            {showResolved ? '← Open flags' : 'Resolved flags'}
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Student</th><th>Admission no.</th><th>Class</th><th>Risk</th><th>Reason</th><th>Flagged</th><th /></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7}>Loading…</td></tr>
              ) : flags.length ? (
                flags.map(f => (
                  <tr key={f.id}>
                    <td><strong>{f.student_name}</strong></td>
                    <td>{f.student_admission_number}</td>
                    <td>{f.student_class || '—'}</td>
                    <td><span className="badge warn">{FLAG_LABELS[f.flag_type] || f.flag_type}</span></td>
                    <td style={{ maxWidth: 340 }}>{f.reason}</td>
                    <td>{fmtDate(f.flagged_at)}</td>
                    <td>
                      {!f.resolved && !showResolved && (
                        <button className="ghost sm" onClick={() => resolve(f)}>Resolve</button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={7}><Empty title={showResolved ? 'No resolved flags' : 'No at-risk flags'} hint="Run an analysis to scan attendance and grade trends." /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
