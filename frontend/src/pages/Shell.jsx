import React, { useEffect, useMemo, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth, roleLabel, title } from '../auth'
import { Alert, BrandMark, Modal } from '../ui'
import { get, patch, post, chatSocketUrl, getSchoolCtx, setSchoolCtx } from '../api'
import Dashboard from './Dashboard'
import Attendance from './Attendance'
import Gradebook from './Gradebook'
import Timetable from './Timetable'
import Fees from './Fees'
import Announcements from './Announcements'
import Branding from './Branding'
import RoleManager from './RoleManager'
import SchoolsAdmin from './SchoolsAdmin'
import CsvImport from './CsvImport'
import Messages from './Messages'
import ModulePage from './ModulePage'
import AuditLog from './AuditLog'
import Rollover from './Rollover'
import DataExport from './DataExport'
import Approvals from './Approvals'
import PlatformUsers from './PlatformUsers'
import DemoLeads from './DemoLeads'
import AiAssistant from './AiAssistant'
import AtRisk from './AtRisk'

const tierRank = { sprout: 1, roots: 2, bloom: 3, summit: 4 }

// Session policy: 30 min idle / 12 h absolute by default;
// "Keep me signed in" extends to a 30-day absolute cap (no idle timeout).
const IDLE_LIMIT_MS = 30 * 60 * 1000
const ABSOLUTE_LIMIT_MS = 12 * 60 * 60 * 1000
const STAY_LIMIT_MS = 30 * 24 * 60 * 60 * 1000

const ADMIN_MENU = [
  { label: 'Overview', items: [['Dashboard', 'dashboard']] },
  { label: 'Admissions & Enrolment', items: [['Applications', 'applications'], ['Enrollments', 'enrollments']] },
  { label: 'Students', items: [['All Students', 'students'], ['Guardians', 'guardians']] },
  {
    label: 'Academics',
    items: [
      ['Classes & Arms', 'classes'], ['Sections', 'sections'], ['Subjects', 'subjects'],
      ['Sessions', 'academic-sessions'], ['Terms', 'terms'],
      ['Results & Grades', 'grades'], ['Report Cards', 'report-cards'],
      ['Grading Schemes', 'grading-schemes'], ['Timetable', 'timetable'],
      ['Assignments', 'assignments'], ['Promotion & Rollover', 'rollover'],
    ],
  },
  { label: 'Attendance', items: [['Daily Attendance', 'attendance']] },
  {
    label: 'Fees & Finance',
    items: [
      ['Finance Overview', 'fees'], ['Fee Categories', 'fee-categories'],
      ['Fee Structures', 'fee-structures'], ['Invoices', 'invoices'],
      ['Payments', 'payments'], ['Expenses', 'expenses'],
    ],
  },
  { label: 'Staff & Communication', items: [['All Staff', 'staff'], ['Announcements', 'announcements'], ['Notices', 'notices'], ['Messages', 'messages']] },
  {
    label: 'Resources',
    items: [
      ['Library', 'library', 'bloom'],
      ['Transport', 'transport', 'summit'], ['Vehicles', 'transport-vehicles', 'summit'], ['Vehicle Assignments', 'transport-assignments', 'summit'],
      ['Hostel', 'hostel', 'summit'], ['Hostel Rooms', 'hostel-rooms', 'summit'], ['Room Allocations', 'hostel-allocations', 'summit'],
    ],
  },
  { label: 'AI Tools', items: [['AI Assistant', 'ai-assistant'], ['At-risk Students', 'at-risk']] },
  { label: 'School Management', items: [['School Branding', 'branding'], ['Users & Roles', 'users-roles'], ['Data Import', 'csv-import'], ['Data Export', 'data-export'], ['Subscription', 'subscriptions'], ['Audit Log', 'audit-log'], ['Live Lessons', 'live-lessons']] },
]

const LEADERSHIP_MENU = ADMIN_MENU.map(g => ({ ...g })).map(g =>
  g.label === 'School Management'
    ? { ...g, items: [['Users & Roles', 'users-roles']] }
    : g
)

const menus = {
  super_admin: [{ label: 'Platform', items: [['Platform Analytics', 'analytics'], ['Schools', 'schools'], ['Users', 'users'], ['Onboarding Approvals', 'approvals'], ['Demo Leads', 'demo-leads'], ['Subscriptions', 'subscriptions'], ['Audit Log', 'audit-log'], ['Data Export', 'data-export']] }],
  group_owner: [{ label: 'Group', items: [['Dashboard', 'dashboard'], ['Branches', 'groups'], ['Announcements', 'announcements'], ['Messages', 'messages']] }],
  school_admin: ADMIN_MENU,
  principal: LEADERSHIP_MENU,
  vice_principal: LEADERSHIP_MENU,
  admissions_officer: [
    { label: 'Overview', items: [['Dashboard', 'dashboard']] },
    { label: 'Admissions', items: [['Applications', 'applications'], ['All Students', 'students'], ['Guardians', 'guardians'], ['Data Import', 'csv-import']] },
    { label: 'Academics', items: [['Classes & Arms', 'classes'], ['Sections', 'sections'], ['Timetable', 'timetable']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  teacher: [
    { label: 'Teaching', items: [['Dashboard', 'dashboard'], ['Attendance', 'attendance'], ['Results & Grades', 'grades'], ['Timetable', 'timetable'], ['Assignments', 'assignments'], ['Report Cards', 'report-cards'], ['AI Assistant', 'ai-assistant'], ['At-risk Students', 'at-risk']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Notices', 'notices'], ['Messages', 'messages']] },
  ],
  form_teacher: [
    { label: 'Teaching', items: [['Dashboard', 'dashboard'], ['Attendance', 'attendance'], ['Results & Grades', 'grades'], ['Timetable', 'timetable'], ['Assignments', 'assignments'], ['Report Cards', 'report-cards'], ['Students', 'students'], ['AI Assistant', 'ai-assistant'], ['At-risk Students', 'at-risk']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Notices', 'notices'], ['Messages', 'messages']] },
  ],
  staff: [
    { label: 'Teaching', items: [['Dashboard', 'dashboard'], ['Attendance', 'attendance'], ['Results & Grades', 'grades'], ['Timetable', 'timetable'], ['Assignments', 'assignments']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  exam_officer: [
    { label: 'Examinations', items: [['Dashboard', 'dashboard'], ['Results & Grades', 'grades'], ['Report Cards', 'report-cards'], ['Grading Schemes', 'grading-schemes'], ['Timetable', 'timetable']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  hr_admin: [
    { label: 'People', items: [['Dashboard', 'dashboard'], ['All Staff', 'staff'], ['Users & Roles', 'users-roles']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  librarian: [
    { label: 'Library', items: [['Dashboard', 'dashboard'], ['Library', 'library'], ['Borrow Records', 'library-borrows']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  accountant: [
    { label: 'Fees & Finance', items: [['Dashboard', 'dashboard'], ['Finance Overview', 'fees'], ['Fee Categories', 'fee-categories'], ['Fee Structures', 'fee-structures'], ['Invoices', 'invoices'], ['Payments', 'payments'], ['Expenses', 'expenses']] },
    { label: 'Communication', items: [['Announcements', 'announcements'], ['Messages', 'messages']] },
  ],
  parent: [{ label: 'Parent Portal', items: [['My Children', 'children'], ['Attendance', 'attendance'], ['Results', 'grades'], ['Report Cards', 'report-cards'], ['Timetable', 'timetable'], ['Assignments', 'assignments'], ['Invoices & Receipts', 'invoices'], ['Announcements', 'announcements'], ['Messages', 'messages']] }],
  student: [{ label: 'Student Portal', items: [['My Dashboard', 'dashboard'], ['Attendance', 'attendance'], ['Results', 'grades'], ['Report Cards', 'report-cards'], ['Timetable', 'timetable'], ['Assignments', 'assignments'], ['Announcements', 'announcements'], ['Messages', 'messages']] }],
  guest: [{ label: 'Read-only Demo', items: [['Dashboard', 'dashboard'], ['Students', 'students'], ['Classes', 'classes'], ['Results', 'grades']] }],
}

export function roleHome(role) {
  const groups = menus[role] || []
  return groups.length ? groups[0].items[0][1] : 'unauthorized'
}

/** Catches page render errors so a broken view shows a message instead of a white screen. */
class PageErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error) { return { error } }
  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey) this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="panel" style={{ maxWidth: 560, margin: '40px auto', textAlign: 'center' }}>
        <h3 style={{ marginBottom: 8 }}>This page hit an error</h3>
        <p className="muted" style={{ wordBreak: 'break-word' }}>{String(this.state.error.message || this.state.error)}</p>
        <button className="primary" style={{ marginTop: 12 }}
          onClick={() => { this.setState({ error: null }); window.location.assign('/') }}>
          Back to dashboard
        </button>
      </div>
    )
  }
}

export default function Shell() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [openGroup, setOpenGroup] = useState(null)
  const [unread, setUnread] = useState(0)
  const location = useLocation()
  const navigate = useNavigate()

  const role = user.role || ''
  const tier = (user.branding?.tier || user.tier || 'sprout').toLowerCase()
  const enabledModules = user.branding?.modules || []
  const groups = useMemo(() =>
    (menus[role] || [])
      .map(group => ({
        ...group,
        items: group.items.filter(item =>
          // Tier gate — unless the module was explicitly granted to this school
          // (e.g. an extra module approved during onboarding review).
          (!item[2] || tierRank[tier] >= tierRank[item[2]]
              || enabledModules.includes(item[1]))
          && (!enabledModules.length
              || enabledModules.includes(item[1])
              || ['dashboard', 'messages', 'announcements'].includes(item[1]))
        ),
      }))
      .filter(group => group.items.length),
    [role, tier, enabledModules])
  const paths = groups.flatMap(group => group.items.map(item => item[1]))
  const home = paths[0] || 'unauthorized'
  const current = location.pathname.split('/').filter(Boolean)[0]

  useEffect(() => {
    if (current && current !== home && !paths.includes(current) && current !== 'unauthorized') {
      navigate(`/${home}`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, home, navigate])

  // Auto sign-out — idle timeout + absolute session cap (skipped/extended
  // when the user chose "Keep me signed in" at login).
  const logoutRef = useRef(logout)
  logoutRef.current = logout
  useEffect(() => {
    if (!user) return
    const stay = localStorage.getItem('tabsforge_stay') === '1'
    const loginAt = Number(localStorage.getItem('tabsforge_login_at') || Date.now())
    let lastActivity = Date.now()
    const markActive = () => { lastActivity = Date.now() }
    const expire = reason => {
      logoutRef.current()
      window.location.assign(`/login?reason=${reason}`)
    }
    const events = ['pointerdown', 'keydown', 'touchstart']
    events.forEach(e => window.addEventListener(e, markActive, { passive: true }))
    const timer = setInterval(() => {
      const now = Date.now()
      if (now - loginAt > (stay ? STAY_LIMIT_MS : ABSOLUTE_LIMIT_MS)) return expire('expired')
      if (!stay && now - lastActivity > IDLE_LIMIT_MS) expire('idle')
    }, 15000)
    return () => {
      events.forEach(e => window.removeEventListener(e, markActive))
      clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id])

  // Mobile drawer: close on navigation, Escape, or tap outside; lock scroll.
  useEffect(() => { setOpen(false) }, [location.pathname])
  useEffect(() => {
    if (!open) return
    const onKey = e => { if (e.key === 'Escape') setOpen(false) }
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Accordion nav — keep the group containing the active route expanded.
  useEffect(() => {
    const active = groups.find(group => group.items.some(item => item[1] === current))
    if (active) setOpenGroup(active.label)
  }, [current, groups])

  // Unread messaging badge — initial fetch + live WebSocket bumps.
  useEffect(() => {
    if (role === 'super_admin') return
    get('/conversations/')
      .then(d => setUnread((d.results || d).reduce((n, c) => n + (c.my_unread || 0), 0)))
      .catch(() => {})
    let ws
    try {
      ws = new WebSocket(chatSocketUrl())
      ws.onmessage = e => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'chat.notify' && data.message?.sender !== user.id) {
            setUnread(n => n + 1)
          }
        } catch {}
      }
    } catch {}
    return () => { try { ws && ws.close() } catch {} }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const branding = user.branding
  const schoolName = branding?.name || 'TabsForge'
  const brandStyle = {
    '--school-primary': branding?.primary_color || 'var(--accent)',
    '--school-secondary': branding?.secondary_color || 'var(--accent-2)',
  }

  return (
    <div className="app-shell" style={brandStyle}>
      <aside className={open ? 'sidebar open' : 'sidebar'}>
        <button type="button" className="brand brand-btn" title="Go to your dashboard"
          onClick={() => navigate(`/${home}`)}>
          {branding?.logo
            ? <img className="school-logo" src={branding.logo} alt={schoolName} />
            : <BrandMark />}
          <span>{branding ? schoolName : 'TabsForge'}</span>
        </button>
        <button type="button" className="school-switch school-btn" title="Go to your dashboard"
          onClick={() => navigate(`/${home}`)}>
          <span className="school-avatar">
            {branding?.logo
              ? <img src={branding.logo} alt="" />
              : schoolName.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <strong>{schoolName}</strong>
            <small>{title(tier)} plan · {roleLabel(role)}</small>
          </div>
        </button>
        <nav>
          {groups.map(group => {
            const expanded = openGroup === group.label
            return (
              <div className={expanded ? 'nav-group expanded' : 'nav-group'} key={group.label}>
                <button type="button" className="nav-group-head"
                  aria-expanded={expanded}
                  onClick={() => setOpenGroup(expanded ? null : group.label)}>
                  <small>{group.label}</small>
                  <span className="chev">▾</span>
                </button>
                {expanded && (
                  <div className="nav-items">
                    {group.items.map(([label, path]) => (
                      <NavLink key={path} onClick={() => setOpen(false)} to={`/${path}`}>
                        <span className="nav-dot" />{label}
                        {path === 'messages' && unread > 0 && <span className="nav-badge">{unread}</span>}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </nav>
        <div className="sidebar-foot">
          {role === 'super_admin' && <button onClick={() => navigate('/onboarding')}>＋ Add school</button>}
          {branding
            ? <small className="watermark"><BrandMark small /> Powered by TabsForge</small>
            : <small>TabsForge OS · v1.0</small>}
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <div className="workspace">
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen(!open)}
            aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open}>☰</button>
          <div>
            <span className="crumb">Workspace /</span>{' '}
            <strong>{title(location.pathname.split('/').pop() || home)}</strong>
          </div>
          <div className="top-actions">
            {role === 'super_admin' && <SchoolCtxPicker />}
            <UserMenu user={user} role={role} />
          </div>
        </header>
        <main className="content">
          <PageErrorBoundary resetKey={location.pathname}>
          <Routes>
            <Route index element={<Navigate to={`/${home}`} replace />} />
            <Route path="unauthorized" element={<div className="alert">This account has no assigned workspace permissions. Contact a platform administrator.</div>} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="analytics" element={<Dashboard analytics />} />
            <Route path="attendance" element={<Attendance />} />
            <Route path="grades" element={<Gradebook />} />
            <Route path="report-cards" element={<Gradebook reportCards />} />
            <Route path="timetable" element={<Timetable />} />
            <Route path="fees" element={<Fees />} />
            <Route path="announcements" element={<Announcements />} />
            <Route path="branding" element={<Branding />} />
            <Route path="csv-import" element={<CsvImport />} />
            <Route path="users-roles" element={<RoleManager />} />
            <Route path="schools" element={<SchoolsAdmin />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="demo-leads" element={<DemoLeads />} />
            {role === 'super_admin' && <Route path="users" element={<PlatformUsers />} />}
            <Route path="rollover" element={<Rollover />} />
            <Route path="audit-log" element={<AuditLog />} />
            <Route path="data-export" element={<DataExport />} />
            <Route path="messages" element={<Messages onRead={() => setUnread(0)} />} />
            <Route path="ai-assistant" element={<AiAssistant />} />
            <Route path="at-risk" element={<AtRisk />} />
            <Route path="*" element={<ModulePage />} />
          </Routes>
          </PageErrorBoundary>
        </main>
      </div>
    </div>
  )
}

/** Topbar user menu: profile editor, notifications, new message, sign out. */
/** Platform-admin school-context switcher — scopes every API request. */
function SchoolCtxPicker() {
  const [schools, setSchools] = useState([])
  const [ctx, setCtx] = useState(getSchoolCtx())
  useEffect(() => {
    get('/schools/?page_size=200').then(d => setSchools(d.results || d)).catch(() => {})
  }, [])
  const change = e => {
    setCtx(e.target.value)
    setSchoolCtx(e.target.value)
    window.location.reload()
  }
  return (
    <label className="ctx-picker" title="Scope all pages to one school">
      <small>School</small>
      <select value={ctx} onChange={change}>
        <option value="">All schools</option>
        {schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
    </label>
  )
}

function UserMenu({ user, role }) {
  const { logout, refresh } = useAuth()
  const navigate = useNavigate()
  const ref = useRef()
  const [open, setOpen] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showTotp, setShowTotp] = useState(false)
  const [showPw, setShowPw] = useState(false)
  const [showNotifs, setShowNotifs] = useState(false)
  const [notifs, setNotifs] = useState([])
  const [unreadN, setUnreadN] = useState(0)
  const [form, setForm] = useState({
    first_name: user.first_name || '', last_name: user.last_name || '',
    phone: user.phone || '', whatsapp_number: user.whatsapp_number || '',
    notification_channel: user.notification_channel || 'email',
  })
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const loadNotifs = () => {
    get('/notifications/?page_size=20').then(d => setNotifs(d.results || d)).catch(() => setNotifs([]))
    get('/notifications/unread-count/').then(d => setUnreadN(d.unread_count || 0)).catch(() => {})
  }
  useEffect(loadNotifs, [])

  const markRead = id =>
    post(`/notifications/${id}/mark-read/`, {})
      .then(() => {
        setNotifs(notifs.map(n => n.id === id ? { ...n, is_read: true } : n))
        setUnreadN(n => Math.max(0, n - 1))
      })
      .catch(() => {})

  const saveProfile = async e => {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      await patch('/auth/me/', form)
      await refresh()
      setMsg({ kind: 'success', text: 'Profile updated.' })
    } catch (err) {
      setMsg({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const item = (label, fn, badge) => (
    <button className="menu-item" onClick={() => { setOpen(false); fn() }}>
      {label}{badge > 0 && <span className="nav-badge">{badge}</span>}
    </button>
  )

  return (
    <div className="user-menu" ref={ref}>
      <button className="profile" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <span className="avatar">{(user.name || user.email || 'U').slice(0, 2).toUpperCase()}</span>
        <div>
          <strong>{user.name || user.email || 'User'}</strong>
          <small>{roleLabel(role)}</small>
        </div>
        <span className="chev">▾</span>
      </button>
      {open && (
        <div className="menu-pop" role="menu">
          {item('My profile', () => setShowProfile(true))}
          {item('Change password', () => setShowPw(true))}
          {item('Authenticator app', () => setShowTotp(true))}
          {item('Notifications', () => { setShowNotifs(true); loadNotifs() }, unreadN)}
          {item('New message', () => navigate('/messages?compose=1'))}
          <button className="menu-item danger" onClick={logout}>Sign out</button>
        </div>
      )}

      {showProfile && (
        <Modal title="My profile" close={() => { setShowProfile(false); setMsg(null) }}>
          <form className="stack" onSubmit={saveProfile}>
            {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
            <label>First name
              <input value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
            </label>
            <label>Last name
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
            </label>
            <label>Phone
              <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </label>
            <label>WhatsApp number
              <input value={form.whatsapp_number} placeholder="+234…"
                onChange={e => setForm({ ...form, whatsapp_number: e.target.value })} />
            </label>
            <label>Preferred notification channel
              <select value={form.notification_channel}
                onChange={e => setForm({ ...form, notification_channel: e.target.value })}>
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
            </label>
            <p className="muted" style={{ fontSize: 12 }}>Signed in as {user.email} · {roleLabel(role)}</p>
            <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button>
          </form>
        </Modal>
      )}

      {showNotifs && (
        <Modal title="Notifications" close={() => setShowNotifs(false)} wide>
          {notifs.length === 0 && <p className="muted">No notifications yet.</p>}
          <div className="notif-list">
            {notifs.map(n => (
              <div key={n.id} className={n.is_read ? 'notif' : 'notif unread'}>
                <div>
                  <strong>{n.title}</strong>
                  <p>{n.message}</p>
                  <small>{n.sender_name || 'System'} · {new Date(n.created_at).toLocaleString()}</small>
                </div>
                {!n.is_read && <button className="ghost sm" onClick={() => markRead(n.id)}>Mark read</button>}
              </div>
            ))}
          </div>
        </Modal>
      )}

      {showPw && (
        <ChangePasswordModal close={() => setShowPw(false)} />
      )}

      {showTotp && (
        <TotpModal user={user} refresh={refresh} close={() => setShowTotp(false)} />
      )}
    </div>
  )
}

function ChangePasswordModal({ close }) {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' })
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setMsg(null)
    if (form.new_password !== form.confirm) {
      setMsg({ kind: 'error', text: 'New passwords do not match.' })
      return
    }
    setBusy(true)
    try {
      const d = await post('/auth/change-password/', {
        current_password: form.current_password,
        new_password: form.new_password,
      })
      if (d.token) localStorage.setItem('tabsforge_token', d.token)
      setDone(true)
      setMsg({ kind: 'success', text: 'Password updated — other sessions have been signed out.' })
    } catch (err) {
      setMsg({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Change password" close={close}>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {done ? (
        <div className="stack">
          <button className="primary" onClick={close}>Done</button>
        </div>
      ) : (
        <form className="stack" onSubmit={submit}>
          <label>Current password
            <input autoFocus type="password" required value={form.current_password}
              onChange={e => setForm({ ...form, current_password: e.target.value })} />
          </label>
          <label>New password
            <input type="password" required value={form.new_password}
              onChange={e => setForm({ ...form, new_password: e.target.value })} />
          </label>
          <label>Confirm new password
            <input type="password" required value={form.confirm}
              onChange={e => setForm({ ...form, confirm: e.target.value })} />
          </label>
          <button className="primary" disabled={busy}>{busy ? 'Updating…' : 'Update password'}</button>
        </form>
      )}
    </Modal>
  )
}

function TotpModal({ user, refresh, close }) {
  const [setup, setSetup] = useState(null) // { secret, otpauth_url }
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const canvasRef = useRef()

  const begin = async () => {
    setBusy(true)
    setMsg(null)
    try {
      const data = await post('/auth/totp/setup/', {})
      setSetup(data)
    } catch (err) {
      setMsg({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (setup?.otpauth_url && canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, setup.otpauth_url, { width: 200, margin: 1 })
    }
  }, [setup])

  const submit = async e => {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      const url = user.totp_enabled ? '/auth/totp/disable/' : '/auth/totp/enable/'
      await post(url, { code })
      await refresh()
      setMsg({ kind: 'success', text: user.totp_enabled ? 'Authenticator removed.' : 'Authenticator app enabled — you can now use it for password resets.' })
      setSetup(null)
      setCode('')
    } catch (err) {
      setMsg({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Authenticator app" close={close}>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {user.totp_enabled ? (
        <form className="stack" onSubmit={submit}>
          <p className="muted">An authenticator app is linked to your account — you can use it to reset your password. Enter a current code to remove it.</p>
          <label>Current authenticator code
            <input inputMode="numeric" maxLength={6} value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, ''))} placeholder="123456" />
          </label>
          <button className="primary" disabled={busy || code.length !== 6}>
            {busy ? 'Removing…' : 'Remove authenticator'}
          </button>
        </form>
      ) : setup ? (
        <form className="stack" onSubmit={submit}>
          <p className="muted">Scan with Google Authenticator, Authy, or any TOTP app — then enter the 6-digit code it shows.</p>
          <div className="qr-box"><canvas ref={canvasRef} /></div>
          <details>
            <summary className="muted">Can't scan? Enter this key manually</summary>
            <code className="totp-secret">{setup.secret}</code>
          </details>
          <label>6-digit code
            <input autoFocus inputMode="numeric" maxLength={6} value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, ''))} placeholder="123456" />
          </label>
          <button className="primary" disabled={busy || code.length !== 6}>
            {busy ? 'Verifying…' : 'Enable authenticator'}
          </button>
        </form>
      ) : (
        <div className="stack">
          <p className="muted">
            Link an authenticator app (Google Authenticator, Authy…) to your account.
            Once enabled you can reset a forgotten password with an app code — no email needed.
          </p>
          <button className="primary" onClick={begin} disabled={busy}>
            {busy ? 'Preparing…' : 'Set up authenticator'}
          </button>
        </div>
      )}
    </Modal>
  )
}
