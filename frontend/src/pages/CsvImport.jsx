import React, { useState } from 'react'
import { getToken } from '../api'
import { PageHead, Alert } from '../ui'

export default function CsvImport() {
  const [type, setType] = useState('students')
  const [file, setFile] = useState(null)
  const [phase, setPhase] = useState('idle') // idle | validated | committed
  const [errors, setErrors] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const validate = async commit => {
    if (!file) return
    setBusy(true)
    setResult(null)
    setErrors([])
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await fetch(`/api/import/${type}/${commit ? '?commit=true' : ''}`, {
        method: 'POST',
        headers: { Authorization: `Token ${getToken()}` },
        body,
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setResult({ kind: 'success', text: data.detail })
        setPhase(commit ? 'committed' : 'validated')
      } else {
        setResult({ kind: 'error', text: data.detail || `Import failed (${res.status})` })
        setErrors(data.errors || [])
      }
    } catch (e) {
      setResult({ kind: 'error', text: `Network error: ${e.message}` })
    } finally {
      setBusy(false)
    }
  }

  const downloadTemplate = () => {
    const a = document.createElement('a')
    a.href = `/api/import/${type}/template/`
    a.download = `${type}_template.csv`
    // needs auth header — fetch blob instead
    fetch(`/api/import/${type}/template/`, {
      headers: { Authorization: `Token ${getToken()}` },
    })
      .then(r => r.blob())
      .then(b => {
        const url = URL.createObjectURL(b)
        a.href = url
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => {})
  }

  return (
    <>
      <PageHead title="CSV import" subtitle="Bring student and staff records into TabsForge in minutes." />
      {result && <Alert kind={result.kind}>{result.text}</Alert>}
      <section className="panel import-panel">
        <div className="import-tabs">
          {[['students', 'Students'], ['staff', 'Staff']].map(([v, l]) => (
            <button key={v} className={type === v ? 'active' : ''} onClick={() => { setType(v); setPhase('idle'); setErrors([]); setResult(null) }}>{l}</button>
          ))}
        </div>
        <div className="upload-zone">
          <span>⇧</span>
          <h3>Drop your CSV file here</h3>
          <p>or choose a file from your computer</p>
          <label className="primary">Browse files
            <input type="file" accept=".csv" onChange={e => { setFile(e.target.files[0]); setPhase('idle'); setErrors([]); setResult(null) }} />
          </label>
          {file && <strong>{file.name}</strong>}
        </div>
        <div className="import-help">
          <div><strong>1</strong><span><b>Download the template</b><small>Start with the correctly formatted columns.</small></span><button className="secondary" onClick={downloadTemplate}>Download CSV</button></div>
          <div><strong>2</strong><span><b>Complete your records</b><small>{type === 'students' ? 'Required: first_name, last_name, admission_number. Optional: class_name, section_name, parent_email, parent_phone.' : 'Required: first_name, last_name, email, employee_id.'}</small></span></div>
          <div><strong>3</strong><span><b>Upload and validate</b><small>We flag row-level issues before anything is saved.</small></span></div>
        </div>
        {file && (
          <div className="validation">
            <strong>{phase === 'committed' ? 'Import complete' : phase === 'validated' ? 'File valid — ready to import' : 'Ready to validate'}</strong>
            <span>{phase === 'validated' ? 'No errors found. You can now commit the import.' : 'Validate first — nothing is saved until you commit.'}</span>
            <div className="head-actions">
              <button className="secondary" onClick={() => validate(false)} disabled={busy}>{busy ? 'Checking…' : 'Validate file'}</button>
              {phase === 'validated' && (
                <button className="primary" onClick={() => validate(true)} disabled={busy}>{busy ? 'Importing…' : `Import ${type}`}</button>
              )}
            </div>
          </div>
        )}
        {errors.length > 0 && (
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table>
              <thead><tr><th>Row</th><th>Problem</th></tr></thead>
              <tbody>
                {errors.map((e, i) => (
                  <tr key={i}><td><strong>Row {e.row}</strong></td><td>{(e.errors || []).join(' ')}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
