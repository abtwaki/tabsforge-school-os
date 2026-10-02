import React, { useEffect, useState } from 'react'
import { get, post, download } from '../api'
import { useAuth, title } from '../auth'
import { PageHead, Modal, Empty, Alert, money, fmtDate, statusBadge } from '../ui'

const WRITERS = new Set(['super_admin', 'school_admin', 'accountant'])
const PAY_METHODS = [['cash', 'Cash'], ['bank_transfer', 'Bank Transfer'], ['card', 'Card'], ['mobile_money', 'Mobile Money'], ['cheque', 'Cheque'], ['ussd', 'USSD'], ['paystack', 'Paystack'], ['flutterwave', 'Flutterwave']]

export default function Fees() {
  const { user } = useAuth()
  const canWrite = WRITERS.has(user.role)
  const [kpis, setKpis] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [payments, setPayments] = useState([])
  const [terms, setTerms] = useState([])
  const [students, setStudents] = useState([])
  const [classes, setClasses] = useState([])
  const [showInvoice, setShowInvoice] = useState(false)
  const [showPayment, setShowPayment] = useState(false)
  const [showExpense, setShowExpense] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [showLedger, setShowLedger] = useState(false)
  const [ledgerStudent, setLedgerStudent] = useState('')
  const [bulkResult, setBulkResult] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    get('/dashboard/').then(d => setKpis(d.kpis)).catch(() => {})
    get('/invoices/?page_size=50').then(d => setInvoices(d.results || d)).catch(() => {})
    get('/payments/?page_size=50').then(d => setPayments(d.results || d)).catch(() => {})
  }
  useEffect(() => {
    load()
    get('/terms/?page_size=50').then(d => setTerms(d.results || d)).catch(() => {})
    get('/students/?page_size=500').then(d => setStudents(d.results || d)).catch(() => {})
    get('/classes/?page_size=100').then(d => setClasses(d.results || d)).catch(() => {})
  }, [])

  const createInvoice = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    try {
      await post('/invoices/', {
        student: Number(fd.get('student')),
        term: Number(fd.get('term')),
        total_amount: Number(fd.get('total_amount')),
        due_date: fd.get('due_date'),
        notes: fd.get('notes') || '',
        status: 'sent',
      })
      setShowInvoice(false)
      setMsg({ kind: 'success', text: 'Invoice created.' })
      load()
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const recordPayment = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    try {
      const res = await post('/payments/', {
        invoice: Number(fd.get('invoice')),
        amount: Number(fd.get('amount')),
        method: fd.get('method'),
        reference: fd.get('reference') || '',
      })
      setShowPayment(false)
      setReceipt(res)
      setMsg({ kind: 'success', text: `Payment recorded — receipt ${res.receipt_number || 'issued'}.` })
      load()
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const recordExpense = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    try {
      await post('/expenses/', {
        title: fd.get('title'),
        category: fd.get('category'),
        amount: Number(fd.get('amount')),
        expense_date: fd.get('expense_date'),
        description: fd.get('description') || '',
      })
      setShowExpense(false)
      setMsg({ kind: 'success', text: 'Expense recorded.' })
      load()
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const bulkInvoice = async e => {
    e.preventDefault()
    const fd = new FormData(e.target)
    setBusy(true)
    setBulkResult(null)
    try {
      const body = {
        term: Number(fd.get('term')),
        due_date: fd.get('due_date'),
        status: fd.get('status'),
        notes: fd.get('notes') || '',
      }
      if (fd.get('school_class')) body.school_class = Number(fd.get('school_class'))
      const res = await post('/invoices/bulk/', body)
      setBulkResult(res)
      setShowBulk(false)
      setMsg({ kind: 'success', text: `Bulk invoicing done — ${res.created} invoice(s) created, ${res.skipped.length} skipped, total billed ${money(res.total_billed)}.` })
      load()
    } catch (e2) { setMsg({ kind: 'error', text: e2.message }) }
    finally { setBusy(false) }
  }

  const openInvoices = invoices.filter(i => !['paid', 'cancelled'].includes(i.status))

  return (
    <>
      <PageHead
        title="Fees & billing"
        subtitle="Live figures from your invoices, payments and expenses."
        action={canWrite && (
          <div className="head-actions">
            <button className="secondary" onClick={() => setShowExpense(true)}>＋ Expense</button>
            <button className="secondary" onClick={() => setShowPayment(true)}>＋ Record payment</button>
            <button className="secondary" onClick={() => setShowBulk(true)}
              title="Invoice a whole class (or the whole school) at once from fee structures">Bulk invoice</button>
            <button className="primary" onClick={() => setShowInvoice(true)}>＋ Create invoice</button>
          </div>
        )}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      <div className="kpi-grid compact">
        <article className="kpi"><small>Total billed</small><strong>{kpis ? money(kpis.total_billed) : '—'}</strong><p>All time</p></article>
        <article className="kpi"><small>Collected</small><strong>{kpis ? money(kpis.fees_collected) : '—'}</strong><p>{kpis ? `${kpis.collection_rate}% collection rate` : ''}</p></article>
        <article className="kpi"><small>Outstanding</small><strong>{kpis ? money(kpis.outstanding_fees) : '—'}</strong><p>{kpis ? `${kpis.open_invoices} open invoice(s)` : ''}</p></article>
        <article className="kpi"><small>Expenses</small><strong>{kpis ? money(kpis.expenses_total) : '—'}</strong><p>{kpis ? `Net ${money(kpis.net_balance)}` : ''}</p></article>
      </div>

      <section className="panel table-panel">
        <div className="panel-title">
          <h3>Invoices</h3>
          <div className="head-actions">
            <button className="secondary" onClick={() => download(`/reports/fee-collection-pdf/?term_id=${terms.find(t => t.is_current)?.id || terms[0]?.id || ''}`, 'fee-collection.pdf')}>Fee collection PDF</button>
            <button className="secondary" onClick={() => download(`/reports/debtors-pdf/?term_id=${terms.find(t => t.is_current)?.id || terms[0]?.id || ''}`, 'debtors.pdf')}>Debtors PDF</button>
            <button className="secondary" onClick={() => download(`/reports/income-expenditure-pdf/?term_id=${terms.find(t => t.is_current)?.id || terms[0]?.id || ''}`, 'income-expenditure.pdf')}>Income & expenditure</button>
            <button className="secondary" onClick={() => download(`/exports/payments/xlsx/?term_id=${terms.find(t => t.is_current)?.id || terms[0]?.id || ''}`, 'payments.xlsx')}>Payments Excel</button>
            <button className="secondary" onClick={() => download(`/exports/debtors/docx/?term_id=${terms.find(t => t.is_current)?.id || terms[0]?.id || ''}`, 'debtors.docx')}>Debtors Word</button>
            <button className="secondary" onClick={() => setShowLedger(true)}>Student ledger PDF</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Invoice</th><th>Student</th><th>Term</th><th>Total</th><th>Paid</th><th>Balance</th><th>Status</th></tr></thead>
            <tbody>
              {invoices.map(i => (
                <tr key={i.id}>
                  <td><strong>{i.invoice_number}</strong></td>
                  <td>{i.student_name}</td>
                  <td>{i.term_name}</td>
                  <td>{money(i.total_amount)}</td>
                  <td>{money(i.amount_paid)}</td>
                  <td>{money(i.balance)}</td>
                  <td>{statusBadge(i.status)}</td>
                </tr>
              ))}
              {!invoices.length && (
                <tr><td colSpan="7">
                  <Empty title="No invoices yet"
                    hint="Create an invoice first — payments and balances build from invoices."
                    onAdd={canWrite ? () => setShowInvoice(true) : undefined} />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-title"><h3>Recent payments & receipts</h3></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Receipt</th><th>Invoice</th><th>Method</th><th>Date</th><th>Amount</th></tr></thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.receipt_number || '—'}</strong></td>
                  <td>{p.invoice_number}</td>
                  <td>{title(p.method)}</td>
                  <td>{fmtDate(p.paid_at)}</td>
                  <td>{money(p.amount)}</td>
                </tr>
              ))}
              {!payments.length && (
                <tr><td colSpan="5">
                  <Empty title="No payments recorded"
                    hint="Record a payment against an open invoice once invoices exist."
                    onAdd={canWrite && openInvoices.length ? () => setShowPayment(true) : undefined} />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showLedger && (
        <Modal title="Student fee ledger" close={() => setShowLedger(false)}>
          <form className="stack" onSubmit={e => {
            e.preventDefault()
            if (!ledgerStudent) return
            const termId = terms.find(t => t.is_current)?.id || ''
            download(`/reports/student-ledger-pdf/?student_id=${ledgerStudent}${termId ? `&term_id=${termId}` : ''}`, 'student-ledger.pdf')
            setShowLedger(false)
          }}>
            {!students.length && <Alert kind="error">No students found — add students first.</Alert>}
            <label>Student
              <select required value={ledgerStudent} onChange={e => setLedgerStudent(e.target.value)}>
                <option value="">Select a student…</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.name || `${s.first_name} ${s.last_name}`} ({s.admission_number})</option>)}
              </select>
            </label>
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>
              Downloads a PDF statement of invoices, payments and balance for the current term.
            </p>
            <button className="primary" disabled={!ledgerStudent}>Download ledger</button>
          </form>
        </Modal>
      )}

      {showInvoice && (
        <Modal title="Create invoice" close={() => setShowInvoice(false)}>
          {!students.length && (
            <Alert kind="error">No students exist yet — add or import students first (Students → Add / CSV import).</Alert>
          )}
          {!terms.length && (
            <Alert kind="error">No academic term exists yet — create a session and term first (Setup → Academic Sessions / Terms).</Alert>
          )}
          <form className="stack" onSubmit={createInvoice}>
            <label>Student
              <select name="student" required>
                <option value="">Select student…</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.name || `${s.first_name} ${s.last_name}`} ({s.admission_number})</option>)}
              </select>
            </label>
            <label>Term
              <select name="term" required>
                {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label>Amount (₦)<input name="total_amount" type="number" min="0" step="0.01" required /></label>
            <label>Due date<input name="due_date" type="date" required /></label>
            <label>Notes<textarea name="notes" rows="2" /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowInvoice(false)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Create invoice'}</button>
            </div>
          </form>
        </Modal>
      )}

      {showPayment && (
        <Modal title="Record payment" close={() => setShowPayment(false)}>
          {!openInvoices.length && (
            <Alert kind="error">No open invoices to pay against — create an invoice first (＋ Create invoice).</Alert>
          )}
          <form className="stack" onSubmit={recordPayment}>
            <label>Invoice
              <select name="invoice" required>
                <option value="">Select open invoice…</option>
                {openInvoices.map(i => (
                  <option key={i.id} value={i.id}>
                    {i.invoice_number} — {i.student_name} — balance {money(i.balance)}
                  </option>
                ))}
              </select>
            </label>
            <label>Amount (₦)<input name="amount" type="number" min="0.01" step="0.01" required /></label>
            <label>Method
              <select name="method">{PAY_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </label>
            <label>Reference<input name="reference" placeholder="Transfer ref / teller no." /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowPayment(false)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Recording…' : 'Record payment'}</button>
            </div>
          </form>
        </Modal>
      )}

      {showExpense && (
        <Modal title="Record expense" close={() => setShowExpense(false)}>
          <form className="stack" onSubmit={recordExpense}>
            <label>Title<input name="title" required /></label>
            <label>Category
              <select name="category">
                {['salaries', 'utilities', 'maintenance', 'supplies', 'transport', 'catering', 'rent', 'insurance', 'events', 'other'].map(c => <option key={c} value={c}>{title(c)}</option>)}
              </select>
            </label>
            <label>Amount (₦)<input name="amount" type="number" min="0" step="0.01" required /></label>
            <label>Date<input name="expense_date" type="date" required /></label>
            <label>Description<textarea name="description" rows="2" /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowExpense(false)}>Cancel</button>
              <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save expense'}</button>
            </div>
          </form>
        </Modal>
      )}

      {showBulk && (
        <Modal title="Bulk invoice — bill a class at once" close={() => setShowBulk(false)}>
          {!terms.length && (
            <Alert kind="error">No academic term exists yet — create a session and term first (Setup → Academic Sessions / Terms).</Alert>
          )}
          <Alert kind="warn">
            Each student's invoice total = the sum of fee structures defined for
            their class in the selected term. Students already invoiced for the
            term are skipped — re-running is safe.
          </Alert>
          <form className="stack" onSubmit={bulkInvoice}>
            <label>Term
              <select name="term" required>
                {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label>Class
              <select name="school_class">
                <option value="">All classes</option>
                {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Due date<input name="due_date" type="date" required /></label>
            <label>Status
              <select name="status">
                <option value="sent">Sent (live to parents)</option>
                <option value="draft">Draft (review first)</option>
              </select>
            </label>
            <label>Notes<textarea name="notes" rows="2" placeholder="Shown on the invoice (defaults to the fee items)" /></label>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={() => setShowBulk(false)}>Cancel</button>
              <button className="primary" disabled={busy || !terms.length}>{busy ? 'Generating…' : 'Generate invoices'}</button>
            </div>
          </form>
        </Modal>
      )}

      {bulkResult && (
        <Modal title="Bulk invoice result" close={() => setBulkResult(null)} wide>
          <p><strong>{bulkResult.created}</strong> invoice(s) created · <strong>{money(bulkResult.total_billed)}</strong> billed.</p>
          {!!bulkResult.skipped.length && (
            <>
              <p><strong>{bulkResult.skipped.length} skipped:</strong></p>
              <ul>
                {bulkResult.skipped.map((s, i) => <li key={i}>{s.student} — {s.reason}</li>)}
              </ul>
            </>
          )}
          <div className="modal-actions">
            <button className="primary" onClick={() => setBulkResult(null)}>Done</button>
          </div>
        </Modal>
      )}

      {receipt && (
        <Modal title="Payment recorded" close={() => setReceipt(null)}>
          <div className="receipt">
            <h3>Receipt {receipt.receipt_number || ''}</h3>
            <p>Invoice {receipt.invoice_number} · {money(receipt.amount)} · {title(receipt.method)}</p>
            <div className="modal-actions">
              <button className="primary" onClick={() => setReceipt(null)}>Done</button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
