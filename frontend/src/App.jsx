import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, Protected, useAuth } from './auth'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Register from './pages/Register'
import Shell, { roleHome } from './pages/Shell'

function Home() {
  const { user, ready } = useAuth()
  if (!ready) return <div className="loading">Loading…</div>
  if (user) return <Navigate to={`/${roleHome(user.role)}`} replace />
  return <Login />
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/*" element={<Protected><Shell /></Protected>} />
      </Routes>
    </AuthProvider>
  )
}

export default App
