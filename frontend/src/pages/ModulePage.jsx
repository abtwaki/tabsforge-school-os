import React, { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { get, post, patch, remove } from '../api'
import { useAuth, title, roleLabel } from '../auth'
import { PageHead, Modal, Empty, Alert, useModule, money, fmtDate, statusBadge } from '../ui'
import SubmissionsModal from './SubmissionsModal'

/* Module specs: columns for the table, optional create-form fields.
 * field spec: { f, label, required, type: 'text'|'number'|'date'|'select'|'fk'|'bool'|'textarea'|'password',
 *               options: [[v,l]] | source: 'endpoint', labelKey }
 */
const NG_STATES = [
  'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno',
  'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT — Abuja', 'Gombe',
  'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi', 'Kwara', 'Lagos',
  'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto',
  'Taraba', 'Yobe', 'Zamfara',
].map(s => [s, s])

const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(s => [s, s])
const GENOTYPES = ['AA', 'AS', 'SS', 'AC', 'SC'].map(s => [s, s])
const RELIGIONS = [['christianity', 'Christianity'], ['islam', 'Islam'], ['traditional', 'Traditional'], ['other', 'Other']]

const moduleConfig = {
  applications: {
    columns: ['Applicant', 'Class', 'Session', 'Guardian', 'Status', 'Applied'],
    fields: ['applicant_full_name', 'class_name', 'session_name', 'guardian_name', 'status', 'created_at'],
  },
  students: {
    columns: ['Admission no.', 'Student', 'Class', 'Gender'],
    fields: ['admission_number', 'name', 'class_name', 'gender'],
    create: [
      { legend: 'Pupil details' },
      { f: 'first_name', required: true }, { f: 'last_name', required: true },
      { f: 'admission_number', required: true },
      { f: 'gender', type: 'select', options: [['male', 'Male'], ['female', 'Female'], ['other', 'Other']] },
      { f: 'date_of_birth', type: 'date' }, { f: 'address', type: 'textarea' },
      { legend: 'Biodata (Nigerian records)' },
      { f: 'state_of_origin', label: 'State of origin', type: 'select', options: NG_STATES },
      { f: 'lga', label: 'Local Government Area' },
      { f: 'nationality', label: 'Nationality', default: 'Nigerian' },
      { f: 'religion', label: 'Religion', type: 'select', options: RELIGIONS },
      { f: 'nin', label: 'NIN (National ID no.)' },
      { f: 'blood_group', label: 'Blood group', type: 'select', options: BLOOD_GROUPS },
      { f: 'genotype', label: 'Genotype', type: 'select', options: GENOTYPES },
      { f: 'previous_school', label: 'Previous school' },
      { f: 'medical_conditions', label: 'Allergies / medical conditions', type: 'textarea' },
      { legend: 'Class assignment' },
      { f: 'section', type: 'fk', source: 'sections', label: 'Class / Section', required: true, labelKey: 'display_name' },
      { legend: 'Parent / guardian — pick an existing one or fill in new details' },
      { f: 'guardian', type: 'fk', source: 'guardians', label: 'Existing guardian (optional)', labelKey: 'full_name' },
      { f: 'guardian_first_name', label: 'Guardian first name' },
      { f: 'guardian_last_name', label: 'Guardian last name' },
      { f: 'guardian_phone', label: 'Guardian phone' },
      { f: 'guardian_email', label: 'Guardian email' },
      { f: 'guardian_relationship', label: 'Relationship to pupil', type: 'select', options: [['father', 'Father'], ['mother', 'Mother'], ['guardian', 'Guardian'], ['other', 'Other']] },
    ],
  },
  children: {
    endpoint: 'students',
    title: 'My children',
    columns: ['Admission no.', 'Student', 'Class', 'Gender'],
    fields: ['admission_number', 'name', 'class_name', 'gender'],
  },
  guardians: {
    columns: ['Guardian', 'Relationship', 'Phone', 'Email'],
    fields: ['first_name', 'relationship', 'phone', 'email'],
    create: [
      { f: 'first_name', required: true }, { f: 'last_name', required: true },
      { f: 'relationship', type: 'select', options: [['father', 'Father'], ['mother', 'Mother'], ['guardian', 'Guardian'], ['other', 'Other']] },
      { f: 'phone' }, { f: 'email' }, { f: 'address', type: 'textarea' },
      { f: 'student', type: 'fk', source: 'students', label: 'Link to student', labelKey: 'name' },
    ],
  },
  classes: {
    columns: ['Class', 'Code'],
    fields: ['name', 'code'],
    create: [{ f: 'name', required: true }, { f: 'code' }],
  },
  sections: {
    columns: ['Section', 'Class', 'Room', 'Capacity'],
    fields: ['name', 'school_class', 'room', 'capacity'],
    create: [
      { f: 'school_class', type: 'fk', source: 'classes', label: 'Class', required: true },
      { f: 'name', required: true }, { f: 'room' }, { f: 'capacity', type: 'number' },
    ],
  },
  subjects: {
    columns: ['Subject', 'Code'],
    fields: ['name', 'code'],
    create: [{ f: 'name', required: true }, { f: 'code' }, { f: 'description', type: 'textarea' }],
  },
  'academic-sessions': {
    columns: ['Session', 'Starts', 'Ends', 'Current'],
    fields: ['name', 'start_date', 'end_date', 'is_current'],
    create: [
      { f: 'name', required: true }, { f: 'start_date', type: 'date', required: true },
      { f: 'end_date', type: 'date', required: true }, { f: 'is_current', type: 'bool' },
    ],
  },
  terms: {
    columns: ['Term', 'Session', 'Starts', 'Ends', 'Current'],
    fields: ['name', 'session', 'start_date', 'end_date', 'is_current'],
    create: [
      { f: 'session', type: 'fk', source: 'academic-sessions', label: 'Session', required: true },
      { f: 'name', required: true }, { f: 'start_date', type: 'date', required: true },
      { f: 'end_date', type: 'date', required: true }, { f: 'is_current', type: 'bool' },
    ],
  },
  'grading-schemes': {
    columns: ['Scheme', 'CA1 %', 'CA2 %', 'Exam %', 'Default'],
    fields: ['name', 'ca1_weight', 'ca2_weight', 'exam_weight', 'is_default'],
    create: [
      { f: 'name', required: true },
      { f: 'ca1_weight', type: 'number', default: 20 }, { f: 'ca2_weight', type: 'number', default: 20 },
      { f: 'exam_weight', type: 'number', default: 60 }, { f: 'is_default', type: 'bool' },
    ],
  },
  'fee-categories': {
    columns: ['Category', 'Mandatory'],
    fields: ['name', 'is_mandatory'],
    create: [{ f: 'name', required: true }, { f: 'description', type: 'textarea' }, { f: 'is_mandatory', type: 'bool', default: true }],
  },
  'fee-structures': {
    columns: ['Structure', 'Category', 'Class', 'Term', 'Amount'],
    fields: ['name', 'category', 'school_class', 'term', 'amount'],
    create: [
      { f: 'category', type: 'fk', source: 'fee-categories', label: 'Category', required: true },
      { f: 'name', required: true },
      { f: 'school_class', type: 'fk', source: 'classes', label: 'Class', required: true },
      { f: 'term', type: 'fk', source: 'terms', label: 'Term', required: true },
      { f: 'amount', type: 'number', required: true }, { f: 'due_date', type: 'date' },
    ],
  },
  invoices: {
    columns: ['Invoice', 'Student', 'Term', 'Total', 'Paid', 'Balance', 'Status'],
    fields: ['invoice_number', 'student_name', 'term_name', 'total_amount', 'amount_paid', 'balance', 'status'],
    money: ['total_amount', 'amount_paid', 'balance'],
  },
  payments: {
    columns: ['Receipt', 'Invoice', 'Method', 'Date', 'Amount'],
    fields: ['receipt_number', 'invoice_number', 'method', 'paid_at', 'amount'],
    money: ['amount'],
  },
  expenses: {
    columns: ['Title', 'Category', 'Date', 'Amount'],
    fields: ['title', 'category_display', 'expense_date', 'amount'],
    money: ['amount'],
    create: [
      { f: 'title', required: true },
      { f: 'category', type: 'select', options: ['salaries', 'utilities', 'maintenance', 'supplies', 'transport', 'catering', 'rent', 'insurance', 'events', 'other'].map(c => [c, title(c)]) },
      { f: 'amount', type: 'number', required: true }, { f: 'expense_date', type: 'date', required: true },
      { f: 'description', type: 'textarea' },
    ],
  },
  staff: {
    columns: ['Staff ID', 'Name', 'Role', 'Department'],
    fields: ['employee_id', 'user_name', 'user_role', 'department'],
    create: [
      { legend: 'Login account — link an existing user or create one below' },
      { f: 'user', type: 'fk', source: 'users', label: 'Existing user account', labelKey: 'email' },
      { f: 'email', label: 'New account email', type: 'email' },
      { f: 'first_name', label: 'Account first name' },
      { f: 'last_name', label: 'Account last name' },
      { f: 'password', type: 'password', label: 'Temporary password' },
      { legend: 'Staff details' },
      { f: 'employee_id', required: true }, { f: 'designation' }, { f: 'department' },
      { f: 'employment_type', type: 'select', options: [['full_time', 'Full time'], ['part_time', 'Part time'], ['contract', 'Contract']] },
    ],
  },
  library: {
    endpoint: 'library/books',
    columns: ['Book', 'Author', 'ISBN', 'Available'],
    fields: ['title', 'author', 'isbn', 'copies_available'],
    create: [
      { f: 'title', required: true }, { f: 'author' }, { f: 'isbn' }, { f: 'publisher' },
      { f: 'published_year', type: 'number' }, { f: 'copies_total', type: 'number', required: true },
      { f: 'category' },
    ],
  },
  'library-borrows': {
    endpoint: 'library/borrows',
    columns: ['Book', 'Student', 'Borrowed', 'Due', 'Status'],
    fields: ['book', 'student', 'borrowed_at', 'due_date', 'status'],
    create: [
      { f: 'book', type: 'fk', source: 'library/books', label: 'Book', required: true },
      { f: 'student', type: 'fk', source: 'students', label: 'Student', required: true },
      { f: 'due_date', type: 'date', required: true },
    ],
  },
  transport: {
    endpoint: 'transport/routes',
    columns: ['Route', 'From', 'To', 'Distance (km)'],
    fields: ['name', 'start_location', 'end_location', 'distance_km'],
    create: [
      { f: 'name', required: true }, { f: 'start_location' }, { f: 'end_location' },
      { f: 'stops', type: 'textarea' }, { f: 'distance_km', type: 'number' },
    ],
  },
  hostel: {
    endpoint: 'hostels',
    columns: ['Hostel', 'Warden', 'Phone'],
    fields: ['name', 'warden_name', 'warden_phone'],
    create: [{ f: 'name', required: true }, { f: 'address', type: 'textarea' }, { f: 'warden_name' }, { f: 'warden_phone' }],
  },
  schools: {
    columns: ['School', 'Subdomain', 'Tier', 'Status'],
    fields: ['name', 'subdomain', 'tier', 'status'],
  },
  users: {
    columns: ['User', 'Email', 'Role', 'School', 'Active'],
    fields: ['name', 'email', 'role', 'school_name', 'is_active'],
  },
  approvals: {
    endpoint: 'onboarding/approvals',
    columns: ['School', 'Requested', 'Tier', 'Status'],
    fields: ['name', 'created_at', 'tier', 'status'],
  },
  'demo-leads': {
    endpoint: 'marketing/demo-leads',
    columns: ['School', 'Contact', 'Email', 'Phone', 'Students'],
    fields: ['school_name', 'contact_name', 'email', 'phone', 'student_count_range'],
  },
  groups: {
    endpoint: 'groups',
    columns: ['Group', 'Billing', 'Branches', 'Active'],
    fields: ['name', 'billing_mode', 'branches_count', 'is_active'],
  },
  'my-classes': {
    endpoint: 'class-subjects',
    columns: ['Class', 'Subject', 'Teacher'],
    fields: ['school_class', 'subject', 'teacher'],
  },
  'class-subjects': {
    columns: ['Class', 'Subject', 'Teacher'],
    fields: ['school_class', 'subject', 'teacher'],
    create: [
      { f: 'school_class', type: 'fk', source: 'classes', label: 'Class', required: true },
      { f: 'subject', type: 'fk', source: 'subjects', label: 'Subject', required: true },
      { f: 'teacher', type: 'fk', source: 'users', label: 'Teacher' },
    ],
  },
  assignments: {
    columns: ['Assignment', 'Class', 'Subject', 'Due', 'Max pts'],
    fields: ['title', 'class_name', 'subject_name', 'due_date', 'max_points'],
    create: [
      { f: 'title', required: true },
      { f: 'school_class', type: 'fk', source: 'classes', label: 'Class', required: true },
      { f: 'subject', type: 'fk', source: 'subjects', label: 'Subject', required: true },
      { f: 'term', type: 'fk', source: 'terms', label: 'Term', required: true },
      { f: 'type', type: 'select', options: [['homework', 'Homework'], ['classwork', 'Classwork'], ['project', 'Project'], ['test', 'Test']] },
      { f: 'due_date', type: 'date', required: true }, { f: 'max_points', type: 'number', default: 20 },
      { f: 'description', type: 'textarea' }, { f: 'is_published', type: 'bool', default: true },
    ],
  },
  notices: {
    columns: ['Title', 'Priority', 'Author', 'Published'],
    fields: ['title', 'priority', 'author_name', 'created_at'],
    create: [
      { f: 'title', required: true },
      { f: 'content', type: 'textarea', required: true },
      { f: 'priority', type: 'select', options: [['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['urgent', 'Urgent']] },
    ],
  },
  enrollments: {
    columns: ['Student', 'Class', 'Section', 'Session', 'Term', 'Status'],
    fields: ['student_name', 'class_name', 'section_name', 'session_name', 'term_name', 'status'],
    create: [
      { f: 'student', type: 'fk', source: 'students', label: 'Student', required: true, labelKey: 'name' },
      { f: 'section', type: 'fk', source: 'sections', label: 'Class / section', required: true, labelKey: 'display_name' },
      { f: 'session', type: 'fk', source: 'academic-sessions', label: 'Session', required: true },
      { f: 'term', type: 'fk', source: 'terms', label: 'Term', required: true },
      { f: 'roll_number' },
      { f: 'status', type: 'select', options: [['active', 'Active'], ['completed', 'Completed'], ['withdrawn', 'Withdrawn']] },
    ],
  },
  'transport-vehicles': {
    endpoint: 'transport/vehicles',
    columns: ['Registration', 'Make', 'Model', 'Capacity', 'Status'],
    fields: ['registration_number', 'make', 'model', 'capacity', 'status'],
    create: [
      { f: 'registration_number', required: true },
      { f: 'make' }, { f: 'model' }, { f: 'capacity', type: 'number' },
      { f: 'status', type: 'select', options: [['active', 'Active'], ['maintenance', 'Maintenance'], ['inactive', 'Inactive']] },
    ],
  },
  'transport-assignments': {
    endpoint: 'transport/assignments',
    columns: ['Vehicle', 'Route', 'Driver', 'Phone', 'Effective'],
    fields: ['vehicle_label', 'route_name', 'driver_name', 'driver_phone', 'effective_date'],
    create: [
      { f: 'vehicle', type: 'fk', source: 'transport/vehicles', label: 'Vehicle', required: true, labelKey: 'registration_number' },
      { f: 'route', type: 'fk', source: 'transport/routes', label: 'Route', required: true },
      { f: 'driver_name', label: 'Driver name' }, { f: 'driver_phone', label: 'Driver phone' },
      { f: 'effective_date', type: 'date', required: true }, { f: 'end_date', type: 'date' },
    ],
  },
  'hostel-rooms': {
    endpoint: 'hostel/rooms',
    columns: ['Room', 'Hostel', 'Capacity', 'Occupied', 'Vacancies'],
    fields: ['display_name', 'hostel_name', 'capacity', 'occupied', 'vacancies'],
    create: [
      { f: 'hostel', type: 'fk', source: 'hostels', label: 'Hostel', required: true },
      { f: 'room_number', required: true }, { f: 'capacity', type: 'number', required: true },
      { f: 'amenities', label: 'Amenities' },
    ],
  },
  'hostel-allocations': {
    endpoint: 'hostel/allocations',
    columns: ['Student', 'Room', 'Check-in', 'Check-out', 'Status'],
    fields: ['student_name', 'room_label', 'check_in', 'check_out', 'status'],
    create: [
      { f: 'student', type: 'fk', source: 'students', label: 'Student', required: true, labelKey: 'name' },
      { f: 'room', type: 'fk', source: 'hostel/rooms', label: 'Room', required: true, labelKey: 'display_name' },
      { f: 'check_in', type: 'date', required: true }, { f: 'check_out', type: 'date' },
      { f: 'status', type: 'select', options: [['active', 'Active'], ['checked_out', 'Checked out']] },
    ],
  },
  subscriptions: {
    columns: ['School', 'Tier', 'Cycle', 'Amount', 'Status', 'Ends'],
    fields: ['school_name', 'tier', 'billing_cycle', 'amount', 'status', 'ends_at'],
    money: ['amount'],
  },
  'live-lessons': {
    columns: ['Lesson', 'Class', 'Subject', 'Scheduled', 'Status'],
    fields: ['title', 'class_name', 'subject_name', 'scheduled_at', 'status'],
    create: [
      { f: 'title', required: true },
      { f: 'school_class', type: 'fk', source: 'classes', label: 'Class', required: true },
      { f: 'subject', type: 'fk', source: 'subjects', label: 'Subject', required: true },
      { f: 'scheduled_at', type: 'datetime', required: true },
      { f: 'duration_minutes', type: 'number', default: 45 },
      { f: 'description', type: 'textarea' },
    ],
  },
}

// Where to create each FK dependency — used to tell the user what to set up first.
const FK_MODULE_HINTS = {
  'academic-sessions': 'Academics → Academic Sessions',
  classes: 'Academics → Classes & Arms',
  sections: 'Academics → Sections',
  subjects: 'Academics → Subjects',
  terms: 'Academics → Terms',
  students: 'Students → All students',
  guardians: 'Students → Guardians',
  users: 'Administration → Users & roles',
  'fee-categories': 'Finance → Fee categories',
  'library/books': 'Library → Books',
}

function FkSelect({ spec, value, onChange, options }) {
  return (
    <select required={spec.required} value={value || ''} onChange={e => onChange(e.target.value)}>
      <option value="">Select…</option>
      {options.map(o => <option key={o.id} value={o.id}>{o[spec.labelKey || 'name'] || o.email || `#${o.id}`}</option>)}
    </select>
  )
}

export default function ModulePage() {
  const { user } = useAuth()
  const name = useLocation().pathname.split('/').filter(Boolean).pop()
  const config = moduleConfig[name] || { columns: ['Name', 'Details', 'Status'], fields: ['name', 'description', 'status'] }
  const endpoint = config.endpoint || name
  const [showArchived, setShowArchived] = useState(false)
  const [rows, setRows, loading, error, reload] = useModule(endpoint, showArchived ? '&archived=only' : '')
  const [show, setShow] = useState(false)
  const [editing, setEditing] = useState(null)
  const [query, setQuery] = useState('')
  const [form, setForm] = useState({})
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [fkOptions, setFkOptions] = useState({})
  const [detail, setDetail] = useState(null)
  const [grading, setGrading] = useState(null)
  const [submitting, setSubmitting] = useState(null)
  const canWrite = config.create && !['parent', 'student', 'guest'].includes(user.role) && !user.is_guest
  const isStudent = user.role === 'student'

  // Preload FK option lists.
  useEffect(() => {
    if (!config.create) return
    config.create.filter(f => f.type === 'fk').forEach(f => {
      get(`/${f.source}/?page_size=300`)
        .then(d => setFkOptions(o => ({ ...o, [f.source]: d.results || d })))
        .catch(() => {})
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name])

  const filtered = rows.filter(r => JSON.stringify(r).toLowerCase().includes(query.toLowerCase()))

  // Required FK fields whose source list has loaded but is empty — these block
  // saving, so name the missing setup step instead of letting the form fail.
  const missingFks = (config.create || [])
    .filter(f => f.type === 'fk' && f.required && fkOptions[f.source] && !fkOptions[f.source].length)

  const save = async e => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const body = {}
      config.create.forEach(f => {
        if (!f.f) return
        let v = form[f.f]
        if (v === undefined || v === '') {
          if (f.type === 'bool') v = false
          else if (f.default !== undefined) v = f.default
          else return
        }
        if (f.type === 'number' || f.type === 'fk') v = Number(v)
        if (f.type === 'datetime' && v && !v.endsWith('Z') && !v.includes('+')) v = `${v}:00`
        body[f.f] = v
      })
      if (name === 'students' && !editing && !body.guardian &&
          !body.guardian_first_name && !body.guardian_last_name &&
          !body.guardian_phone && !body.guardian_email) {
        setSaveError('Add parent/guardian details, or pick an existing guardian, so the pupil can be linked.')
        return
      }
      if (editing) {
        const row = await patch(`/${endpoint}/${editing.id}/`, body)
        setRows(rows.map(r => r.id === editing.id ? { ...r, ...row } : r))
        setMsg({ kind: 'success', text: 'Record updated.' })
      } else {
        const row = await post(`/${endpoint}/`, body)
        setRows([row, ...rows])
        setMsg({ kind: 'success', text: 'Record created.' })
      }
      setShow(false)
      setEditing(null)
      setForm({})
    } catch (e2) {
      setSaveError(e2.message)
    } finally {
      setSaving(false)
    }
  }

  const openEdit = row => {
    const init = {}
    config.create.forEach(f => {
      if (!f.f) return
      let v = row[f.f]
      if (v === undefined && row[`${f.f}_id`] !== undefined) v = row[`${f.f}_id`]
      if (f.type === 'datetime' && v) v = String(v).slice(0, 16)
      if (v !== undefined && v !== null) init[f.f] = v
    })
    setEditing(row)
    setForm(init)
    setSaveError('')
    setShow(true)
  }

  const archive = async row => {
    try {
      const { dependents } = await get(`/${endpoint}/${row.id}/dependents/`)
      const depList = Object.entries(dependents || {}).map(([k, n]) => `${n} ${k}`).join(', ')
      const warn = depList
        ? `This record is linked to ${depList}. Linked records keep working and everything can be restored later.`
        : 'Archived records can be restored anytime from the archived view.'
      if (!window.confirm(`Archive “${row.name || row.title || `#${row.id}`}”?\n\n${warn}`)) return
      const res = await remove(`/${endpoint}/${row.id}/`)
      setMsg({ kind: 'success', text: res.detail || 'Archived.' })
      reload()
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const payOnline = async row => {
    try {
      const res = await post('/payments/paystack/initialize/', { invoice_id: row.id })
      if (res.authorization_url) window.location.assign(res.authorization_url)
    } catch (e) {
      setMsg({ kind: 'error', text: e.message.includes('503') || e.message.toLowerCase().includes('configured')
        ? 'Online payments are not yet enabled for this school — pay via bank transfer or ask the bursar.'
        : e.message })
    }
  }

  const restore = async row => {
    try {
      await post(`/${endpoint}/${row.id}/restore/`, {})
      setMsg({ kind: 'success', text: 'Restored.' })
      reload()
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
  }

  const cell = (row, f, j) => {
    const v = row[f]
    if (config.money?.includes(f)) return money(v)
    if (typeof v === 'boolean') return v ? '✓' : '—'
    if (f.endsWith('_at') || f === 'date' || f === 'paid_at' || f === 'borrowed_at' || f === 'scheduled_at') return fmtDate(v)
    if (f === 'status' || f === 'role') return v ? statusBadge(v) : '—'
    return v ?? '—'
  }

  return (
    <>
      <PageHead
        title={config.title || title(name)}
        subtitle={`Manage ${title(config.title || name).toLowerCase()} — live records from your workspace.`}
        action={canWrite && (
          <button className="primary" onClick={() => setShow(true)}>＋ Add {title(name).replace(/s$/, '')}</button>
        )}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {error && <Alert kind="error">Could not load records: {error}</Alert>}
      <section className="panel table-panel">
        <div className="table-tools">
          <div className="search">⌕ <input value={query} onChange={e => setQuery(e.target.value)} placeholder={`Search ${title(name).toLowerCase()}…`} /></div>
          {canWrite && (
            <button className="secondary" onClick={() => setShowArchived(v => !v)}
              title={showArchived ? 'Back to active records' : 'View archived records — they can be restored'}>
              {showArchived ? '← Active records' : 'Archived'}
            </button>
          )}
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr>{config.columns.map(c => <th key={c}>{c}</th>)}<th /></tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={config.columns.length + 1}>Loading records…</td></tr>
              ) : !error && filtered.length ? (
                filtered.map((row, i) => (
                  <tr key={row.id || i} className={row.is_archived ? 'muted-row' : ''}
                    onClick={() => ['applications', 'students'].includes(name) && setDetail(row)}
                    style={['applications', 'students'].includes(name) ? { cursor: 'pointer' } : {}}>
                    {config.fields.map((f, j) => (
                      <td key={f}>{j === 0 ? <strong>{cell(row, f, j)}</strong> : cell(row, f, j)}</td>
                    ))}
                    <td>
                      <div className="row-actions" onClick={e => e.stopPropagation()}>
                      {name === 'assignments' && canWrite && !row.is_archived && (
                        <button className="ghost sm" onClick={() => setGrading(row)}
                          title="View and mark student submissions">Submissions</button>
                      )}
                      {name === 'assignments' && isStudent && (
                        <button className="ghost sm" onClick={() => setSubmitting(row)}
                          title="Submit your work for this assignment">Submit work</button>
                      )}
                      {name === 'invoices' && user.role === 'parent' && ['sent', 'partial', 'overdue'].includes(row.status) && (
                        <button className="ghost sm" onClick={() => payOnline(row)}
                          title="Pay the outstanding balance online via Paystack">Pay online</button>
                      )}
                      {canWrite && config.create && (
                        <>
                          {row.is_archived ? (
                            <button className="ghost sm" onClick={() => restore(row)}>Restore</button>
                          ) : (
                            <>
                              <button className="ghost sm" onClick={() => openEdit(row)}>Edit</button>
                              <button className="ghost sm danger" onClick={() => archive(row)}
                                title="Archive — linked records keep working, restore anytime">Archive</button>
                            </>
                          )}
                        </>
                      )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : !error ? (
                <tr><td colSpan={config.columns.length + 1}>
                  <Empty title={showArchived ? 'No archived records' : `No ${title(name).toLowerCase()} yet`}
                    hint={showArchived
                      ? 'Records you archive appear here — switch back with “← Active records”.'
                      : canWrite
                        ? `Use “＋ Add ${title(name).replace(/s$/, '')}” or click here to create the first record.`
                        : 'Records will appear here once they are created by staff.'}
                    onAdd={!showArchived && canWrite ? () => setShow(true) : undefined} />
                </td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      {show && canWrite && (
        <Modal title={`${editing ? 'Edit' : 'Add'} ${title(name).replace(/s$/, '')}`} close={() => { setShow(false); setEditing(null); setForm({}) }} wide>
          <form onSubmit={save} className="form-grid">
            {saveError && <div className="alert">{saveError}</div>}
            {!!missingFks.length && (
              <div className="alert">
                {missingFks.map(f => (
                  <div key={f.f}>
                    No {title(f.label || f.f).toLowerCase()} exists yet — create one first
                    {FK_MODULE_HINTS[f.source] ? ` (${FK_MODULE_HINTS[f.source]})` : ''}.
                  </div>
                ))}
              </div>
            )}
            {config.create.map(f => f.legend ? (
              <div key={`legend-${f.legend}`} className="form-legend">{f.legend}</div>
            ) : (
              <label key={f.f}>{f.label || title(f.f)}
                {f.type === 'fk' ? (
                  <FkSelect spec={f} value={form[f.f]} onChange={v => setForm({ ...form, [f.f]: v })} options={fkOptions[f.source] || []} />
                ) : f.type === 'select' ? (
                  <select required={f.required} value={form[f.f] ?? f.default ?? (f.required ? f.options[0][0] : '')} onChange={e => setForm({ ...form, [f.f]: e.target.value })}>
                    {!f.required && <option value="">—</option>}
                    {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                ) : f.type === 'bool' ? (
                  <select value={String(form[f.f] ?? f.default ?? false)} onChange={e => setForm({ ...form, [f.f]: e.target.value === 'true' })}>
                    <option value="true">Yes</option><option value="false">No</option>
                  </select>
                ) : f.type === 'textarea' ? (
                  <textarea rows="3" value={form[f.f] || ''} onChange={e => setForm({ ...form, [f.f]: e.target.value })} />
                ) : (
                  <input
                    type={f.type === 'datetime' ? 'datetime-local' : f.type || 'text'}
                    required={f.required}
                    value={form[f.f] ?? f.default ?? ''}
                    onChange={e => setForm({ ...form, [f.f]: e.target.value })}
                  />
                )}
              </label>
            ))}
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => { setShow(false); setEditing(null); setForm({}) }}>Cancel</button>
              <button className="primary" disabled={saving || !!missingFks.length}
                title={missingFks.length ? 'Create the missing record(s) listed above first' : ''}>
                {saving ? 'Saving…' : editing ? 'Save changes' : 'Save record'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {detail && name === 'applications' && (
        <Modal title={`Application — ${detail.applicant_full_name || `${detail.first_name} ${detail.last_name}`}`} close={() => setDetail(null)} wide>
          <div className="detail-grid">
            <div><small>Status</small><strong>{statusBadge(detail.status)}</strong></div>
            <div><small>Applying for</small><strong>{detail.class_name || '—'}</strong></div>
            <div><small>Session</small><strong>{detail.session_name || '—'}</strong></div>
            <div><small>Date of birth</small><strong>{detail.date_of_birth || '—'}</strong></div>
            <div><small>Guardian</small><strong>{detail.guardian_name} ({detail.guardian_relationship})</strong></div>
            <div><small>Guardian contact</small><strong>{detail.guardian_phone} · {detail.guardian_email}</strong></div>
            <div><small>Previous school</small><strong>{detail.previous_school || '—'}</strong></div>
            <div><small>Admission no.</small><strong>{detail.generated_admission_number || '—'}</strong></div>
          </div>
          {detail.status !== 'approved' && detail.status !== 'rejected' && ['school_admin', 'admissions_officer', 'principal', 'super_admin'].includes(user.role) && (
            <div className="modal-actions">
              <button className="secondary" onClick={async () => {
                try { await post(`/applications/${detail.id}/set-under-review/`, {}); setDetail({ ...detail, status: 'under_review' }); reload() } catch (e) { setMsg({ kind: 'error', text: e.message }) }
              }}>Mark under review</button>
              <button className="secondary" onClick={async () => {
                if (!window.confirm('Reject this application?')) return
                try { await post(`/applications/${detail.id}/reject/`, {}); setDetail(null); reload() } catch (e) { setMsg({ kind: 'error', text: e.message }) }
              }}>Reject</button>
              <button className="primary" onClick={async () => {
                try {
                  const res = await post(`/applications/${detail.id}/approve/`, {})
                  setMsg({ kind: 'success', text: `Approved — admission number ${res.admission_number}.` })
                  setDetail(null)
                  reload()
                } catch (e) { setMsg({ kind: 'error', text: e.message }) }
              }}>Approve & admit</button>
            </div>
          )}
        </Modal>
      )}

      {detail && name === 'students' && (
        <Modal title={`${detail.name || `${detail.first_name} ${detail.last_name}`} — ${detail.admission_number}`} close={() => setDetail(null)} wide>
          <div className="detail-grid">
            <div><small>Class</small><strong>{detail.class_name || '—'}</strong></div>
            <div><small>Gender</small><strong>{title(detail.gender) || '—'}</strong></div>
            <div><small>Date of birth</small><strong>{fmtDate(detail.date_of_birth)}</strong></div>
            <div><small>Religion</small><strong>{title(detail.religion) || '—'}</strong></div>
            <div><small>State of origin</small><strong>{detail.state_of_origin || '—'}</strong></div>
            <div><small>LGA</small><strong>{detail.lga || '—'}</strong></div>
            <div><small>Nationality</small><strong>{detail.nationality || '—'}</strong></div>
            <div><small>NIN</small><strong>{detail.nin || '—'}</strong></div>
            <div><small>Blood group</small><strong>{detail.blood_group || '—'}</strong></div>
            <div><small>Genotype</small><strong>{detail.genotype || '—'}</strong></div>
            <div><small>Previous school</small><strong>{detail.previous_school || '—'}</strong></div>
            <div style={{ gridColumn: '1 / -1' }}><small>Allergies / medical conditions</small><strong>{detail.medical_conditions || '—'}</strong></div>
            <div style={{ gridColumn: '1 / -1' }}><small>Address</small><strong>{detail.address || '—'}</strong></div>
          </div>
        </Modal>
      )}

      {grading && (
        <SubmissionsModal assignment={grading} close={() => setGrading(null)} />
      )}

      {submitting && (
        <Modal title={`Submit — ${submitting.title}`} close={() => setSubmitting(null)}>
          <p className="muted">
            {submitting.class_name} · {submitting.subject_name} · due {fmtDate(submitting.due_date)}
            · max {submitting.max_points} pts
          </p>
          <form className="stack" onSubmit={async e => {
            e.preventDefault()
            const fd = new FormData(e.target)
            fd.append('assignment', submitting.id)
            setSaving(true)
            try {
              await post('/submissions/', fd)
              setMsg({ kind: 'success', text: 'Work submitted — your teacher will mark it.' })
              setSubmitting(null)
            } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
            finally { setSaving(false) }
          }}>
            <label>Your answer / notes
              <textarea name="content" rows="5" placeholder="Type your answer or notes here…" />
            </label>
            <label>Attach a file (optional)
              <input type="file" name="file" />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setSubmitting(null)}>Cancel</button>
              <button className="primary" disabled={saving}>{saving ? 'Submitting…' : 'Submit work'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
