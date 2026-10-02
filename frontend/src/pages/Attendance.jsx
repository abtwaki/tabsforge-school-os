import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, post } from '../api'
import { useAuth, title } from '../auth'
import { PageHead, Modal, Empty, Alert, fmtDate, statusBadge } from '../ui'
import { queueItem, flushQueue, listQueue } from '../offline'

const STATUSES = ['present', 'late', 'absent', 'excused']
const today = () => new Date().toISOString().slice(0, 10)

function RollCall({ user }) {
  const navigate = useNavigate()
  const [classes, setClasses] = useState([])
  const [classId, setClassId] = useState('')
  const [date, setDate] = useState(today())
  const [students, setStudents] = useState([])
  const [marks, setMarks] = useState({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [online, setOnline] = useState(navigator.onLine)
  const [queued, setQueued] = useState(0)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    get('/classes/?page_size=200')
      .then(d => {
        const list = d.results || d
        setClasses(list)
        if (list.length && !classId) setClassId(String(list[0].id))
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refreshQueue = useCallback(
    () => listQueue().then(items => setQueued(items.filter(i => i.kind === 'attendance').length)),
    [])

  const syncQueue = useCallback(async () => {
    if (!navigator.onLine) return
    setSyncing(true)
    const res = await flushQueue(item =>
      post('/attendance/bulk-mark/', item.payload))
    setSyncing(false)
    refreshQueue()
    if (res.sent) setMsg({ kind: 'success', text: `Synced ${res.sent} queued attendance record(s).` })
    if (res.failed) setMsg({ kind: 'error', text: `${res.failed} queued record(s) failed to sync.` })
  }, [refreshQueue])

  useEffect(() => {
    const on = () => { setOnline(true); syncQueue() }
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    refreshQueue()
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [syncQueue, refreshQueue])

  // Load roster + existing marks whenever class/date changes.
  useEffect(() => {
    if (!classId) return
    setLoading(true)
    setMsg(null)
    Promise.all([
      get(`/students/?school_class=${classId}&page_size=500`),
      get(`/attendance/?school_class=${classId}&date=${date}&page_size=500`),
    ])
      .then(([stu, att]) => {
        const roster = stu.results || stu
        setStudents(roster)
        const existing = {}
        ;(att.results || att).forEach(a => { existing[a.student] = a.status })
        const initial = {}
        roster.forEach(s => { initial[s.id] = existing[s.id] || 'present' })
        setMarks(initial)
      })
      .catch(e => {
        if (!navigator.onLine) {
          setStudents([])
          setMsg({ kind: 'error', text: 'Offline — roster unavailable. Cached marks can still be queued once a roster was previously loaded.' })
        } else {
          setMsg({ kind: 'error', text: e.message })
        }
      })
      .finally(() => setLoading(false))
  }, [classId, date])

  const summary = useMemo(() => {
    const counts = { present: 0, late: 0, absent: 0, excused: 0 }
    Object.values(marks).forEach(s => { counts[s] = (counts[s] || 0) + 1 })
    return counts
  }, [marks])

  const save = async () => {
    const payload = {
      school_class: Number(classId),
      date,
      marks: students.map(s => ({ student: s.id, status: marks[s.id] || 'present' })),
    }
    setSaving(true)
    setMsg(null)
    try {
      const res = await post('/attendance/bulk-mark/', payload)
      setMsg({ kind: 'success', text: `Attendance saved for ${res.saved} students.` })
    } catch (e) {
      // Network failure → queue locally for background sync.
      if (!navigator.onLine || /failed to fetch|network/i.test(e.message)) {
        await queueItem('attendance', payload)
        refreshQueue()
        setMsg({ kind: 'success', text: 'Offline — attendance queued and will sync automatically when reconnected.' })
      } else {
        setMsg({ kind: 'error', text: e.message })
      }
    } finally {
      setSaving(false)
    }
  }

  const cls = classes.find(c => String(c.id) === String(classId))
  return (
    <>
      <PageHead
        title="Daily attendance"
        subtitle="Mark and review student attendance — saved to the register."
        action={<button className="primary" onClick={save} disabled={saving || !students.length}
          title={students.length ? 'Save today’s register' : 'No students to mark — enroll students into this class first'}>
          {saving ? 'Saving…' : 'Save attendance'}
        </button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="sync-strip">
        <span className={online ? 'sync-dot on' : 'sync-dot off'} />
        {online ? 'Online' : 'Offline'}
        {queued > 0 && <span className="badge warn">{queued} queued</span>}
        {queued > 0 && online && (
          <button className="secondary" onClick={syncQueue} disabled={syncing}>
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
        )}
      </div>
      {!classes.length && !loading && (
        <Alert kind="error">No classes exist yet — create a class (Academics → Classes &amp; Arms) and enroll students before taking attendance.</Alert>
      )}
      <section className="panel">
        <div className="filter-row">
          <label>Class
            <select value={classId} onChange={e => setClassId(e.target.value)}>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>Date
            <input type="date" value={date} onChange={e => setDate(e.target.value)} />
          </label>
          <div className="attendance-summary">
            <strong>{(summary.present || 0) + (summary.late || 0)} / {students.length}</strong>
            <small>In school {cls ? `· ${cls.name}` : ''}</small>
          </div>
          <div className="attendance-summary absent">
            <strong>{summary.absent || 0}</strong>
            <small>Absent</small>
          </div>
        </div>
        {loading ? <div className="loading">Loading roster…</div> : (
          students.length ? (
            <div className="roll-call">
              {students.map(s => (
                <div key={s.id} className="roll-row">
                  <span className="student-avatar">
                    {`${s.first_name?.[0] || ''}${s.last_name?.[0] || ''}`.toUpperCase()}
                  </span>
                  <div className="roll-meta">
                    <strong>{s.name || `${s.first_name} ${s.last_name}`}</strong>
                    <small>{s.admission_number}{s.class_name ? ` · ${s.class_name}` : ''}</small>
                  </div>
                  <div className="segmented">
                    {STATUSES.map(v => (
                      <button type="button" key={v}
                        className={marks[s.id] === v ? `active ${v}` : ''}
                        onClick={() => setMarks({ ...marks, [s.id]: v })}>
                        {title(v)}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No students in this class"
              hint="Enroll students into this class first (Students → Add or CSV import), then mark the register here."
              onAdd={() => navigate('/students')} />
          ))}
      </section>
    </>
  )
}

function AttendanceHistory() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const load = () => {
    setLoading(true)
    const params = `?page_size=100${from ? `&date_from=${from}` : ''}${to ? `&date_to=${to}` : ''}`
    get(`/attendance/${params}`)
      .then(d => setRows(d.results || d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [])

  return (
    <>
      <PageHead title="Attendance" subtitle="Your daily attendance record." />
      {error && <Alert kind="error">{error}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <label>From <input type="date" value={from} onChange={e => setFrom(e.target.value)} /></label>
          <label>To <input type="date" value={to} onChange={e => setTo(e.target.value)} /></label>
          <button className="secondary" onClick={load}>Apply</button>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Date</th><th>Student</th><th>Class</th><th>Status</th><th>Marked by</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan="5">Loading…</td></tr>
                : rows.length ? rows.map(r => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.date)}</td>
                    <td><strong>{r.student_name}</strong></td>
                    <td>{r.class_name}</td>
                    <td>{statusBadge(r.status)}</td>
                    <td>{r.marked_by_name || '—'}</td>
                  </tr>
                )) : (
                  <tr><td colSpan="5">
                    <Empty title="No attendance records"
                      hint="Registers saved on the Daily attendance tab appear here — pick a class and date, mark students, then Save attendance." />
                  </td></tr>
                )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

export default function Attendance() {
  const { user } = useAuth()
  if (['parent', 'student', 'guest'].includes(user.role)) return <AttendanceHistory />
  return <RollCall user={user} />
}
