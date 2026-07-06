export const frontendVersionInfo = Object.freeze({
  name: 'homes-frontend',
  version: typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.0.0',
  commit: typeof __APP_COMMIT__ !== 'undefined' ? __APP_COMMIT__ : 'unknown',
  buildTime: typeof __APP_BUILD_TIME__ !== 'undefined' ? __APP_BUILD_TIME__ : '',
})

export const formatVersionText = (version, fallback = '未知') => {
  const text = String(version || '').trim()
  return text ? `v${text}` : fallback
}
