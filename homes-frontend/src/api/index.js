import axios from 'axios'
import router from '../router'
import { ElMessage } from 'element-plus'

// API 鍩虹鍦板潃锛氫紭鍏堣鍙栫幆澧冨彉閲忥紝鍥為€€鍒版湰鍦伴粯璁ゅ湴鍧€
const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api'

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
        ElMessage.error('鐧诲綍鐘舵€佸凡杩囨湡锛岃閲嶆柊鐧诲綍')
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
  getRoom: (roomId) => apiClient.get(`/rooms/${roomId}`),
  getRoomMeterImage: (roomId, type) => apiClient.get(`/rooms/${roomId}/meter-image?type=${type}`),
  addRoom: (roomData) => apiClient.post('/rooms', roomData),
  updateRoom: (roomId, roomData) => apiClient.put(`/rooms/${roomId}`, roomData),
  deleteRoom: (roomId) => apiClient.delete(`/rooms/${roomId}`),
  checkoutRoom: (roomNo) => apiClient.post(`/rooms/${roomNo}/checkout`),
  getRoomTenants: (roomNo) => apiClient.get(`/rooms/${roomNo}/tenants`)
}

// 绉熸埛绠＄悊API
export const tenantsApi = {
  listTenants: (params = {}) => apiClient.get('/tenants', { params }),
  addTenant: (tenantData) => apiClient.post('/tenants', tenantData),
  updateTenant: (tenantId, tenantData) => apiClient.put(`/tenants/${tenantData.id_card}`, tenantData),
  deleteTenant: (idCard) => apiClient.delete(`/tenants/${encodeURIComponent(idCard)}`),
  checkoutTenant: (idCard) => apiClient.post(`/tenants/${idCard}/checkout`)
}

// OCR API
export const ocrApi = {
  ocrIdCard: (file, side = 'front') => {
    const formData = new FormData()
    formData.append('image', file)
    formData.append('side', side)
    return apiClient.post('/ocr/idcard', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  ocrIdCardByUrl: (imageUrl, side = 'front') => apiClient.post('/ocr/idcard/url', {
    image_url: imageUrl,
    side
  })
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
  addRepairRecord: (recordData) => apiClient.post('/repair-records', recordData),
  updateRepairRecord: (recordId, recordData) => apiClient.put(`/repair-records/${recordId}`, recordData),
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

export const systemApi = {
  exportData: () => apiClient.get('/system/export', { responseType: 'blob' }),
  importData: (fileOrUrl) => {
    if (typeof fileOrUrl === 'string') {
      return apiClient.post('/system/import', { file_url: fileOrUrl }, {
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
  createProcurement: (data) => apiClient.post('/procurements', data),
  updateProcurement: (id, data) => apiClient.put(`/procurements/${id}`, data),
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
export default apiClient






