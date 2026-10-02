import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { get } from '../api'
import { useAuth, title } from '../auth'
import { PageHead, money } from '../ui'

const MONEY_KEYS = new Set([
  'fees_collected', 'outstanding_fees', 'total_billed', 'expenses_total',
  'net_balance', 'total_payments',
])
const PCT_KEYS = new Set(['collection_rate', 'attendance_today'])

const CHECKLIST_LINKS = {
  add_classes: 'classes', add_staff: 'staff', add_students: 'students',
  set_fees: 'fee-structures', customize_branding: 'branding',
  invite_parents: 'guardians',
}

// Backend task links use API-ish paths; map them to app routes.
const TASK_LINKS = {
  attendance: 'attendance', admissions: 'applications', results: 'grades',
  homework: 'assignments', finance: 'fees',
}
const taskLink = link => {
  const seg = String(link || '').replace(/^\/+|\/.*$/g, '')
  return TASK_LINKS[seg] || null
}

// Where each KPI drills down to (view/edit the underlying records).
const KPI_LINKS = {
  total_students: 'students', total_staff: 'staff', total_users: 'users-roles',
  total_schools: 'schools', active_schools: 'schools',
  pending_approvals: 'approvals', onboarding_schools: 'approvals',
  suspended_schools: 'schools', attendance_today: 'attendance',
  fees_collected: 'payments', outstanding_fees: 'invoices',
  total_billed: 'invoices', open_invoices: 'invoices',
  collection_rate: 'fees', expenses_total: 'expenses',
  net_balance: 'fees', average_grade: 'grades', total_payments: 'payments',
}

function fmt(key, value) {
  if (MONEY_KEYS.has(key)) return money(value)
  if (PCT_KEYS.has(key)) return `${value}%`
  return typeof value === 'number' ? value.toLocaleString() : value
}

export default function Dashboard({ analytics = false }) {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [tasks, setTasks] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    get(analytics ? '/analytics/' : '/dashboard/')
      .then(setData)
      .catch(e => setError(e.message))
    if (!analytics) {
      get('/tasks/')
        .then(d => setTasks(d.tasks || []))
        .catch(() => setTasks([]))
    }
  }, [analytics])

  const cards = data?.kpis
    ? Object.entries(data.kpis).map(([k, v], i) => {
        // Role-aware drill-down: super admins use /users, school admins /users-roles.
        let link = KPI_LINKS[k]
        if (k === 'total_users') link = user.role === 'super_admin' ? 'users' : 'users-roles'
        return [title(k), fmt(k, v), 'Live data', link]
      })
    : []
  const checklist = data?.checklist || null
  const progress = data?.checklist_progress

  return (
    <>
      <PageHead
        title={analytics ? 'Platform analytics' : `Good day, ${(user.name || 'Administrator').split(' ')[0]}`}
        subtitle={analytics
          ? 'Performance across all schools on TabsForge.'
          : 'Here’s what is happening across your school today.'}
      />
      {error && <div className="alert">Could not load dashboard: {error}</div>}
      {!error && !data && <div className="loading">Loading dashboard…</div>}
      <div className="kpi-grid">
        {cards.map(([label, value, note, link], i) => {
          const inner = (
            <>
              <span className={`kpi-icon c${i}`}>{['↗', '✓', '◷', '₦'][i] || '•'}</span>
              <small>{label}</small>
              <strong>{value}</strong>
              <p>{link ? 'View details →' : note}</p>
            </>
          )
          return link
            ? <Link className="kpi" to={`/${link}`} key={label}>{inner}</Link>
            : <article className="kpi" key={label}>{inner}</article>
        })}
      </div>
      {tasks !== null && tasks.length > 0 && (
        <section className="panel checklist">
          <div className="panel-title">
            <h3>Pending tasks</h3>
            <span className="badge warn">{tasks.length} open</span>
          </div>
          <div>
            {tasks.map(t => (
              <div className="task-item" key={t.id || t.title}>
                <span className={`task-prio ${t.priority || 'medium'}`}>{t.priority || 'task'}</span>
                <div>
                  <strong>{t.link && taskLink(t.link)
                    ? <Link to={`/${taskLink(t.link)}`}>{t.title}</Link>
                    : t.title}</strong>
                  <p style={{ margin: '3px 0 0', fontSize: 13, color: 'var(--muted)' }}>{t.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      {checklist && progress && progress.completed < progress.total && (
        <section className="panel checklist">
          <div className="panel-title">
            <h3>Setup checklist</h3>
            <span className="badge">{progress.completed}/{progress.total} complete</span>
          </div>
          <ul>
            {Object.entries(checklist).map(([k, done]) => (
              <li key={k} className={done ? 'done' : ''}>
                <span>{done ? '✓' : '○'}</span>{' '}
                {CHECKLIST_LINKS[k]
                  ? <Link to={`/${CHECKLIST_LINKS[k]}`}>{title(k)}</Link>
                  : title(k)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {data?.schools_by_tier && (
        <section className="panel checklist">
          <div className="panel-title"><h3>Schools by tier</h3></div>
          <ul>
            {Object.entries(data.schools_by_tier).map(([k, v]) => (
              <li key={k}><strong>{v}</strong> {k}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
