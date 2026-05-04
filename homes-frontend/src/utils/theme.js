const THEME_STORAGE_KEY = 'theme'

export const getPreferredTheme = () => {
  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY)
  if (savedTheme === 'dark' || savedTheme === 'light') return savedTheme
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  return prefersDark ? 'dark' : 'light'
}

export const applyTheme = (theme = getPreferredTheme(), options = {}) => {
  const htmlEl = document.documentElement
  if (options.transition) {
    htmlEl.classList.add('theme-transitioning')
  }
  htmlEl.classList.toggle('dark', theme === 'dark')
  localStorage.setItem(THEME_STORAGE_KEY, theme)
  if (options.transition) {
    requestAnimationFrame(() => {
      htmlEl.classList.remove('theme-transitioning')
    })
  }
  return theme
}

export const toggleTheme = (options = {}) => {
  const nextTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark'
  return applyTheme(nextTheme, options)
}
