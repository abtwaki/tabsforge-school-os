/* Offline queue for attendance marks (and future homework submissions).
 *
 * Uses a tiny IndexedDB store so marks captured without connectivity are
 * persisted across reloads, then flushed to the API when the network
 * returns. The Attendance screen surfaces queue depth as a status badge. */

const DB_NAME = 'tabsforge-offline'
const STORE = 'queue'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function queueItem(kind, payload) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).add({ kind, payload, queued_at: new Date().toISOString() })
    tx.oncomplete = resolve
    tx.onerror = () => reject(tx.error)
  })
}

export async function listQueue() {
  try {
    const db = await openDb()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const req = tx.objectStore(STORE).getAll()
      req.onsuccess = () => resolve(req.result || [])
      req.onerror = () => reject(req.error)
    })
  } catch {
    return []
  }
}

export async function removeQueueItem(id) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).delete(id)
    tx.oncomplete = resolve
    tx.onerror = () => reject(tx.error)
  })
}

/** Flush queued items with a sender function; returns {sent, failed}. */
export async function flushQueue(send) {
  const items = await listQueue()
  let sent = 0
  let failed = 0
  for (const item of items) {
    try {
      await send(item)
      await removeQueueItem(item.id)
      sent += 1
    } catch {
      failed += 1
    }
  }
  return { sent, failed }
}
