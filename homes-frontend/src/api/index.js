import axios from 'axios'
import router from '../router'
import { ElMessage } from 'element-plus'

// API 基础地址：优先读取环境变量，回退到本地默认地址
const API_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// 鍒涘缓axios瀹炰緥
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 璇锋眰鎷︽埅鍣ㄦ坊鍔爐oken
apiClient.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

apiClient.interceptors.response.use(
  response => {
    try {
      const newToken = response?.headers?.['x-refreshed-token'] || response?.headers?.['X-Refreshed-Token']
      if (newToken) {
        localStorage.setItem('token', newToken)
      }
    } catch (_) {}
    return response
  },
  error => {
    const status = error?.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 鍙嬪ソ鎻愮ず
      try {
        ElMessage.error('登录状态已过期，请重新登录')
      } catch (_) {}
      // 閬垮厤鍦ㄧ櫥褰曢〉閲嶅璺宠浆
      const current = router.currentRoute?.value
      if (!current || current.name !== 'Login') {
        router.push({ name: 'Login' })
      }
    }
    return Promise.reject(error)
  }
)

// 鎴块棿绠＄悊API
export const roomsApi = {
  listRooms: (params = {}) => apiClient.get('/rooms', { params }),
  getFeatureOptions: () => apiClient.get('/rooms/feature-options'),
  getRoom: (roomId) => apiClient.get(`/rooms/${roomId}`),
  getRoomMeterImage: (roomId, type) => apiClient.get(`/rooms/${roomId}/meter-image?type=${type}`),
  uploadRoomMeterImage: (roomId, type, file) => {
    const formData = new FormData()
    formData.append('type', type)
    formData.append('file', file)
    return apiClient.post(`/rooms/${roomId}/meter-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  addRoom: (roomData) => apiClient.post('/rooms', roomData),
  updateRoom: (roomId, roomData) => apiClient.put(`/rooms/${roomId}`, roomData),
  deleteRoom: (roomId) => apiClient.delete(`/rooms/${roomId}`),
  checkoutRoom: (roomNo) => apiClient.post(`/rooms/${encodeURIComponent(roomNo)}/checkout`),
  getRoomTenants: (roomNo) => apiClient.get(`/rooms/${roomNo}/tenants`),
  listSelfCheckinLinks: (roomId) => apiClient.get(`/self-checkin/rooms/${roomId}/links`),
  createSelfCheckinLink: (roomId) => apiClient.post(`/self-checkin/rooms/${roomId}/links`),
  disableSelfCheckinLink: (linkId) => apiClient.post(`/self-checkin/links/${linkId}/disable`),
  enableSelfCheckinLink: (linkId) => apiClient.post(`/self-checkin/links/${linkId}/enable`),
  deleteSelfCheckinLink: (linkId) => apiClient.delete(`/self-checkin/links/${linkId}`),
  listSelfCheckinSubmissions: (roomId) => apiClient.get(`/self-checkin/rooms/${roomId}/submissions`),
  approveSelfCheckinSubmission: (submissionId, payload = {}) => apiClient.post(`/self-checkin/submissions/${submissionId}/approve`, payload),
  rejectSelfCheckinSubmission: (submissionId, payload) => apiClient.post(`/self-checkin/submissions/${submissionId}/reject`, payload),
  deleteSelfCheckinSubmission: (submissionId) => apiClient.delete(`/self-checkin/submissions/${submissionId}`),
}

// 绉熸埛绠＄悊API
export const tenantsApi = {
  listTenants: (params = {}) => apiClient.get('/tenants', { params }),
  addTenant: (tenantData) => apiClient.post('/tenants', tenantData),
  updateTenant: (tenantId, tenantData) => {
    const tenantRecordId = tenantData?.id ?? tenantId
    const idCard = String(tenantData?.id_card || '').trim()
    if (!idCard && tenantRecordId !== undefined && tenantRecordId !== null && tenantRecordId !== '') {
      return apiClient.put(`/tenants/by-id/${tenantRecordId}`, tenantData)
    }
    return apiClient.put(`/tenants/${encodeURIComponent(idCard || tenantId || '')}`, tenantData)
  },
  deleteTenant: (tenant) => {
    if (tenant && typeof tenant === 'object') {
      if ((!tenant.id_card || !String(tenant.id_card).trim()) && tenant.id !== undefined && tenant.id !== null && tenant.id !== '') {
        return apiClient.delete(`/tenants/by-id/${tenant.id}`)
      }
      return apiClient.delete(`/tenants/${encodeURIComponent(tenant.id_card || '')}`)
    }
    return apiClient.delete(`/tenants/${encodeURIComponent(tenant)}`)
  },
  checkoutTenant: (tenant) => {
    if (tenant && typeof tenant === 'object') {
      if (tenant.id !== undefined && tenant.id !== null && tenant.id !== '') {
        return apiClient.post(`/tenants/by-id/${tenant.id}/checkout`)
      }
      return apiClient.post(`/tenants/${encodeURIComponent(tenant.id_card || '')}/checkout`)
    }
    return apiClient.post(`/tenants/${encodeURIComponent(tenant)}/checkout`)
  },
  createAiDraft: (payload) => apiClient.post('/tenants/ai-draft', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  }),
  recognizeIdCard: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/tenants/recognize-id-card', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

// 鎼縼绠＄悊API
export const movesApi = {
  listMoves: () => apiClient.get('/moves'),
  moveTenant: (moveData) => apiClient.post('/moves/tenant', moveData),
  deleteMove: (moveId) => apiClient.delete(`/moves/${moveId}`)
}

// 绉熸湡鍒版湡閫氱煡API
export const notifyApi = {
  getConfig: () => apiClient.get('/notification-config'),
  updateConfig: (configData) => apiClient.put('/notification-config', configData),
  testEmail: (payload) => apiClient.post('/test-email', payload),
  testSms: (payload) => apiClient.post('/test-sms', payload),
  sendNotification: (data) => apiClient.post('/notify/send', data),
  getHistory: (days = 30) => apiClient.get(`/notify/history?days=${days}`)
}

// 缁翠慨璁板綍API
export const repairRecordsApi = {
  listRepairRecords: (params = {}) => apiClient.get('/repair-records', { params }),
  getRepairRecord: (recordId) => apiClient.get(`/repair-records/${recordId}`),
  createAiDraft: (payload) => apiClient.post('/repair-records/ai-draft', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  }),
  addRepairRecord: (recordData) => apiClient.post('/repair-records', recordData),
  updateRepairRecord: (recordId, recordData) => apiClient.put(`/repair-records/${recordId}`, recordData),
  listInventoryOptions: () => apiClient.get('/repair-records/inventory-options'),
  uploadRepairImage: (recordId, file, onProgress, imageType = 'before') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('type', imageType)
    return apiClient.post(`/repair-records/${recordId}/image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress) return
        const total = evt?.total || 0
        if (!total) return
        const percent = Math.floor((evt.loaded * 100) / total)
        onProgress(percent)
      }
    })
  },
  deleteRepairRecord: (recordId) => apiClient.delete(`/repair-records/${recordId}`),
  getRoomRepairRecords: (roomNo) => apiClient.get(`/repair-records/room/${roomNo}`)
}


// 鍚堝悓妯℃澘API
export const contractTemplatesApi = {
  listTemplates: () => apiClient.get('/contract-templates'),
  getTemplate: (id) => apiClient.get(`/contract-templates/${id}`),
  addTemplate: (tplData) => apiClient.post('/contract-templates', tplData),
  updateTemplate: (id, tplData) => apiClient.put(`/contract-templates/${id}`, tplData),
  deleteTemplate: (id) => apiClient.delete(`/contract-templates/${id}`),
  deleteTemplateCascade: (id) => apiClient.delete(`/contract-templates/${id}?cascade=true`),
  renderTemplate: (id, vars) => apiClient.post(`/contract-templates/${id}/render`, { vars })
}

// 鍚堝悓妗ｆAPI
export const contractsApi = {
  createContract: (templateId, vars) => apiClient.post('/contracts', { template_id: templateId, vars }),
  listContracts: (page = 1, pageSize = 10) => apiClient.get(`/contracts?page=${page}&page_size=${pageSize}`),
  getContract: (id) => apiClient.get(`/contracts/${id}`),
  updateContract: (id, vars) => apiClient.put(`/contracts/${id}`, { vars })
}

export const authApi = {
  login: (credentials) => apiClient.post('/login', credentials),
  verifyToken: () => apiClient.get('/verify-token', { skipLoading: true })
}

export const dashboardApi = {
  getStats: () => apiClient.get('/dashboard/stats')
}

export const systemApi = {
  exportData: () => apiClient.get('/system/export', { responseType: 'blob' }),
  getImportRollbackStatus: () => apiClient.get('/system/import-rollback-status'),
  getSnapshotTaskStatus: () => apiClient.get('/system/snapshot-task-status'),
  listSnapshots: () => apiClient.get('/system/snapshots'),
  createSnapshot: () => apiClient.post('/system/snapshots'),
  restoreSnapshot: (snapshotId) => apiClient.post(`/system/snapshots/${snapshotId}/restore`),
  deleteSnapshot: (snapshotId) => apiClient.delete(`/system/snapshots/${snapshotId}`),
  rollbackLastImport: () => apiClient.post('/system/import-rollback'),
  getRoomFeatureOptions: () => apiClient.get('/system/room-feature-options'),
  updateRoomFeatureOptions: (payload) => apiClient.put('/system/room-feature-options', payload),
  getUtilityAccountOptions: () => apiClient.get('/system/utility-account-options'),
  updateUtilityAccountOptions: (payload) => apiClient.put('/system/utility-account-options', payload),
  getOcrSettings: () => apiClient.get('/system/ocr-settings'),
  updateOcrSettings: (payload) => apiClient.put('/system/ocr-settings', payload),
  getAiSettings: () => apiClient.get('/system/ai-settings'),
  updateAiSettings: (payload) => apiClient.put('/system/ai-settings', payload),
  testAiSettings: (payload) => apiClient.post('/system/ai-settings/test', payload),
  listAiModels: (payload) => apiClient.post('/system/ai-settings/models', payload),
  getAiSwitchStatus: () => apiClient.get('/system/ai-settings/switch-status'),
  importData: (fileOrUrl) => {
    if (typeof fileOrUrl === 'string') {
      return apiClient.post('/system/import', { file_url: fileOrUrl }, {
        timeout: 60000 // 导入可能需要较长时间
      })
    }
    if (fileOrUrl && typeof fileOrUrl === 'object' && !(fileOrUrl instanceof File)) {
      return apiClient.post('/system/import', fileOrUrl, {
        timeout: 60000 // 导入可能需要较长时间
      })
    }
    const formData = new FormData()
    formData.append('file', fileOrUrl)
    return apiClient.post('/system/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000 // 导入可能需要较长时间
    })
  },
  resetSystem: () => apiClient.post('/system/reset'),
  seedData: () => apiClient.post('/system/seed')
}

// 閲囪喘绠＄悊API
export const procurementApi = {
  listProcurements: (params) => apiClient.get('/procurements', { params }),
  createAiDraft: (payload) => apiClient.post('/procurements/ai-draft', payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  }),
  createProcurement: (data) => apiClient.post('/procurements', data),
  updateProcurement: (id, data) => apiClient.put(`/procurements/${id}`, data),
  updateProcurementImages: (id, data) => apiClient.put(`/procurements/${id}/images`, data),
  uploadProcurementImage: (id, file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post(`/procurements/${id}/image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress) return
        const total = evt?.total || 0
        if (!total) return
        const percent = Math.floor((evt.loaded * 100) / total)
        onProgress(percent)
      }
    })
  },
  deleteProcurement: (id) => apiClient.delete(`/procurements/${id}`)
}

export const utilityBillsApi = {
  getSummary: (year) => apiClient.get('/utility-bills/summary', { params: { year } }),
  getAccountOptions: () => apiClient.get('/utility-bills/account-options'),
  saveBill: (data) => apiClient.post('/utility-bills', data),
  updateBill: (id, data) => apiClient.put(`/utility-bills/${id}`, data),
  updateBillImages: (id, data) => apiClient.put(`/utility-bills/${id}/images`, data),
  deleteBill: (id) => apiClient.delete(`/utility-bills/${id}`),
}

export const rentLedgerApi = {
  getSummary: (year, status = '') => apiClient.get('/rent-ledger/summary', { params: { year, status } }),
  sync: (year) => apiClient.post('/rent-ledger/sync', { year }),
  updateEntry: (id, data) => apiClient.put(`/rent-ledger/${id}`, data),
}

export const businessEntryLinksApi = {
  getLink: (businessType) => apiClient.get(`/public-entry-links/${businessType}`),
  createLink: (businessType) => apiClient.post(`/public-entry-links/${businessType}`),
  disableLink: (linkId) => apiClient.post(`/public-entry-links/${linkId}/disable`),
  enableLink: (linkId) => apiClient.post(`/public-entry-links/${linkId}/enable`),
  deleteLink: (linkId) => apiClient.delete(`/public-entry-links/${linkId}`),
}

// 搴撴埧鏁版嵁API
export const warehouseApi = {
  listItems: (params) => apiClient.get('/warehouse-items', { params }),
  getItem: (id) => apiClient.get(`/warehouse-items/${id}`),
  createItem: (data) => apiClient.post('/warehouse-items', data),
  updateItem: (id, data) => apiClient.put(`/warehouse-items/${id}`, data),
  deleteItem: (id) => apiClient.delete(`/warehouse-items/${id}`)
}


export const uploadApi = {
  initChunkUpload: (data) => apiClient.post('/uploads/chunk/init', data),
  uploadChunk: (uploadId, chunkBlob, index, totalChunks, onProgress) => {
    const formData = new FormData()
    formData.append('chunk', chunkBlob)
    formData.append('index', String(index))
    formData.append('total_chunks', String(totalChunks))
    return apiClient.post(`/uploads/chunk/${uploadId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress) return
        onProgress(evt)
      }
    })
  },
  getChunkUploadStatus: (uploadId) => apiClient.get(`/uploads/chunk/${uploadId}/status`),
  completeChunkUpload: (uploadId) => apiClient.post(`/uploads/chunk/${uploadId}/complete`)
}

export const publicSelfCheckinApi = {
  getForm: (token) => apiClient.get(`/public/self-checkin/${token}`),
  getSubmissionStatus: (token, params) => apiClient.get(`/public/self-checkin/${token}/submission-status`, { params }),
  createAiDraft: (token, payload) => apiClient.post(`/public/self-checkin/${token}/ai-draft`, payload, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  }),
  recognizeIdCard: (token, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post(`/public/self-checkin/${token}/recognize-id-card`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  submit: (token, payload) => apiClient.post(`/public/self-checkin/${token}/submit`, payload),
}

export const publicBusinessEntryApi = {
  getForm: (businessType, token) => apiClient.get(`/public-entry/${businessType}/${token}`),
  uploadImage: (businessType, token, file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post(`/public-entry/${businessType}/${token}/upload-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress) return
        onProgress(evt)
      },
    })
  },
  submit: (businessType, token, payload) => apiClient.post(`/public-entry/${businessType}/${token}/submit`, payload),
}
export default apiClient
