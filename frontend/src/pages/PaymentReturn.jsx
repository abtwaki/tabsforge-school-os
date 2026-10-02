import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { get } from '../api'
import { PageHead, Alert } from '../ui'

/** Landing page after a Paystack/Flutterwave checkout — verifies the charge
 *  server-side and settles it into a Payment + receipt. */
export default function PaymentReturn() {
  const params = new URLSearchParams(window.location.search)
  const provider = params.get('provider') || 'paystack'
  const reference = params.get('reference') || params.get('tx_ref') || ''
  const [state, setState] = useState('checking')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!reference) { setState('bad'); return }
    get(`/payments/${provider}/verify/?reference=${encodeURIComponent(reference)}${params.get('transaction_id') ? `&transaction_id=${params.get('transaction_id')}` : ''}`)
      .then(d => setState(d.status === 'paid' ? 'paid' : 'failed'))
      .catch(e => { setError(e.message); setState('failed') })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <PageHead title="Payment status" subtitle="Confirming your online payment with the bank." />
      <section className="panel" style={{ maxWidth: 560, margin: '40px auto', textAlign: 'center' }}>
        {state === 'checking' && <p className="muted">Confirming payment…</p>}
        {state === 'paid' && (
          <>
            <p style={{ fontSize: 40, margin: '8px 0' }}>✅</p>
            <h3>Payment received</h3>
            <p className="muted">Reference {reference} — a receipt has been issued and the invoice balance updated.</p>
          </>
        )}
        {state === 'failed' && (
          <>
            <p style={{ fontSize: 40, margin: '8px 0' }}>⚠️</p>
            <h3>Payment not completed</h3>
            <p className="muted">{error || 'The payment could not be confirmed. If you were debited, contact the bursar with your reference.'}</p>
          </>
        )}
        {state === 'bad' && (
          <p className="muted">No payment reference in the link — return to your invoices and try again.</p>
        )}
        <div style={{ marginTop: 16 }}>
          <Link className="primary" to="/invoices" style={{ padding: '10px 18px', borderRadius: 8 }}>Back to invoices</Link>
        </div>
      </section>
    </>
  )
}
