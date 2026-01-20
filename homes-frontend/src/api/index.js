import axios from 'axios'
import router from '../router'
import { ElMessage } from 'element-plus'

// API 基础地址：优先读取环境变量，回退到本地默认地址
const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api'

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器添加token
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

// 响应拦截器：处理 401 未授权，清理登录状态并跳转登录页
apiClient.interceptors.response.use(
  response => {
    // 接收后端通过响应头返回的刷新令牌，实现“有活动就续期”
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
      // 清理本地存储的登录信息
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 友好提示
      try {
        ElMessage.error('登录状态已过期，请重新登录')
      } catch (_) {}
      // 避免在登录页重复跳转
      const current = router.currentRoute?.value
      if (!current || current.name !== 'Login') {
        router.push({ name: 'Login' })
      }
    }
    return Promise.reject(error)
  }
)

// 房间管理API
export const roomsApi = {
  listRooms: () => apiClient.get('/rooms'),
  addRoom: (roomData) => apiClient.post('/rooms', roomData),
  updateRoom: (roomId, roomData) => apiClient.put(`/rooms/${roomData.room_no}`, roomData),
  deleteRoom: (roomId) => apiClient.delete(`/rooms/${roomId}`),
  checkoutRoom: (roomNo) => apiClient.post(`/rooms/${roomNo}/checkout`),
  getRoomTenants: (roomNo) => apiClient.get(`/rooms/${roomNo}/tenants`)
}

// 租户管理API
export const tenantsApi = {
  listTenants: () => apiClient.get('/tenants'),
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
  }
}

// 搬迁管理API
export const movesApi = {
  listMoves: () => apiClient.get('/moves'),
  moveTenant: (moveData) => apiClient.post('/moves/tenant', moveData),
  deleteMove: (moveId) => apiClient.delete(`/moves/${moveId}`)
}

// 租期到期通知API
export const notifyApi = {
  getConfig: () => apiClient.get('/notification-config'),
  updateConfig: (configData) => apiClient.put('/notification-config', configData),
  testEmail: (payload) => apiClient.post('/test-email', payload),
  testSms: (payload) => apiClient.post('/test-sms', payload),
  sendNotification: (data) => apiClient.post('/notify/send', data),
  getHistory: (days = 30) => apiClient.get(`/notify/history?days=${days}`)
}

// 维修记录API
export const repairRecordsApi = {
  listRepairRecords: () => apiClient.get('/repair-records'),
  getRepairRecord: (recordId) => apiClient.get(`/repair-records/${recordId}`),
  addRepairRecord: (recordData) => apiClient.post('/repair-records', recordData),
  updateRepairRecord: (recordId, recordData) => apiClient.put(`/repair-records/${recordId}`, recordData),
  deleteRepairRecord: (recordId) => apiClient.delete(`/repair-records/${recordId}`),
  getRoomRepairRecords: (roomNo) => apiClient.get(`/repair-records/room/${roomNo}`)
}


// 合同模板API
export const contractTemplatesApi = {
  listTemplates: () => apiClient.get('/contract-templates'),
  getTemplate: (id) => apiClient.get(`/contract-templates/${id}`),
  addTemplate: (tplData) => apiClient.post('/contract-templates', tplData),
  updateTemplate: (id, tplData) => apiClient.put(`/contract-templates/${id}`, tplData),
  deleteTemplate: (id) => apiClient.delete(`/contract-templates/${id}`),
  // 级联删除：同时删除引用该模板的合同
  deleteTemplateCascade: (id) => apiClient.delete(`/contract-templates/${id}?cascade=true`),
  renderTemplate: (id, vars) => apiClient.post(`/contract-templates/${id}/render`, { vars })
}

// 合同档案API
export const contractsApi = {
  createContract: (templateId, vars) => apiClient.post('/contracts', { template_id: templateId, vars }),
  listContracts: (page = 1, pageSize = 10) => apiClient.get(`/contracts?page=${page}&page_size=${pageSize}`),
  getContract: (id) => apiClient.get(`/contracts/${id}`),
  updateContract: (id, vars) => apiClient.put(`/contracts/${id}`, { vars })
}

// 认证API（心跳校验/续期/登录）
export const authApi = {
  login: (credentials) => apiClient.post('/login', credentials),
  verifyToken: () => apiClient.get('/verify-token', { skipLoading: true })
}

export const systemApi = {
  exportData: () => apiClient.get('/system/export', { responseType: 'blob' }),
  importData: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/system/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000 // 导入可能需要较长时间
    })
  },
  resetSystem: () => apiClient.post('/system/reset'),
  seedData: () => apiClient.post('/system/seed')
}

export default apiClient