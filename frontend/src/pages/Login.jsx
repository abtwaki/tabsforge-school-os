import React, { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { get, post } from '../api'

const REASONS = {
  idle: 'You were signed out after 30 minutes of inactivity — sign in again to continue.',
  expired: 'Your session expired — sign in again to continue.',
}

export default function Login() {
  const { user, login, setUser } = useAuth()
  const navigate = useNavigate()
  const params = new URLSearchParams(window.location.search)
  const tenant = params.get('tenant')
  const reason = params.get('reason')
  const [form, setForm] = useState({ email: '', password: '', stay: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // mode: 'login' | 'reset-email' | 'reset-code' | 'reset-totp' | 'reset-done'
  const [mode, setMode] = useState('login')
  const [reset, setReset] = useState({ email: '', otp_id: null, code: '', new_password: '', hint: '' })

  if (user) return <Navigate to="/" replace />

  const submit = async e => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      // Session policy flags are set before login resolves so Shell picks them up.
      localStorage.setItem('tabsforge_login_at', String(Date.now()))
      if (form.stay) localStorage.setItem('tabsforge_stay', '1')
      else localStorage.removeItem('tabsforge_stay')
      await login({ email: form.email, password: form.password })
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const sendResetCode = async e => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await post('/auth/send-otp/', { email: reset.email, purpose: 'password_reset' })
      setReset({ ...reset, otp_id: r.otp_id, hint: r.detail })
      setMode('reset-code')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const doReset = async e => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = mode === 'reset-totp'
        ? { email: reset.email, totp_code: reset.code, new_password: reset.new_password }
        : { otp_id: reset.otp_id, code: reset.code, new_password: reset.new_password }
      await post('/auth/reset-password/', body)
      setMode('reset-done')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const guestLogin = async () => {
    setBusy(true)
    setError('')
    try {
      localStorage.setItem('tabsforge_login_at', String(Date.now()))
      const r = await post('/auth/guest-token/', {})
      localStorage.setItem('tabsforge_token', r.token)
      const u = await get('/auth/me/')
      localStorage.setItem('tabsforge_user', JSON.stringify(u))
      setUser(u)
      navigate('/')
    } catch (err) {
      localStorage.removeItem('tabsforge_token')
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const backToLogin = () => {
    setMode('login')
    setError('')
    setReset({ email: '', otp_id: null, code: '', new_password: '', hint: '' })
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand light"><img className="logo-full" src="/logo.jpg" alt="TabsForge School OS" /></div>
        <div>
          <span className="eyebrow">School operations, composed</span>
          <h1>One calm place to run your entire school.</h1>
          <p>Keep learning, people, finance, and communication beautifully in sync.</p>
          <div className="auth-cta">
            <a className="ghost light" href="/learn/">Learn about TabsForge</a>
            <a className="ghost light" href="/onboarding">Onboard your school</a>
          </div>
        </div>
        <div className="quote">“The operating system thoughtful schools deserve.”</div>
      </section>
      <section className="auth-panel">
        {mode === 'login' && (
          <form className="login-card" onSubmit={submit}>
            <div className="brand mobile"><img className="logo-full" src="/logo.jpg" alt="TabsForge School OS" /></div>
            <span className="eyebrow">Welcome back</span>
            <h2>Sign in to your workspace</h2>
            <p>Use your school account to continue.</p>
            {reason && REASONS[reason] && <div className="alert warn">{REASONS[reason]}</div>}
            {error && <div className="alert">{error}</div>}
            <label>Email address
              <input autoFocus required type="email" autoComplete="username" value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                placeholder="you@school.edu" />
            </label>
            <label>Password
              <input required type="password" autoComplete="current-password" value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="Enter your password" />
            </label>
            <label className="check-line">
              <input type="checkbox" checked={form.stay}
                onChange={e => setForm({ ...form, stay: e.target.checked })} />
              <span>Keep me signed in on this device</span>
            </label>
            <button className="primary full" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
            <button type="button" className="ghost" style={{ alignSelf: 'center' }}
              onClick={() => { setMode('reset-email'); setReset({ ...reset, email: form.email }); setError('') }}>
              Forgot password?
            </button>
            <button type="button" className="secondary full" disabled={busy} onClick={guestLogin}
              style={{ marginTop: 4 }}>
              {busy ? 'Please wait…' : 'Explore the live demo'}
            </button>
            <div className="auth-cta">
              <a className="ghost" href="/learn/">Learn about TabsForge</a>
              <a className="ghost" href="/onboarding">Onboard your school</a>
            </div>
            <div className="auth-links">
              {tenant && <span style={{ color: 'var(--muted)' }}>Workspace: {tenant}</span>}
              <span>Need help? Contact your administrator.</span>
            </div>
          </form>
        )}

        {mode === 'reset-email' && (
          <form className="login-card" onSubmit={sendResetCode}>
            <span className="eyebrow">Password reset</span>
            <h2>Send a reset code</h2>
            <p>Enter your account email — we'll send a 6-digit code to your registered channel.</p>
            {error && <div className="alert">{error}</div>}
            <label>Email address
              <input autoFocus required type="email" autoComplete="username" value={reset.email}
                onChange={e => setReset({ ...reset, email: e.target.value })}
                placeholder="you@school.edu" />
            </label>
            <button className="primary full" disabled={busy}>
              {busy ? 'Sending…' : 'Send reset code'}
            </button>
            <button type="button" className="ghost" style={{ alignSelf: 'center' }}
              onClick={() => { setMode('reset-totp'); setError('') }}>
              Use an authenticator app instead
            </button>
            <button type="button" className="ghost" style={{ alignSelf: 'center' }} onClick={backToLogin}>
              ← Back to sign in
            </button>
          </form>
        )}

        {(mode === 'reset-code' || mode === 'reset-totp') && (
          <form className="login-card" onSubmit={doReset}>
            <span className="eyebrow">Password reset</span>
            <h2>{mode === 'reset-totp' ? 'Authenticator code' : 'Enter your code'}</h2>
            <p>{mode === 'reset-totp'
              ? 'Enter the 6-digit code from your authenticator app (Google Authenticator, Authy, etc).'
              : (reset.hint || 'Check your email/WhatsApp for the 6-digit code.') + ' It expires in 10 minutes.'}</p>
            {error && <div className="alert">{error}</div>}
            {mode === 'reset-totp' && (
              <label>Email address
                <input required type="email" autoComplete="username" value={reset.email}
                  onChange={e => setReset({ ...reset, email: e.target.value })}
                  placeholder="you@school.edu" />
              </label>
            )}
            <label>{mode === 'reset-totp' ? 'Authenticator code' : 'Reset code'}
              <input autoFocus required value={reset.code} maxLength={6}
                inputMode={mode === 'reset-totp' ? 'numeric' : 'text'}
                onChange={e => setReset({ ...reset, code: e.target.value.toUpperCase() })}
                placeholder="6-digit code" autoComplete="one-time-code" />
            </label>
            <label>New password
              <input required type="password" minLength={8} autoComplete="new-password" value={reset.new_password}
                onChange={e => setReset({ ...reset, new_password: e.target.value })}
                placeholder="At least 8 characters" />
            </label>
            <button className="primary full" disabled={busy}>
              {busy ? 'Updating…' : 'Set new password'}
            </button>
            <button type="button" className="ghost" style={{ alignSelf: 'center' }} onClick={backToLogin}>
              ← Back to sign in
            </button>
          </form>
        )}

        {mode === 'reset-done' && (
          <div className="login-card">
            <span className="eyebrow">Password reset</span>
            <h2>Password updated</h2>
            <p>Your password has been changed. Sign in with your new password.</p>
            <button className="primary full" onClick={backToLogin}>Back to sign in</button>
          </div>
        )}
      </section>
    </main>
  )
}
