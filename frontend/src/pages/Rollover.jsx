import React, { useEffect, useMemo, useState } from 'react'
import { get, post } from '../api'
import { Alert, Empty, PageHead } from '../ui'

/** End-of-session rollover wizard: promote classes, graduate leavers,
 * and carry enrolments into a new session — instead of re-enrolling
 * the whole school by hand. */
export default function Rollover() {
  const [sessions, setSessions] = useState([])
  const [terms, setTerms] = useState([])
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [targetTerm, setTargetTerm] = useState('')
  const [preview, setPreview] = useState(null)
  const [actions, setActions] = useState({})
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    get('/academic-sessions/?page_size=50').then(d => {
      const list = d.results || d
      setSessions(list)
      const cur = list.find(s => s.is_current)
      if (cur) setSource(String(cur.id))
    }).catch(e => setError(e.message))
    get('/terms/?page_size=100').then(d => setTerms(d.results || d)).catch(() => {})
  }, [])

  const targetTerms = useMemo(
    () => terms.filter(t => String(t.session) === String(target)),
    [terms, target],
  )

  const runPreview = async () => {
    if (!source || !target) { setError('Pick a source and a target session.'); return }
    setBusy(true); setError(''); setResult(null)
    try {
      const d = await get(`/rollover/preview/?source_session=${source}&target_session=${target}`)
      setPreview(d)
      // Sensible defaults: promote to nothing chosen yet (admin picks), unless no students.
      const init = {}
      d.classes.forEach(c => { if (c.students) init[c.class_id] = 'skip' })
      setActions(init)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const execute = async () => {
    const mapped = Object.entries(actions).filter(([, a]) => a && a !== 'skip')
    if (!mapped.length) { setError('Choose an action for at least one class (promote or graduate).'); return }
    if (!targetTerm) { setError('Pick the target term new enrolments will use.'); return }
    const lines = mapped.map(([cid, a]) => {
      const cls = preview.classes.find(c => String(c.class_id) === String(cid))
      const label = a === 'graduate' ? 'graduate (alumni)'
        : `promote → ${preview.all_classes.find(c => `promote:${c.id}` === a)?.name}`
      return `${cls?.class_name || cid}: ${label}`
    })
    if (!window.confirm(`Run rollover?\n\n${lines.join('\n')}\n\nThis creates new enrolments and marks the old ones completed.`)) return
    setBusy(true); setError('')
    try {
      const mappings = Object.fromEntries(mapped)
      const res = await post('/rollover/', {
        source_session: Number(source), target_session: Number(target),
        target_term: Number(targetTerm), mappings,
      })
      setResult(res)
      setPreview(null)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  return (
    <>
      <PageHead title="Promotion & rollover"
        subtitle="Move each class forward into a new session — promote, graduate, or skip. Records carry forward; nothing is deleted." />
      {error && <Alert kind="error">{error}</Alert>}
      {result && (
        <Alert kind="success">
          <strong>{result.detail}</strong>
          <ul style={{ margin: '8px 0 0' }}>
            {result.results.map((r, i) => (
              <li key={i}>
                {r.class}: {r.promoted ? `${r.promoted} promoted` : ''}
                {r.graduated ? ` ${r.graduated} graduated` : ''}
                {r.skipped ? ` ${r.skipped} skipped` : ''}
                {r.error ? ` — ${r.error}` : ''}
                {r.skipped_students?.length ? ` (${r.skipped_students.join(', ')})` : ''}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      <section className="panel">
        <div className="form-grid" style={{ alignItems: 'end' }}>
          <label>From session (closing)
            <select value={source} onChange={e => setSource(e.target.value)}>
              <option value="">Select…</option>
              {sessions.map(s => <option key={s.id} value={s.id}>{s.name}{s.is_current ? ' (current)' : ''}</option>)}
            </select>
          </label>
          <label>To session (new)
            <select value={target} onChange={e => { setTarget(e.target.value); setTargetTerm('') }}>
              <option value="">Select…</option>
              {sessions.filter(s => String(s.id) !== String(source)).map(s =>
                <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label>First term of new session
            <select value={targetTerm} onChange={e => setTargetTerm(e.target.value)} disabled={!target}>
              <option value="">Select…</option>
              {targetTerms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <button className="primary" onClick={runPreview} disabled={busy || !source || !target}>
            {busy ? 'Loading…' : 'Preview classes'}
          </button>
        </div>
        {!sessions.length && !error && (
          <Alert kind="warn">No academic sessions yet — create the new session and its first term first (Academics → Academic Sessions / Terms).</Alert>
        )}
      </section>

      {preview && (
        <section className="panel table-panel">
          <div className="panel-title"><h3>Choose what happens to each class</h3></div>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>Class</th><th>Active students</th><th>Already in target</th><th>Action</th>
              </tr></thead>
              <tbody>
                {preview.classes.map(c => (
                  <tr key={c.class_id}>
                    <td><strong>{c.class_name}</strong></td>
                    <td>{c.students}</td>
                    <td>{c.already_in_target || '—'}</td>
                    <td>
                      {c.students === 0 ? <span className="muted">no students</span> : (
                        <select value={actions[c.class_id] || 'skip'}
                          onChange={e => setActions({ ...actions, [c.class_id]: e.target.value })}>
                          <option value="skip">Skip (leave as-is)</option>
                          {preview.all_classes
                            .filter(t => t.id !== c.class_id)
                            .map(t => <option key={t.id} value={`promote:${t.id}`}>Promote → {t.name}</option>)}
                          <option value="graduate">Graduate (mark as alumni)</option>
                        </select>
                      )}
                    </td>
                  </tr>
                ))}
                {!preview.classes.some(c => c.students) && (
                  <tr><td colSpan="4">
                    <Empty title="No active enrolments"
                      hint="There are no active enrolments in the source session — enrol students first." />
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="modal-actions" style={{ padding: '12px 0 0' }}>
            <button className="primary" onClick={execute}
              disabled={busy || !targetTerm || !Object.values(actions).some(a => a !== 'skip')}
              title={!targetTerm ? 'Pick the first term of the new session' : ''}>
              Run rollover
            </button>
          </div>
        </section>
      )}
    </>
  )
}
