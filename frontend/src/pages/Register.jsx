import React, { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { post } from '../api'

/** Public page — completes an emailed registration invite (/register?token=…&uid=…). */
export default function Register() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  const uid = params.get('uid')
  const [form, setForm] = useState({ first_name: '', last_name: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  if (user && !done) return <Navigate to="/" replace />

  const submit = async e => {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      const res = await post('/auth/complete-registration/', {
        uid, token,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      })
      localStorage.setItem('tabsforge_token', res.token)
      localStorage.setItem('tabsforge_user', JSON.stringify(res.user))
      localStorage.setItem('tabsforge_login_at', String(Date.now()))
      setDone(true)
      setUser(res.user)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const invalid = !token || !uid

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand light"><img className="logo-full" src="/logo.jpg" alt="TabsForge School OS" /></div>
        <div>
          <span className="eyebrow">You have been invited</span>
          <h1>Set up your account.</h1>
          <p>Choose a password to activate your school workspace account.</p>
        </div>
        <div className="quote">“The operating system thoughtful schools deserve.”</div>
      </section>
      <section className="auth-panel">
        <form className="login-card" onSubmit={submit}>
          <span className="eyebrow">Complete registration</span>
          <h2>Create your password</h2>
          {invalid
            ? <div className="alert">This invite link is missing or malformed — ask your administrator to resend it.</div>
            : <p>Enter your details and choose a secure password.</p>}
          {error && <div className="alert">{error}</div>}
          {!invalid && (
            <>
              <div className="form-grid">
                <label>First name
                  <input required value={form.first_name} autoComplete="given-name"
                    onChange={e => setForm({ ...form, first_name: e.target.value })} />
                </label>
                <label>Last name
                  <input required value={form.last_name} autoComplete="family-name"
                    onChange={e => setForm({ ...form, last_name: e.target.value })} />
                </label>
              </div>
              <label>Password
                <input required type="password" minLength={8} autoComplete="new-password" value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  placeholder="At least 8 characters" />
              </label>
              <label>Confirm password
                <input required type="password" autoComplete="new-password" value={form.confirm}
                  onChange={e => setForm({ ...form, confirm: e.target.value })} />
              </label>
              <button className="primary full" disabled={busy}>
                {busy ? 'Activating…' : 'Activate account'}
              </button>
            </>
          )}
          <a className="ghost" href="/login" style={{ alignSelf: 'center' }}>← Back to sign in</a>
        </form>
      </section>
    </main>
  )
}
