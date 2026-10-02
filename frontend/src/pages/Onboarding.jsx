import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, post } from '../api'
import { title } from '../auth'
export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({ tier: 'roots', requested_modules: [] })
  const [tiers, setTiers] = useState(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (k, v) => setForm({ ...form, [k]: v })

  useEffect(() => {
    get('/onboarding/tiers/')
      .then(d => setTiers(d.tiers || []))
      .catch(() => setTiers([]))
  }, [])

  const activeTier = (tiers || []).find(t => t.id === form.tier)
  const toggleModule = key =>
    update('requested_modules', form.requested_modules.includes(key)
      ? form.requested_modules.filter(m => m !== key)
      : [...form.requested_modules, key])

  useEffect(() => {
    if (step !== 3 || !form.subdomain) return
    setStatus('checking')
    const timer = setTimeout(() => {
      get(`/onboarding/check_subdomain/?subdomain=${encodeURIComponent(form.subdomain)}`)
        .then(d => setStatus(d.available ? 'available' : 'taken'))
        .catch(() => setStatus('Unable to verify subdomain availability'))
    }, 450)
    return () => clearTimeout(timer)
  }, [form.subdomain, step])

  const submit = async () => {
    setBusy(true)
    try {
      const adminName = `${form.admin_first_name || ''} ${form.admin_last_name || ''}`.trim()
      await post('/onboarding/', {
        school_name: form.name,
        address: form.address || '',
        subdomain: form.subdomain,
        tier: title(form.tier),
        billing_cycle: 'termly',
        admin_name: adminName,
        admin_email: form.admin_email,
        admin_password: form.password,
        contact_info: { email: form.contact_email || '', phone: form.phone || '' },
        requested_modules: form.requested_modules,
      })
      setStep(6)
    } catch (e) {
      setStatus(`Request failed: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="onboarding">
      <header>
        <div className="brand"><img className="logo-full" src="/logo.jpg" alt="TabsForge School OS" /></div>
        <button onClick={() => navigate('/login')}>Sign in</button>
      </header>
      <div className="onboard-wrap">
        <div className="progress">
          {[1, 2, 3, 4, 5].map(n => (
            <React.Fragment key={n}>
              <span className={step >= n ? 'done' : ''}>{step > n ? '✓' : n}</span>
              {n < 5 && <i className={step > n ? 'done' : ''} />}
            </React.Fragment>
          ))}
        </div>
        {step === 6 ? (
          <section className="onboard-card success">
            <span>✓</span>
            <h1>Your application is on its way</h1>
            <p>We’ll review your school details and send account access instructions to {form.admin_email}.</p>
            <button className="primary" onClick={() => navigate('/login')}>Return to sign in</button>
          </section>
        ) : (
          <section className="onboard-card">
            <span className="eyebrow">Step {step} of 5</span>
            {step === 1 && (
              <>
                <h1>Tell us about your school</h1>
                <p>Start with the essentials. You can update these later.</p>
                <div className="form-grid">
                  <label>School name<input value={form.name || ''} onChange={e => update('name', e.target.value)} placeholder="Greenfield Academy" /></label>
                  <label>Contact email<input type="email" value={form.contact_email || ''} onChange={e => update('contact_email', e.target.value)} /></label>
                  <label className="span-2">Address<textarea value={form.address || ''} onChange={e => update('address', e.target.value)} rows="3" /></label>
                  <label>Phone<input value={form.phone || ''} onChange={e => update('phone', e.target.value)} /></label>
                  <label>School logo<input type="file" onChange={e => update('logo', e.target.files[0])} /></label>
                </div>
              </>
            )}
            {step === 2 && (
              <>
                <h1>Choose the right foundation</h1>
                <p>Plans grow with your school. Upgrade any time.</p>
                {!tiers ? <p className="muted">Loading plans…</p> : (
                  <div className="tier-grid plans">
                    {tiers.map(t => (
                      <button type="button" key={t.id}
                        className={form.tier === t.id ? 'selected' : ''}
                        onClick={() => update('tier', t.id)}>
                        <span>{t.tagline}</span>
                        <h3>{t.name}</h3>
                        <strong className="tier-price">{t.billing}</strong>
                        <ul className="tier-mods">
                          {t.modules.slice(0, 8).map(m => <li key={m.key}>{m.label}</li>)}
                          {t.modules.length > 8 && <li>+ {t.modules.length - 8} more</li>}
                        </ul>
                        <small className="tier-fit">Best for: {t.suitable}</small>
                      </button>
                    ))}
                  </div>
                )}
                {activeTier && activeTier.extra_modules.length > 0 && (
                  <div className="addon-box">
                    <strong>Need modules outside the {activeTier.name} plan?</strong>
                    <p className="muted">Select any extras — the platform team reviews and can enable them for your school.</p>
                    <div className="module-grid">
                      {activeTier.extra_modules.map(m => (
                        <label key={m.key} className="check">
                          <input type="checkbox" checked={form.requested_modules.includes(m.key)}
                            onChange={() => toggleModule(m.key)} />
                          {m.label}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {step === 3 && (
              <>
                <h1>Claim your school address</h1>
                <p>This becomes your unique TabsForge workspace.</p>
                <label className="subdomain">School subdomain
                  <div>
                    <input value={form.subdomain || ''} onChange={e => update('subdomain', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder="greenfield" />
                    <span>.tabsforge.com</span>
                  </div>
                  {status && <small className={status}>{status === 'checking' ? 'Checking availability…' : status === 'available' ? 'Available — it’s yours!' : 'This address is already taken.'}</small>}
                </label>
              </>
            )}
            {step === 4 && (
              <>
                <h1>Create your admin account</h1>
                <p>This person will manage the school workspace.</p>
                <div className="form-grid">
                  <label>First name<input value={form.admin_first_name || ''} onChange={e => update('admin_first_name', e.target.value)} /></label>
                  <label>Last name<input value={form.admin_last_name || ''} onChange={e => update('admin_last_name', e.target.value)} /></label>
                  <label className="span-2">Email address<input type="email" value={form.admin_email || ''} onChange={e => update('admin_email', e.target.value)} /></label>
                  <label className="span-2">Password<input type="password" value={form.password || ''} onChange={e => update('password', e.target.value)} /></label>
                </div>
              </>
            )}
            {step === 5 && (
              <>
                <h1>Everything look right?</h1>
                <p>Review your details before submitting for approval.</p>
                <div className="review">
                  <div><small>School</small><strong>{form.name || 'Not provided'}</strong><span>{form.address}</span></div>
                  <div><small>Plan</small><strong>{title(form.tier)}</strong><span>{form.subdomain}.tabsforge.com</span>
                    {form.requested_modules.length > 0 &&
                      <span>+ {form.requested_modules.length} extra module{form.requested_modules.length > 1 ? 's' : ''} requested</span>}
                  </div>
                  <div><small>Administrator</small><strong>{form.admin_first_name} {form.admin_last_name}</strong><span>{form.admin_email}</span></div>
                </div>
              </>
            )}
            <footer>
              <button className="secondary" disabled={step === 1} onClick={() => setStep(step - 1)}>Back</button>
              <button className="primary" disabled={(step === 3 && status !== 'available') || busy}
                title={step === 3 && status !== 'available' ? 'Pick an available subdomain above to continue' : ''}
                onClick={() => step === 5 ? submit() : setStep(step + 1)}>
                {busy ? 'Submitting…' : step === 5 ? 'Submit application' : 'Continue'}
              </button>
            </footer>
            {typeof status === 'string' && status.startsWith('Request failed') && <div className="alert">{status}</div>}
          </section>
        )}
      </div>
    </main>
  )
}
