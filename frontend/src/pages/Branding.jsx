import React, { useEffect, useState } from 'react'
import { get } from '../api'
import { api } from '../api'
import { useAuth } from '../auth'
import { PageHead, Alert, BrandMark } from '../ui'

const LAYOUT_TOGGLES = [
  ['show_position', 'Show positions'],
  ['show_class_size', 'Show class size'],
  ['show_grade_points', 'Show grade points'],
  ['show_teacher_comment', "Teacher's comment"],
  ['show_principal_comment', "Principal's comment"],
  ['show_attendance_summary', 'Attendance summary'],
]

export default function Branding() {
  const { user, refresh } = useAuth()
  const schoolId = user.branding?.id || user.school
  const [primary, setPrimary] = useState(user.branding?.primary_color || '#1c5b52')
  const [secondary, setSecondary] = useState(user.branding?.secondary_color || '#e9a23b')
  const [logo, setLogo] = useState(null)
  const [logoUrl, setLogoUrl] = useState(user.branding?.logo || null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [cfg, setCfg] = useState(user.branding?.report_config || {})
  const [tplFile, setTplFile] = useState(null)
  const [tplMsg, setTplMsg] = useState(null)

  const weights = cfg.weights || { ca1: 20, ca2: 20, exam: 60 }
  const bands = cfg.grade_bands || []

  useEffect(() => {
    if (schoolId) {
      get(`/schools/${schoolId}/`)
        .then(s => {
          setPrimary(s.primary_color || primary)
          setSecondary(s.secondary_color || secondary)
          setLogoUrl(s.logo || logoUrl)
          setCfg(s.report_config || {})
        })
        .catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schoolId])

  const save = async () => {
    if (!schoolId) {
      setMsg({ kind: 'error', text: 'No school is linked to this account.' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const body = new FormData()
      body.append('primary_color', primary)
      body.append('secondary_color', secondary)
      if (logo) body.append('logo', logo)
      const res = await api(`/schools/${schoolId}/`, { method: 'PATCH', body })
      if (res.logo) setLogoUrl(res.logo)
      await refresh()
      setMsg({ kind: 'success', text: 'Branding saved — it now applies across your school portal.' })
    } catch (e) {
      setMsg({ kind: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const saveCfg = async patch => {
    if (!schoolId) return
    try {
      const res = await api(`/schools/${schoolId}/report-config/`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
        headers: { 'Content-Type': 'application/json' },
      })
      setCfg(res.report_config || {})
      setTplMsg({ kind: 'success', text: 'Report format saved — applies to computed results and PDF cards.' })
      await refresh()
    } catch (e) {
      setTplMsg({ kind: 'error', text: e.message })
    }
  }

  const uploadTemplate = async () => {
    if (!tplFile || !schoolId) return
    const body = new FormData()
    body.append('file', tplFile)
    setTplMsg(null)
    try {
      const res = await api(`/schools/${schoolId}/report-template/`, { method: 'POST', body })
      setCfg(res.report_config || cfg)
      setTplFile(null)
      setTplMsg({ kind: 'success', text: res.adopted?.note || res.detail })
    } catch (e) {
      setTplMsg({ kind: 'error', text: e.message })
    }
  }

  const updateBand = (i, key, value) => {
    const next = bands.map((b, j) => (j === i ? { ...b, [key]: value } : b))
    setCfg({ ...cfg, grade_bands: next })
  }

  const schoolName = user.branding?.name || 'Your school'

  return (
    <>
      <PageHead
        title="School branding"
        subtitle="Make TabsForge feel like your school — saved changes apply immediately."
        action={<button className="primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <div className="branding-grid">
        <section className="panel stack">
          <h3>Brand identity</h3>
          <label>School logo
            <div className="logo-upload">
              <span className={logoUrl ? 'has-logo' : ''}>
                {logoUrl ? <img src={logoUrl} alt="logo" /> : schoolName.slice(0, 2).toUpperCase()}
              </span>
              <div>
                <strong>{logo ? logo.name : 'Upload a new logo'}</strong>
                <small>PNG, JPG or SVG · Max 2 MB</small>
              </div>
              <input type="file" accept="image/*" onChange={e => setLogo(e.target.files[0])} />
            </div>
          </label>
          <label>Primary colour
            <div className="color-field">
              <input type="color" value={primary} onChange={e => setPrimary(e.target.value)} />
              <input value={primary} onChange={e => setPrimary(e.target.value)} />
            </div>
          </label>
          <label>Accent colour
            <div className="color-field">
              <input type="color" value={secondary} onChange={e => setSecondary(e.target.value)} />
              <input value={secondary} onChange={e => setSecondary(e.target.value)} />
            </div>
          </label>
        </section>
        <section className="preview-card">
          <span>Live preview</span>
          <div className="preview-window">
            <header style={{ background: primary }}>
              {logoUrl ? <img src={logoUrl} alt="" className="preview-logo" /> : null}
              <b>{schoolName}</b>
              <button style={{ background: secondary }}>Sign in</button>
            </header>
            <main>
              <div className="preview-hero" style={{ borderColor: primary }}>
                <small>WELCOME BACK</small>
                <h2>Learning starts here.</h2>
                <span style={{ background: primary }}>View dashboard</span>
              </div>
              <footer className="preview-watermark">
                <BrandMark small /> <small>Powered by TabsForge</small>
              </footer>
            </main>
          </div>
        </section>
      </div>

      <section className="panel stack" style={{ marginTop: '1.25rem' }}>
        <h3>Report card format</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Upload your school's report card template (PDF, Word or Excel). Excel/Word
          grading tables are adopted automatically; PDF is kept as the reference layout.
          Then review the adopted weights and grade bands below — nothing is applied
          until you save.
        </p>
        {tplMsg && <Alert kind={tplMsg.kind}>{tplMsg.text}</Alert>}
        <div className="filter-row" style={{ alignItems: 'flex-end' }}>
          <label style={{ flex: 1 }}>Template file
            <input type="file" accept=".pdf,.docx,.xlsx,.xls,.csv"
              onChange={e => setTplFile(e.target.files[0])} />
          </label>
          <button className="secondary" onClick={uploadTemplate} disabled={!tplFile}
            title={tplFile ? 'Upload and adopt this report format' : 'Choose a PDF, Word, or Excel file first'}>Upload &amp; analyse</button>
        </div>
        {cfg.template_name && (
          <small className="muted">Current template: {cfg.template_name}
            {cfg.adopted?.bands ? ` · ${cfg.adopted.bands} grade band(s) adopted` : ''}</small>
        )}

        <h4>Score weights (%)</h4>
        <div className="filter-row">
          {[['ca1', 'CA 1'], ['ca2', 'CA 2'], ['exam', 'Exam']].map(([k, label]) => (
            <label key={k}>{label}
              <input type="number" min="0" max="100" value={weights[k]}
                onChange={e => setCfg({ ...cfg, weights: { ...weights, [k]: Number(e.target.value) } })} />
            </label>
          ))}
          <span className="muted" style={{ alignSelf: 'flex-end' }}>
            Total: {Number(weights.ca1) + Number(weights.ca2) + Number(weights.exam)}%
          </span>
        </div>

        <div className="table-tools" style={{ padding: 0 }}>
          <h4 style={{ margin: 0 }}>Grade bands</h4>
          <button className="secondary" onClick={() => setCfg({
            ...cfg, grade_bands: [...bands, { min: 0, label: '', remark: '', points: 0 }],
          })}>＋ Add band</button>
        </div>
        {bands.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Min %</th><th>Grade</th><th>Remark</th><th>Points</th><th /></tr></thead>
              <tbody>
                {bands.map((b, i) => (
                  <tr key={i}>
                    <td><input type="number" min="0" max="100" value={b.min}
                      onChange={e => updateBand(i, 'min', Number(e.target.value))} /></td>
                    <td><input value={b.label} onChange={e => updateBand(i, 'label', e.target.value)} /></td>
                    <td><input value={b.remark} onChange={e => updateBand(i, 'remark', e.target.value)} /></td>
                    <td><input type="number" step="0.5" value={b.points}
                      onChange={e => updateBand(i, 'points', Number(e.target.value))} /></td>
                    <td><button className="secondary" onClick={() => setCfg({
                      ...cfg, grade_bands: bands.filter((_, j) => j !== i),
                    })}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <small className="muted">No custom bands — the school's grading scheme (or WAEC default) is used.</small>
        )}

        <h4>Layout options</h4>
        <div className="filter-row" style={{ gap: '1rem' }}>
          {LAYOUT_TOGGLES.map(([k, label]) => (
            <label key={k} style={{ display: 'flex', alignItems: 'center', gap: '.4rem' }}>
              <input type="checkbox" checked={cfg[k] !== false}
                onChange={e => setCfg({ ...cfg, [k]: e.target.checked })} />
              {label}
            </label>
          ))}
        </div>
        <label>Footer note (printed at the bottom of every report card)
          <input value={cfg.footer_note || ''}
            onChange={e => setCfg({ ...cfg, footer_note: e.target.value })}
            placeholder="e.g. Next term begins Monday 8th January" />
        </label>
        <div>
          <button className="primary" onClick={() => saveCfg({
            weights: cfg.weights, grade_bands: cfg.grade_bands,
            footer_note: cfg.footer_note,
            ...Object.fromEntries(LAYOUT_TOGGLES.map(([k]) => [k, cfg[k] !== false])),
          })}>Save report format</button>
        </div>
      </section>
    </>
  )
}
