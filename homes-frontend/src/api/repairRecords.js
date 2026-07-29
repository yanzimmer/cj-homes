import axios from 'axios'
import router from '../router'
import { ElMessage } from 'element-plus'
import { clearAuthStorage, getStoredToken } from '../utils/authStorage'

// API 基础地址：优先读取环境变量，回退到本地默认地址
const API_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

const SESSION_ERROR_CODES = new Set([
  'AUTH_TOKEN_MISSING',
  'AUTH_TOKEN_INVALID',
  'AUTH_TOKEN_EXPIRED',
  'AUTH_SESSION_INVALID',
  'AUTH_SESSION_REVOKED',
  'AUTH_SESSION_REPLACED'
])

// 请求拦截器添加token
apiClient.interceptors.request.use(
  config => {
    const token = getStoredToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器：处理 401 未授权，清理登录状态并跳转登录页
apiClient.interceptors.response.use(
  response => response,
  error => {
    const status = error?.response?.status
    const code = error?.response?.data?.code
    if (status === 401 && SESSION_ERROR_CODES.has(code)) {
      clearAuthStorage()
      try {
        ElMessage.error(error?.response?.data?.error || '登录状态已过期，请重新登录')
      } catch (_) {}
      const current = router.currentRoute?.value
      if (!current || current.name !== 'Login') {
        router.push({ name: 'Login' })
      }
    }
    return Promise.reject(error)
  }
)

// 维修记录API
export const repairRecordsApi = {
  // 获取所有维修记录
  listRepairRecords: () => apiClient.get('/repair-records'),
  
  // 获取单个维修记录详情
  getRepairRecord: (recordId) => apiClient.get(`/repair-records/${recordId}`),
  
  // 添加维修记录
  addRepairRecord: (recordData) => apiClient.post('/repair-records', recordData),
  
  // 更新维修记录
  updateRepairRecord: (recordId, recordData) => apiClient.put(`/repair-records/${recordId}`, recordData),
  
  // 删除维修记录
  deleteRepairRecord: (recordId) => apiClient.delete(`/repair-records/${recordId}`),
  
  // 获取指定房间的维修记录
  getRoomRepairRecords: (roomNo) => apiClient.get(`/repair-records/room/${roomNo}`)
}

export default repairRecordsApi
