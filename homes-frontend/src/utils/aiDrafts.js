const AI_DRAFT_PREFIX = 'homes-ai-draft:'

export const AI_ASSISTANT_TARGETS = {
  tenant: '/dashboard/tenants',
  room: '/dashboard/rooms',
  repair: '/dashboard/repair-records',
  procurement: '/dashboard/procurement',
  warehouse: '/dashboard/warehouse',
  move: '/dashboard/moves',
  contract_template: '/dashboard/contract-templates',
}

export const saveAiDraft = (type, payload) => {
  if (!type) return
  sessionStorage.setItem(`${AI_DRAFT_PREFIX}${type}`, JSON.stringify(payload || {}))
}

export const readAiDraft = (type) => {
  if (!type) return null
  const raw = sessionStorage.getItem(`${AI_DRAFT_PREFIX}${type}`)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch (_) {
    return null
  }
}

export const consumeAiDraft = (type) => {
  const key = `${AI_DRAFT_PREFIX}${type}`
  const value = readAiDraft(type)
  sessionStorage.removeItem(key)
  return value
}

export const mapRouteToAssistantType = (path) => {
  if (path.startsWith('/dashboard/tenants')) return 'tenant'
  if (path.startsWith('/dashboard/rooms')) return 'room'
  if (path.startsWith('/dashboard/repair-records')) return 'repair'
  if (path.startsWith('/dashboard/procurement')) return 'procurement'
  if (path.startsWith('/dashboard/warehouse')) return 'warehouse'
  if (path.startsWith('/dashboard/moves')) return 'move'
  if (path.startsWith('/dashboard/contract-templates')) return 'contract_template'
  return 'tenant'
}
