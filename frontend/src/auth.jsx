import React, { createContext, useContext, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { get, post } from './api'

const AuthContext = createContext(null)

export const ROLE_LABELS = {
  super_admin: 'Super Admin',
  group_owner: 'Group Owner',
  school_admin: 'School Admin',
  principal: 'Principal',
  vice_principal: 'Vice Principal',
  admissions_officer: 'Admissions Officer',
  teacher: 'Teacher',
  form_teacher: 'Form Teacher',
  exam_officer: 'Exam Officer',
  hr_admin: 'HR Admin',
  librarian: 'Librarian',
  staff: 'Staff',
  accountant: 'Accountant',
  parent: 'Parent',
  student: 'Student',
  guest: 'Guest',
}

export const title = value =>
  String(value || '')
    .replaceAll('-', ' ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())

export const roleLabel = role => ROLE_LABELS[role] || title(role)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() =>
    JSON.parse(localStorage.getItem('tabsforge_user') || 'null'))
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem('tabsforge_token')) return setReady(true)
    get('/auth/me/')
      .then(data => {
        const u = { ...user, ...data }
        setUser(u)
        localStorage.setItem('tabsforge_user', JSON.stringify(u))
      })
      .catch(() => {})
      .finally(() => setReady(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = async credentials => {
    const data = await post('/auth/login/', credentials)
    const token = data.token || data.key || data.access
    if (!token) throw new Error('The server did not return an authentication token.')
    const u = data.user
    localStorage.setItem('tabsforge_token', token)
    localStorage.setItem('tabsforge_user', JSON.stringify(u))
    setUser(u)
    return u
  }

  const refresh = async () => {
    const data = await get('/auth/me/')
    const u = { ...user, ...data }
    setUser(u)
    localStorage.setItem('tabsforge_user', JSON.stringify(u))
    return u
  }

  const logout = () => {
    post('/auth/logout/', {}).catch(() => {})
    localStorage.removeItem('tabsforge_token')
    localStorage.removeItem('tabsforge_user')
    localStorage.removeItem('tabsforge_stay')
    localStorage.removeItem('tabsforge_login_at')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, refresh, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

export function Protected({ children }) {
  const { user, ready } = useAuth()
  if (!ready) return <div className="loading">Loading workspace…</div>
  return user ? children : <Navigate to="/login" replace />
}
