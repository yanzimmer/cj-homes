const THEME_STORAGE_KEY = 'theme'
const THEME_MODE_STORAGE_KEY = 'theme_mode'
const AUTO_LIGHT_START_HOUR = 7
const AUTO_DARK_START_HOUR = 19

const normalizeTheme = (theme) => (theme === 'dark' ? 'dark' : 'light')

const getStoredTheme = () => {
  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY)
  return savedTheme === 'dark' || savedTheme === 'light' ? savedTheme : ''
}

export const getThemeMode = () => {
  const savedMode = localStorage.getItem(THEME_MODE_STORAGE_KEY)
  if (savedMode === 'auto' || savedMode === 'manual') return savedMode
  return getStoredTheme() ? 'manual' : 'auto'
}

export const getAutoTheme = (now = new Date()) => {
  const hour = now.getHours()
  return hour >= AUTO_LIGHT_START_HOUR && hour < AUTO_DARK_START_HOUR ? 'light' : 'dark'
}

export const getPreferredTheme = () => {
  const mode = getThemeMode()
  if (mode === 'auto') return getAutoTheme()
  return getStoredTheme() || getAutoTheme()
}

export const applyTheme = (theme = getPreferredTheme(), options = {}) => {
  const htmlEl = document.documentElement
  const resolvedTheme = normalizeTheme(theme)
  if (options.transition) {
    htmlEl.classList.add('theme-transitioning')
  }
  htmlEl.classList.toggle('dark', resolvedTheme === 'dark')
  if (options.persist !== false) {
    localStorage.setItem(THEME_STORAGE_KEY, resolvedTheme)
  }
  if (options.mode === 'auto' || options.mode === 'manual') {
    localStorage.setItem(THEME_MODE_STORAGE_KEY, options.mode)
  }
  if (options.transition) {
    requestAnimationFrame(() => {
      htmlEl.classList.remove('theme-transitioning')
    })
  }
  return resolvedTheme
}

export const setManualTheme = (theme, options = {}) => {
  const resolvedTheme = normalizeTheme(theme)
  localStorage.setItem(THEME_MODE_STORAGE_KEY, 'manual')
  return applyTheme(resolvedTheme, { ...options, mode: 'manual', persist: true })
}

export const setThemeMode = (mode, options = {}) => {
  const resolvedMode = mode === 'manual' ? 'manual' : 'auto'
  const nextTheme = resolvedMode === 'auto'
    ? getAutoTheme(options.date)
    : normalizeTheme(options.theme || getStoredTheme() || (document.documentElement.classList.contains('dark') ? 'dark' : 'light'))
  localStorage.setItem(THEME_MODE_STORAGE_KEY, resolvedMode)
  return applyTheme(nextTheme, { ...options, mode: resolvedMode, persist: true })
}

export const toggleTheme = (options = {}) => {
  const nextTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark'
  return setManualTheme(nextTheme, options)
}
