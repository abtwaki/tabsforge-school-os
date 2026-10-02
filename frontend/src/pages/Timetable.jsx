import React, { useEffect, useMemo, useState } from 'react'
import { get, post, patch, remove } from '../api'
import { useAuth, title } from '../auth'
import { PageHead, Modal, Empty, Alert } from '../ui'

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const EDITORS = new Set([
  'super_admin', 'school_admin', 'principal', 'vice_principal',
  'exam_officer', 'admissions_officer', 'hr_admin',
])

export default function Timetable() {
  const { user } = useAuth()
  const canEdit = EDITORS.has(user.role)
  const [sections, setSections] = useState([])
  const [subjects, setSubjects] = useState([])
  const [teachers, setTeachers] = useState([])
  const [sectionId, setSectionId] = useState('')
  const [slots, setSlots] = useState([])
  const [allSlots, setAllSlots] = useState([])
  const [show, setShow] = useState(false)
  const [editing, setEditing] = useState(null)
  const [conflicts, setConflicts] = useState([])
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    get('/sections/?page_size=300').then(d => {
      const list = d.results || d
      setSections(list)
      if (list.length && !sectionId) setSectionId(String(list[0].id))
    }).catch(() => {})
    get('/subjects/?page_size=300').then(d => setSubjects(d.results || d)).catch(() => {})
    get('/users/?page_size=300').then(d => setTeachers((d.results || d).filter(u => !['parent', 'student', 'guest'].includes(u.role)))).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = () => {
    get('/timetable/?page_size=500')
      .then(d => {
        const list = d.results || d
        setAllSlots(list)
        setSlots(sectionId ? list.filter(t => String(t.section) === String(sectionId)) : list)
      })
      .catch(e => setMsg({ kind: 'error', text: e.message }))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [sectionId])

  const grid = useMemo(() => {
    const byDay = {}
    DAYS.forEach(d => { byDay[d] = [] })
    slots.forEach(s => { (byDay[s.day] = byDay[s.day] || []).push(s) })
    Object.values(byDay).forEach(list => list.sort((a, b) => a.start_time.localeCompare(b.start_time)))
    return byDay
  }, [slots])

  const checkConflicts = async entry => {
    try {
      const res = await post('/ai/timetable-conflicts/', { entries: [entry], check_existing: true })
      setConflicts(res.conflicts || [])
      return res
    } catch {
      return null
    }
  }

  const save = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    const entry = {
      section: Number(fd.get('section')),
      subject: Number(fd.get('subject')),
      teacher: fd.get('teacher') ? Number(fd.get('teacher')) : null,
      day: fd.get('day'),
      start_time: fd.get('start_time'),
      end_time: fd.get('end_time'),
      room: fd.get('room') || '',
    }
    if (entry.end_time <= entry.start_time) {
      setMsg({ kind: 'error', text: 'End time must be after start time.' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const res = await checkConflicts({
        teacher_id: entry.teacher,
        section_id: entry.section,
        subject_id: entry.subject,
        day: entry.day,
        start_time: entry.start_time,
        end_time: entry.end_time,
        room: entry.room,
        id: editing?.id,
      })
      if (res?.has_conflicts && !editing) {
        setMsg({ kind: 'error', text: `Slot has conflicts: ${res.conflicts.map(c => c.message).join('; ')}` })
        setBusy(false)
        return
      }
      if (editing) {
        await patch(`/timetable/${editing.id}/`, entry)
      } else {
        await post('/timetable/', entry)
      }
      setShow(false)
      setEditing(null)
      setMsg({ kind: 'success', text: 'Timetable slot saved.' })
      load()
    } catch (e2) {
      setMsg({ kind: 'error', text: e2.message })
    } finally {
      setBusy(false)
    }
  }

  const del = async slot => {
    if (!window.confirm(`Delete ${slot.subject_name} on ${title(slot.day)} ${slot.start_time}–${slot.end_time}?`)) return
    try {
      await remove(`/timetable/${slot.id}/`)
      setSlots(slots.filter(s => s.id !== slot.id))
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    }
  }

  const sec = sections.find(s => String(s.id) === String(sectionId))
  return (
    <>
      <PageHead
        title="Timetable"
        subtitle={sec ? `Weekly schedule for ${sec.class_name || ''} ${sec.name}` : 'Weekly class schedules'}
        action={canEdit && <button className="primary" onClick={() => { setEditing(null); setShow(true) }}>＋ Add slot</button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {conflicts.length > 0 && (
        <Alert kind="error">
          <strong>Conflicts:</strong>
          <ul>{conflicts.map((c, i) => <li key={i}>{c.message}</li>)}</ul>
        </Alert>
      )}
      <section className="panel timetable">
        <div className="table-tools">
          <label>Section
            <select value={sectionId} onChange={e => setSectionId(e.target.value)}>
              {sections.map(s => <option key={s.id} value={s.id}>{s.class_name ? `${s.class_name} · ` : ''}{s.name}</option>)}
            </select>
          </label>
          <button className="secondary" onClick={async () => {
            // Validate every loaded slot against the rest of the timetable.
            const entries = allSlots.map(t => ({
              id: t.id, teacher_id: t.teacher, section_id: t.section,
              subject_id: t.subject, day: t.day,
              start_time: t.start_time.slice(0, 5), end_time: t.end_time.slice(0, 5),
              room: t.room,
            }))
            try {
              const res = await post('/ai/timetable-conflicts/', { entries, check_existing: false })
              setConflicts(res.conflicts || [])
              if (!res.has_conflicts) setMsg({ kind: 'success', text: 'No conflicts found.' })
            } catch (e) { setMsg({ kind: 'error', text: e.message }) }
          }}>
            Check conflicts
          </button>
        </div>
        <div className="tt-week">
          {DAYS.map(day => (
            <div className="tt-day" key={day}>
              <strong>{title(day)}</strong>
              {(grid[day] || []).length ? grid[day].map(s => (
                <div className="tt-slot" key={s.id}>
                  <time>{s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)}</time>
                  <b>{s.subject_name}</b>
                  <small>{s.teacher_name || 'No teacher'}{s.room ? ` · ${s.room}` : ''}</small>
                  {canEdit && (
                    <span className="tt-actions">
                      <button onClick={() => { setEditing(s); setShow(true) }}>Edit</button>
                      <button onClick={() => del(s)}>✕</button>
                    </span>
                  )}
                </div>
              )) : <div className="tt-empty">No classes</div>}
            </div>
          ))}
        </div>
      </section>

      {show && (
        <Modal title={editing ? 'Edit timetable slot' : 'New timetable slot'} close={() => { setShow(false); setEditing(null) }}>
          {!sections.length && (
            <Alert kind="error">No class sections exist yet — create sections first (Academics → Sections) before scheduling.</Alert>
          )}
          {sections.length > 0 && !subjects.length && (
            <Alert kind="error">No subjects exist yet — create subjects first (Academics → Subjects).</Alert>
          )}
          <form className="stack" onSubmit={save}>
            <label>Section
              <select name="section" required defaultValue={editing?.section || sectionId}>
                {sections.map(s => <option key={s.id} value={s.id}>{s.class_name ? `${s.class_name} · ` : ''}{s.name}</option>)}
              </select>
            </label>
            <label>Subject
              <select name="subject" required defaultValue={editing?.subject}>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>Teacher
              <select name="teacher" defaultValue={editing?.teacher || ''}>
                <option value="">—</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.name || t.email} ({title(t.role)})</option>)}
              </select>
            </label>
            <div className="form-grid">
              <label>Day
                <select name="day" required defaultValue={editing?.day || 'monday'}>
                  {DAYS.map(d => <option key={d} value={d}>{title(d)}</option>)}
                </select>
              </label>
              <label>Room<input name="room" defaultValue={editing?.room || ''} placeholder="e.g. Room 8" /></label>
              <label>Start<input name="start_time" type="time" required defaultValue={editing?.start_time?.slice(0, 5) || '08:00'} /></label>
              <label>End<input name="end_time" type="time" required defaultValue={editing?.end_time?.slice(0, 5) || '09:00'} /></label>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => { setShow(false); setEditing(null) }}>Cancel</button>
              <button className="primary" disabled={busy || !sections.length || !subjects.length}
                title={(!sections.length || !subjects.length) ? 'Create sections and subjects first' : ''}>
                {busy ? 'Saving…' : 'Save slot'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
