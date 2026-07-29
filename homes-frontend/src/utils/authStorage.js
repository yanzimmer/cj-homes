const AUTH_KEYS = ['token', 'user', 'session_id']

const clearStorage = (storage) => {
  AUTH_KEYS.forEach(key => storage.removeItem(key))
}

const activeStorage = () => {
  if (sessionStorage.getItem('token')) return sessionStorage
  if (localStorage.getItem('token')) return localStorage
  return null
}

export const getStoredToken = () => activeStorage()?.getItem('token') || null

export const getStoredAuth = () => {
  const storage = activeStorage()
  if (!storage) return { token: null, user: null, sessionId: null }

  let user = null
  try {
    user = JSON.parse(storage.getItem('user') || 'null')
  } catch (_) {}
  return {
    token: storage.getItem('token') || null,
    user,
    sessionId: storage.getItem('session_id') || null,
  }
}

export const saveAuthSession = ({ token, user, sessionId }, remember) => {
  clearStorage(localStorage)
  clearStorage(sessionStorage)
  const storage = remember ? localStorage : sessionStorage
  storage.setItem('token', token)
  storage.setItem('user', JSON.stringify(user))
  if (sessionId) storage.setItem('session_id', sessionId)
}

export const updateStoredToken = (token) => {
  const storage = activeStorage()
  if (storage && token) storage.setItem('token', token)
}

export const clearAuthStorage = () => {
  clearStorage(localStorage)
  clearStorage(sessionStorage)
}
