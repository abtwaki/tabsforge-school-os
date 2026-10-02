import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, post, patch, download } from '../api'
import { useAuth, title } from '../auth'
import { PageHead, Modal, Empty, Alert, statusBadge } from '../ui'

const ASSESSMENT_TYPES = [
  ['ca1', 'CA 1'], ['ca2', 'CA 2'], ['exam', 'Exam'], ['quiz', 'Quiz'],
  ['assignment', 'Assignment'], ['project', 'Project'], ['mid_term', 'Mid Term'],
]

const WRITERS = new Set([
  'super_admin', 'school_admin', 'principal', 'vice_principal',
  'teacher', 'form_teacher', 'exam_officer', 'staff',
])

function useLookups() {
  const [terms, setTerms] = useState([])
  const [classes, setClasses] = useState([])
  const [subjects, setSubjects] = useState([])
  useEffect(() => {
    get('/terms/?page_size=100').then(d => setTerms(d.results || d)).catch(() => {})
    get('/classes/?page_size=200').then(d => setClasses(d.results || d)).catch(() => {})
    get('/subjects/?page_size=300').then(d => setSubjects(d.results || d)).catch(() => {})
  }, [])
  return { terms, classes, subjects }
}

export default function Gradebook({ reportCards = false }) {
  const { user } = useAuth()
  const canWrite = WRITERS.has(user.role)
  const { terms, classes, subjects } = useLookups()
  const [termId, setTermId] = useState('')
  const [classId, setClassId] = useState('')
  const [subjectId, setSubjectId] = useState('')
  const [assessments, setAssessments] = useState([])
  const [assessmentId, setAssessmentId] = useState('')
  const [students, setStudents] = useState([])
  const [scores, setScores] = useState({})
  const [results, setResults] = useState([])
  const [cards, setCards] = useState([])
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [editCard, setEditCard] = useState(null)
  const [view, setView] = useState(reportCards ? 'cards' : 'entry')

  // Default selections once lookups land.
  useEffect(() => {
    if (!termId && terms.length) {
      const cur = terms.find(t => t.is_current) || terms[0]
      setTermId(String(cur.id))
    }
    if (!classId && classes.length) setClassId(String(classes[0].id))
    if (!subjectId && subjects.length) setSubjectId(String(subjects[0].id))
  }, [terms, classes, subjects, termId, classId, subjectId])

  // Assessments for the chosen scope.
  useEffect(() => {
    if (!termId || !classId || !subjectId) return
    get(`/assessments/?term=${termId}&school_class=${classId}&subject=${subjectId}&page_size=200`)
      .then(d => {
        const list = d.results || d
        setAssessments(list)
        setAssessmentId(list.length ? String(list[0].id) : '')
      })
      .catch(e => setMsg({ kind: 'error', text: e.message }))
  }, [termId, classId, subjectId])

  // Students + existing scores for the chosen assessment.
  useEffect(() => {
    if (!classId) return
    get(`/students/?school_class=${classId}&page_size=500`)
      .then(d => setStudents(d.results || d))
      .catch(() => setStudents([]))
  }, [classId])

  useEffect(() => {
    if (!assessmentId) { setScores({}); return }
    get(`/grades/?assessment=${assessmentId}&page_size=500`)
      .then(d => {
        const map = {}
        ;(d.results || d).forEach(g => { map[g.student] = g.score })
        setScores(map)
      })
      .catch(() => setScores({}))
  }, [assessmentId])

  // Results + report cards for the chosen scope.
  useEffect(() => {
    if (!termId) return
    const qs = `?term=${termId}${classId ? `&school_class=${classId}` : ''}${subjectId ? `&subject=${subjectId}` : ''}&page_size=500`
    get(`/results/${qs}`).then(d => setResults(d.results || d)).catch(() => setResults([]))
    get(`/report-cards/?term=${termId}${classId ? `&school_class=${classId}` : ''}&page_size=500`)
      .then(d => setCards(d.results || d)).catch(() => setCards([]))
  }, [termId, classId, subjectId, view])

  const assessment = assessments.find(a => String(a.id) === String(assessmentId))

  // Prerequisite chain for score entry: term → class → subject → students.
  const missingPrereqs = () => {
    if (!terms.length) return 'Create an academic session and term first (Setup → Academic Sessions / Terms).'
    if (!classes.length) return 'Create a class first (Academics → Classes & Arms).'
    if (!subjects.length) return 'Create a subject first (Academics → Subjects).'
    if (!students.length) return 'Enroll students into this class first (Students → Add / CSV import).'
    return null
  }

  const saveScores = async () => {
    if (!assessment) return
    setBusy(true)
    setMsg(null)
    try {
      const payload = {
        assessment: Number(assessmentId),
        scores: students
          .filter(s => scores[s.id] !== undefined && scores[s.id] !== '')
          .map(s => ({ student: s.id, score: scores[s.id] })),
      }
      const res = await post('/grades/bulk-enter/', payload)
      if (res.errors?.length) {
        setMsg({ kind: 'error', text: `${res.saved} saved; ${res.errors.length} row(s) rejected: ${res.errors.map(e => `student ${e.student} — ${e.error}`).join('; ')}` })
      } else {
        setMsg({ kind: 'success', text: `Saved ${res.saved} score(s) for ${assessment.name}.` })
      }
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const compute = async () => {
    if (!termId) {
      setMsg({ kind: 'error', text: 'Select a term first — results are computed per term.' })
      return
    }
    if (!results.length && !assessments.length) {
      setMsg({ kind: 'error', text: 'Nothing to compute yet — create an assessment and enter scores first.' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const res = await post('/report-cards/compute/', { term_id: Number(termId) })
      setMsg({ kind: 'success', text: res.detail || 'Results computed.' })
      setView('cards')
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const createAssessment = async e => {
    e.preventDefault()
    if (!termId || !classId || !subjectId) {
      setMsg({ kind: 'error', text: 'Pick a specific term, class, and subject in the filters above first — “All …” selections can’t be used to create an assessment.' })
      setShowNew(false)
      return
    }
    const fd = new FormData(e.target)
    setBusy(true)
    setMsg(null)
    try {
      const res = await post('/assessments/', {
        name: fd.get('name'),
        type: fd.get('type'),
        max_score: Number(fd.get('max_score') || 100),
        date: fd.get('date'),
        term: Number(termId),
        subject: Number(subjectId),
        school_class: Number(classId),
      })
      setAssessments(prev => [...prev, res])
      setAssessmentId(String(res.id))
      setShowNew(false)
      setMsg({ kind: 'success', text: `Assessment “${res.name}” created.` })
    } catch (e2) {
      setMsg({ kind: 'error', text: e2.message })
    } finally {
      setBusy(false)
    }
  }

  const publishCard = async (card, publish) => {
    try {
      await post(`/report-cards/${card.id}/${publish ? 'publish' : 'unpublish'}/`, {})
      setCards(cards.map(c => c.id === card.id ? { ...c, status: publish ? 'published' : 'draft' } : c))
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    }
  }

  const releaseClass = async publish => {
    try {
      const res = await post('/report-cards/release-class/', {
        term_id: termId ? Number(termId) : undefined,
        class_id: classId ? Number(classId) : undefined,
        publish,
      })
      setMsg({ kind: 'success', text: res.detail })
      get(`/report-cards/?term=${termId}${classId ? `&school_class=${classId}` : ''}&page_size=500`)
        .then(d => setCards(d.results || d)).catch(() => {})
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    }
  }

  const saveCardComments = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    try {
      const res = await patch(`/report-cards/${editCard.id}/`, {
        teacher_comments: fd.get('teacher_comments'),
        principal_comments: fd.get('principal_comments'),
        next_term_begins: fd.get('next_term_begins') || undefined,
      })
      setCards(cards.map(c => c.id === editCard.id ? { ...c, ...res } : c))
      setEditCard(null)
      setMsg({ kind: 'success', text: 'Report card comments saved.' })
    } catch (e2) {
      setMsg({ kind: 'error', text: e2.message })
    }
  }

  const downloadCard = async card => {
    try {
      await download(`/report-cards/${card.id}/pdf/`, `report-card-${card.student_name}.pdf`)
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    }
  }

  const viewer = ['parent', 'student', 'guest'].includes(user.role)
  const navigate = useNavigate()

  const openNew = () => {
    const missing = missingPrereqs()
    if (missing) setMsg({ kind: 'error', text: missing })
    else setShowNew(true)
  }

  return (
    <>
      <PageHead
        title={reportCards ? 'Report cards' : 'Results & grades'}
        subtitle={viewer
          ? 'Computed results and report cards.'
          : 'Create assessments, enter scores, and generate report cards.'}
        action={canWrite && !reportCards && (
          <button className="primary"
            title={missingPrereqs() || 'Create a scored assessment'}
            onClick={openNew}>＋ New assessment</button>
        )}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      <section className="panel">
        <div className="filter-row">
          <label>Term
            <select value={termId} onChange={e => setTermId(e.target.value)}>
              <option value="">All terms</option>
              {terms.map(t => <option key={t.id} value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>)}
            </select>
          </label>
          <label>Class
            <select value={classId} onChange={e => setClassId(e.target.value)}>
              <option value="">All classes</option>
              {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>Subject
            <select value={subjectId} onChange={e => setSubjectId(e.target.value)}>
              <option value="">All subjects</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <div className="segmented view-switch">
            {[['entry', 'Score entry'], ['results', 'Results'], ['cards', 'Report cards']].map(([k, l]) => (
              <button key={k} className={view === k ? 'active' : ''} onClick={() => setView(k)} type="button">{l}</button>
            ))}
          </div>
        </div>
      </section>

      {view === 'entry' && (
        <section className="panel table-panel">
          <div className="table-tools">
            <label>Assessment
              <select value={assessmentId} onChange={e => setAssessmentId(e.target.value)}>
                {assessments.length
                  ? assessments.map(a => <option key={a.id} value={a.id}>{a.name} · {title(a.type)} / {a.max_score}</option>)
                  : <option value="">No assessments — create one</option>}
              </select>
            </label>
            {canWrite && assessment && (
              <button className="primary" onClick={saveScores} disabled={busy}>
                {busy ? 'Saving…' : 'Save scores'}
              </button>
            )}
          </div>
          {assessment ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Student</th><th>Admission no.</th><th>{assessment.name} / {assessment.max_score}</th></tr>
                </thead>
                <tbody>
                  {students.map(s => (
                    <tr key={s.id}>
                      <td><strong>{s.name || `${s.first_name} ${s.last_name}`}</strong></td>
                      <td>{s.admission_number}</td>
                      <td>
                        {canWrite ? (
                          <input className="score" type="number" min="0" max={assessment.max_score}
                            value={scores[s.id] ?? ''}
                            onChange={e => setScores({ ...scores, [s.id]: e.target.value })} />
                        ) : (scores[s.id] ?? '—')}
                      </td>
                    </tr>
                  ))}
                  {!students.length && (
                    <tr><td colSpan="3">
                      <Empty title="No students in this class"
                        hint="Enroll students into this class first (Students → Add or CSV import), then scores can be entered here."
                        onAdd={canWrite ? () => navigate('/students') : undefined} />
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title="No assessment selected"
              hint={missingPrereqs()
                || 'Create an assessment first (＋ New assessment or click here), then enter scores.'}
              onAdd={canWrite ? openNew : undefined} />
          )}
        </section>
      )}

      {view === 'results' && (
        <section className="panel table-panel">
          <div className="table-tools">
            <strong>{results.length} result row(s)</strong>
            {canWrite && <button className="secondary" onClick={compute} disabled={busy}>{busy ? 'Computing…' : 'Compute results for term'}</button>}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Student</th><th>Subject</th><th>CA1</th><th>CA2</th><th>Exam</th><th>Total</th><th>Grade</th><th>Position</th></tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.id}>
                    <td><strong>{r.student_name}</strong></td>
                    <td>{r.subject_name}</td>
                    <td>{r.ca1_score}</td><td>{r.ca2_score}</td><td>{r.exam_score}</td>
                    <td><span className="grade">{r.total_score}</span></td>
                    <td>{statusBadge(r.grade)}</td>
                    <td>{r.subject_position || '—'}</td>
                  </tr>
                ))}
                {!results.length && (
                  <tr><td colSpan="8">
                    <Empty title="No computed results yet"
                      hint="Enter scores under Score entry, then use “Compute results for term” — or click here to compute."
                      onAdd={canWrite ? compute : undefined} />
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {view === 'cards' && (
        <section className="panel table-panel">
          <div className="table-tools">
            <strong>{cards.length} report card(s)</strong>
            {canWrite && (
              <span className="row-actions">
                <button className="primary" onClick={compute} disabled={busy}>{busy ? 'Computing…' : 'Generate / refresh report cards'}</button>
                <button className="secondary" onClick={() => releaseClass(true)} disabled={!cards.length}
                  title={cards.length ? 'Publish every listed card to student & parent portals' : 'Generate report cards first'}>Release to parents</button>
                <button className="secondary" onClick={() => releaseClass(false)} disabled={!cards.length}
                  title={cards.length ? 'Withdraw published cards from portals' : 'Generate report cards first'}>Unrelease</button>
                <button className="secondary" disabled={!termId}
                  title={termId ? 'Download the results table as Excel' : 'Select a term first'}
                  onClick={() => download(`/exports/results/xlsx/?term_id=${termId}${classId ? `&class_id=${classId}` : ''}`, 'results.xlsx')}>Excel</button>
                <button className="secondary" disabled={!termId}
                  title={termId ? 'Download the results table as Word' : 'Select a term first'}
                  onClick={() => download(`/exports/results/docx/?term_id=${termId}${classId ? `&class_id=${classId}` : ''}`, 'results.docx')}>Word</button>
              </span>
            )}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Student</th><th>Term</th><th>Class</th><th>Average</th><th>Position</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {cards.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.student_name}</strong></td>
                    <td>{c.term_name}</td>
                    <td>{c.class_name || '—'}</td>
                    <td><span className="grade">{c.average_score != null ? `${c.average_score}%` : '—'}</span></td>
                    <td>{c.position ? `${c.position} / ${c.class_size || '—'}` : '—'}</td>
                    <td>{statusBadge(c.status)}</td>
                    <td className="row-actions">
                      <button className="secondary" onClick={() => downloadCard(c)}>PDF</button>
                      {canWrite && <button className="secondary" onClick={() => setEditCard(c)}>Comments</button>}
                      {canWrite && (
                        <button className="secondary" onClick={() => publishCard(c, c.status !== 'published')}>
                          {c.status === 'published' ? 'Unpublish' : 'Publish'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {!cards.length && (
                  <tr><td colSpan="7">
                    <Empty title="No report cards yet"
                      hint="Generate report cards after scores are entered — cards stay hidden from parents until released. Click to generate."
                      onAdd={canWrite ? compute : undefined} />
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {showNew && (
        <Modal title="New assessment" close={() => setShowNew(false)}>
          <p className="muted" style={{ fontSize: 12 }}>
            This assessment will be created under the selected filters
            (term · class · subject). Scores for it are entered in the Score entry tab.
          </p>
          <form className="stack" onSubmit={createAssessment}>
            <label>Name<input name="name" required placeholder="e.g. First CA, Midterm Exam" /></label>
            <label>Type
              <select name="type" required>{ASSESSMENT_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </label>
            <label>Max score<input name="max_score" type="number" min="1" defaultValue="100" required /></label>
            <label>Date<input name="date" type="date" required /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowNew(false)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Create assessment'}</button>
            </div>
          </form>
        </Modal>
      )}

      {editCard && (
        <Modal title={`Comments — ${editCard.student_name}`} close={() => setEditCard(null)}>
          <form className="stack" onSubmit={saveCardComments}>
            <label>Class teacher's comment
              <textarea name="teacher_comments" rows="3" defaultValue={editCard.teacher_comments || ''} />
            </label>
            <label>Principal's comment
              <textarea name="principal_comments" rows="3" defaultValue={editCard.principal_comments || ''} />
            </label>
            <label>Next term begins
              <input name="next_term_begins" type="date" defaultValue={editCard.next_term_begins || ''} />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setEditCard(null)}>Cancel</button>
              <button className="primary">Save comments</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
