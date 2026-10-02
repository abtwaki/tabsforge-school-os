import React, { useState } from 'react'
import { download } from '../api'
import { Alert, PageHead } from '../ui'

const MODULES = [
  ['Students', 'students'], ['Staff', 'staff'], ['Users', 'users'],
  ['Results', 'results'], ['Attendance', 'attendance'],
  ['Payments', 'payments'], ['Debtors', 'debtors'], ['Fee collection', 'fee-collection'],
]

/** Whole-school data export — every dataset as an Excel workbook sheet,
 * for data portability, backups and NDPR data-subject requests. */
export default function DataExport() {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const fullExport = async () => {
    setBusy(true); setMsg(null)
    try {
      await download('/export/all/', `tabsforge-export-${new Date().toISOString().slice(0, 10)}.xlsx`)
      setMsg({ kind: 'success', text: 'Export downloaded — one sheet per dataset, archived records included.' })
    } catch (e) { setMsg({ kind: 'error', text: e.message }) }
    finally { setBusy(false) }
  }

  return (
    <>
      <PageHead title="Data export"
        subtitle="Download everything your school has stored — for backups, audits, portability and data-subject requests." />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      <section className="panel" style={{ maxWidth: 720 }}>
        <h3>Complete school export</h3>
        <p className="muted">
          One Excel workbook covering students, guardians, enrolments, staff, classes,
          sessions &amp; terms, assessments, grades, report cards, invoices, payments,
          expenses, assignments, submissions, timetable, announcements, library,
          transport, hostel and user accounts.
        </p>
        <button className="primary" onClick={fullExport} disabled={busy}>
          {busy ? 'Preparing workbook…' : '⬇ Download full export (.xlsx)'}
        </button>
      </section>

      <section className="panel" style={{ maxWidth: 720 }}>
        <h3>Per-module exports</h3>
        <p className="muted">Single-dataset exports for routine reporting — pick a format per module.</p>
        <div className="table-wrap">
          <table>
            <tbody>
              {MODULES.map(([label, kind]) => (
                <tr key={kind}>
                  <td><strong>{label}</strong></td>
                  <td>
                    <div className="head-actions">
                      {['xlsx', 'csv', 'docx'].map(fmt => (
                        <button key={fmt} className="ghost sm"
                          onClick={() => download(`/exports/${kind}/${fmt}/`, `${kind}.${fmt}`).catch(e => setMsg({ kind: 'error', text: e.message }))}>
                          {fmt === 'xlsx' ? 'Excel' : fmt.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
