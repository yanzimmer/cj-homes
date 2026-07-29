import { defineStore } from 'pinia'
import { authApi } from '../api'
import { clearAuthStorage, getStoredAuth, saveAuthSession } from '../utils/authStorage'

export const useAuthStore = defineStore('auth', {
  state: () => {
    const stored = getStoredAuth()
    return {
      token: stored.token,
      user: stored.user,
      sessionId: stored.sessionId,
      totpRequired: false,
      recoveryCodeUsed: false,
      recoveryCodesRemaining: null,
      loading: false,
      error: null
    }
  },
  
  getters: {
    isAuthenticated: (state) => !!state.token
  },
  
  actions: {
    async login(username, password, remember = true, totpCode = '') {
      this.loading = true
      this.error = null
      
      try {
        const response = await authApi.login({
          username,
          password,
          totp_code: totpCode,
        })
        
        this.token = response.data.token
        this.user = {
          username: response.data.username,
          fullName: response.data.full_name
        }
        
        this.sessionId = response.data.session_id || null
        this.totpRequired = false
        this.recoveryCodeUsed = response.data.recovery_code_used === true
        this.recoveryCodesRemaining = response.data.recovery_codes_remaining
        saveAuthSession(
          { token: this.token, user: this.user, sessionId: this.sessionId },
          remember,
        )
        
        return true
      } catch (error) {
        const code = error?.response?.data?.code
        if (['AUTH_TOTP_REQUIRED', 'AUTH_TOTP_INVALID', 'AUTH_TOTP_LOCKED'].includes(code)) {
          this.totpRequired = true
        }
        this.error = error.response?.data?.error || '登录失败，请检查网络连接'
        return false
      } finally {
        this.loading = false
      }
    },
    
    logout() {
      this.token = null
      this.user = null
      this.sessionId = null
      this.totpRequired = false
      this.recoveryCodeUsed = false
      this.recoveryCodesRemaining = null
      clearAuthStorage()
    }
  }
})
