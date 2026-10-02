import React, { useEffect, useState } from 'react'
import { get, post } from '../api'
import { Alert, Empty, Modal, fmtDate, statusBadge } from '../ui'

/** Grading drawer for one assignment: every submission with score/feedback
 * inputs, plus enrolled students who haven't submitted yet. */
export default function SubmissionsModal({ assignment, close }) {
  const [subs, setSubs] = useState(null)
  const [enrolled, setEnrolled] = useState([])
  const [drafts, setDrafts] = useState({})
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = () => {
    get(`/assignments/${assignment.id}/submissions/`)
      .then(d => setSubs(d.results || d))
      .catch(e => setMsg({ kind: 'error', text: e.message }))
    if (assignment.school_class) {
      get(`/enrollments/?school_class=${assignment.school_class}&status=active&page_size=500`)
        .then(d => setEnrolled(d.results || d))
        .catch(() => {})
    }
  }
  useEffect(load, [assignment.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (subs === null) return <Modal title={assignment.title} close={close} wide><p>Loading submissions…</p></Modal>

  const submittedIds = new Set(subs.map(s => s.student))
  const missing = enrolled.filter(e => !submittedIds.has(e.student))
  const isPast = assignment.due_date && new Date(assignment.due_date) < new Date()

  const draft = (id, patch) => setDrafts(d => ({ ...d, [id]: { ...d[id], ...patch } }))

  const grade = async sub => {
    const d = drafts[sub.id] || {}
    setBusy(sub.id)
    setMsg(null)
    try {
      await post(`/submissions/${sub.id}/grade/`, {
        score: d.score ?? sub.score, feedback: d.feedback ?? sub.feedback,
      })
      setMsg({ kind: 'success', text: `Saved mark for ${sub.student_name}.` })
      load()
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
    finally { setBusy(null) }
  }

  const returnWork = async sub => {
    setBusy(sub.id)
    try {
      await post(`/submissions/${sub.id}/return/`, {})
      setMsg({ kind: 'success', text: `Returned to ${sub.student_name}.` })
      load()
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
    finally { setBusy(null) }
  }

  return (
    <Modal title={`${assignment.title} — submissions`} close={close} wide>
      <p className="muted">
        {assignment.class_name} · {assignment.subject_name} · due {fmtDate(assignment.due_date)}
        · max {assignment.max_points} pts — {subs.length} submitted, {missing.length} outstanding.
      </p>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {!!missing.length && (
        <Alert kind="warn">
          <strong>Not submitted ({missing.length}):</strong>{' '}
          {missing.map(e => e.student_name || `#${e.student}`).join(', ')}
          {isPast ? ' — past due.' : '.'}
        </Alert>
      )}
      {!subs.length && !missing.length && (
        <Empty title="No submissions yet" hint="Students submit from their portal — their work appears here for marking." />
      )}
      {!!subs.length && (
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>Student</th><th>Submitted</th><th>Work</th>
              <th>Score /{assignment.max_points}</th><th>Feedback</th><th>Status</th><th />
            </tr></thead>
            <tbody>
              {subs.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.student_name}</strong></td>
                  <td>{fmtDate(s.submitted_at)}</td>
                  <td style={{ maxWidth: 220 }}>
                    {s.file_url && <a href={s.file_url} target="_blank" rel="noreferrer">📎 file</a>}
                    {s.content && <span title={s.content}>{s.content.slice(0, 60)}{s.content.length > 60 ? '…' : ''}</span>}
                    {!s.file_url && !s.content && '—'}
                  </td>
                  <td>
                    <input type="number" min="0" max={assignment.max_points} step="0.5"
                      style={{ width: 90 }}
                      value={(drafts[s.id]?.score ?? s.score) ?? ''}
                      onChange={e => draft(s.id, { score: e.target.value })} />
                  </td>
                  <td>
                    <input type="text" style={{ minWidth: 160 }}
                      value={drafts[s.id]?.feedback ?? s.feedback ?? ''}
                      placeholder="Feedback…"
                      onChange={e => draft(s.id, { feedback: e.target.value })} />
                  </td>
                  <td>{statusBadge(s.status)}</td>
                  <td>
                    <div className="row-actions">
                      <button className="ghost sm" disabled={busy === s.id}
                        onClick={() => grade(s)}>
                        {busy === s.id ? '…' : s.status === 'submitted' || s.status === 'late' ? 'Mark' : 'Update'}
                      </button>
                      {s.status === 'graded' && (
                        <button className="ghost sm" disabled={busy === s.id}
                          title="Publish the grade to the student"
                          onClick={() => returnWork(s)}>Return</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
