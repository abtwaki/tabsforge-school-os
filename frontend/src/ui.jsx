import React, { useEffect, useState } from 'react'
import { get } from './api'
import { title } from './auth'

export function BrandMark({ small }) {
  return <img src="/logo-mark.png" alt="TabsForge" className={small ? 'brand-mark small' : 'brand-mark'} />
}

export function PageHead({ title: heading, subtitle, action }) {
  return (
    <div className="page-head">
      <div>
        <span className="eyebrow">TabsForge workspace</span>
        <h1>{heading}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Empty({ title: heading, hint, onAdd }) {
  const body = (
    <>
      <span>＋</span>
      <strong>{heading}</strong>
      <small>{hint || 'Add your first record to get started.'}</small>
      {onAdd && <em className="empty-cta">Click to add</em>}
    </>
  )
  if (!onAdd) return <div className="empty">{body}</div>
  return <button type="button" className="empty clickable" onClick={onAdd}>{body}</button>
}

export function Modal({ title: heading, close, children, wide }) {
  return (
    <div className="modal-backdrop" onMouseDown={close}>
      <section className={wide ? 'modal wide' : 'modal'} onMouseDown={e => e.stopPropagation()}>
        <header>
          <h2>{heading}</h2>
          <button onClick={close}>×</button>
        </header>
        {children}
      </section>
    </div>
  )
}

export function Alert({ children, kind }) {
  if (!children) return null
  return <div className={kind ? `alert ${kind}` : 'alert'}>{children}</div>
}

/** Generic list loader. Returns [rows, setRows, loading, error, reload]. */
export function useModule(name, params = '') {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = () => {
    setLoading(true)
    setError('')
    get(`/${name}/?page_size=200${params}`)
      .then(d => setRows(d.results || d))
      .catch(e => { setRows([]); setError(e.message) })
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [name, params])
  return [rows, setRows, loading, error, load]
}

export const money = v =>
  `₦${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`

export const fmtDate = v => (v ? new Date(v).toLocaleDateString() : '—')

export const statusBadge = s => (
  <span className={`badge st-${s}`}>{title(s)}</span>
)
