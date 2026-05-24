const DISPLAY_MODE_STORAGE_KEY = 'display_mode'

export const DISPLAY_MODE_EVENT = 'display-mode-change'

const normalizeDisplayMode = (mode) => (mode === 'mobile' ? 'mobile' : 'desktop')

export const getPreferredDisplayMode = () => {
  const savedMode = localStorage.getItem(DISPLAY_MODE_STORAGE_KEY)
  if (savedMode === 'mobile' || savedMode === 'desktop') return savedMode
  return document.documentElement.classList.contains('mobile-mode') ? 'mobile' : 'desktop'
}

export const applyDisplayMode = (mode = getPreferredDisplayMode(), options = {}) => {
  const htmlEl = document.documentElement
  const bodyEl = document.body
  const resolvedMode = normalizeDisplayMode(mode)
  const mobileMode = resolvedMode === 'mobile'

  htmlEl.classList.toggle('mobile-mode', mobileMode)
  bodyEl?.classList.toggle('mobile-mode', mobileMode)

  if (options.persist !== false) {
    localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, resolvedMode)
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(DISPLAY_MODE_EVENT, {
      detail: { mode: resolvedMode }
    }))
  }

  return resolvedMode
}

export const toggleDisplayMode = (options = {}) => {
  const nextMode = getPreferredDisplayMode() === 'mobile' ? 'desktop' : 'mobile'
  return applyDisplayMode(nextMode, options)
}
