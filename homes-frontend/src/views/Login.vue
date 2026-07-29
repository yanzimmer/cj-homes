<template>
  <div class="login-container" id="login-page">
    <div class="theme-switch">
      <ThemeModeSwitch floating />
    </div>
    <div class="background-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>
    <div class="dark-overlay"></div>
    
    <div class="login-card glass-effect">
      <div class="card-left">
        <div class="card-left-overlay"></div>
        <div class="brand-content">
          <div class="logo-circle">
            <el-icon class="logo-icon"><House /></el-icon>
          </div>
          <h1 class="welcome-title">从江房屋登记系统</h1>
          <p class="welcome-desc">仅限授权人员登录使用</p>
        </div>
        <div class="decoration-circles">
          <div class="circle c1"></div>
          <div class="circle c2"></div>
        </div>
      </div>

      <div class="card-right">
        <div class="form-header">
          <h2>{{ isResetMode ? '重置密码' : (totpStep ? '两步验证' : '账号登录') }}</h2>
          <p class="sub-text">{{ isResetMode ? '请输入您的安全口令以重置密码' : (totpStep ? '输入身份验证器动态码或恢复码' : '请输入您的账号密码以继续') }}</p>
        </div>

        <transition name="fade-slide" mode="out-in">
          <!-- 登录表单 -->
          <el-form v-if="!isResetMode" :model="loginForm" :rules="rules" ref="loginFormRef" class="custom-form" size="large">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" :prefix-icon="User" :disabled="totpStep" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" :disabled="totpStep" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item v-if="totpStep">
              <el-input
                v-model="loginForm.totpCode"
                placeholder="6 位动态码或恢复码"
                :prefix-icon="Key"
                autocomplete="one-time-code"
                maxlength="20"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            
            <div class="form-options">
              <el-checkbox v-model="rememberMe">记住我</el-checkbox>
              <span v-if="totpStep" class="back-link" @click="resetTotpStep">返回账号密码</span>
              <span v-else class="forgot-link" @click="switchToReset">忘记密码？</span>
            </div>

            <el-button type="primary" :loading="loading" class="submit-btn" @click="handleLogin">
              {{ totpStep ? '验证并登录' : '立即登录' }}
            </el-button>
          </el-form>

          <!-- 重置密码表单 -->
          <el-form v-else :model="forgotForm" :rules="forgotRules" ref="forgotFormRef" class="custom-form" size="large">
            <el-form-item style="display:none" prop="username">
              <el-input v-model="forgotForm.username" />
            </el-form-item>
            <el-form-item prop="answer">
              <el-input v-model="forgotForm.answer" placeholder="安全口令" :prefix-icon="Key" />
            </el-form-item>
            <el-form-item prop="newPassword">
              <el-input v-model="forgotForm.newPassword" type="password" show-password placeholder="新密码" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item prop="confirmPassword">
              <el-input v-model="forgotForm.confirmPassword" type="password" show-password placeholder="确认新密码" :prefix-icon="Lock" />
            </el-form-item>

            <div class="form-options center">
              <span class="back-link" @click="switchToLogin">返回登录</span>
            </div>

            <el-button type="primary" :loading="resetLoading" class="submit-btn" @click="submitForgot">
              确认重置
            </el-button>
          </el-form>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Key, House } from '@element-plus/icons-vue'
import axios from 'axios'
import ThemeModeSwitch from '../components/ThemeModeSwitch.vue'
import { applyDisplayMode } from '../utils/displayMode'
import { applyTheme, getPreferredTheme } from '../utils/theme'

const router = useRouter()
const authStore = useAuthStore()

const detectLoginDisplayMode = () => {
  const ua = navigator.userAgent || ''
  const mobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)
  const narrowScreen = window.matchMedia('(max-width: 768px)').matches
  const touchTablet = window.matchMedia('(pointer: coarse) and (max-width: 1024px)').matches
  return mobileUA || narrowScreen || touchTablet ? 'mobile' : 'desktop'
}

const syncLoginDisplayMode = () => {
  applyDisplayMode(detectLoginDisplayMode())
}

onMounted(() => {
  applyTheme(getPreferredTheme(), { persist: true })
  syncLoginDisplayMode()
  window.addEventListener('resize', syncLoginDisplayMode)
  window.addEventListener('orientationchange', syncLoginDisplayMode)
})

onUnmounted(() => {
  window.removeEventListener('resize', syncLoginDisplayMode)
  window.removeEventListener('orientationchange', syncLoginDisplayMode)
})

const loginFormRef = ref(null)
const loading = computed(() => authStore.loading)
const loginForm = reactive({
  username: '',
  password: '',
  totpCode: '',
})
const rememberMe = ref(true)
const totpStep = ref(false)

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  if (totpStep.value && !loginForm.totpCode.trim()) {
    ElMessage.warning('请输入身份验证器动态码或恢复码')
    return
  }
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      const wasTotpStep = totpStep.value
      const success = await authStore.login(
        loginForm.username,
        loginForm.password,
        rememberMe.value,
        loginForm.totpCode.trim(),
      )
      if (success) {
        if (authStore.recoveryCodeUsed) {
          ElMessage.warning(`已使用一次性恢复码，剩余 ${authStore.recoveryCodesRemaining} 个`)
        } else {
          ElMessage.success('登录成功')
        }
        router.push('/dashboard')
      } else if (authStore.totpRequired && !wasTotpStep) {
        totpStep.value = true
        loginForm.totpCode = ''
      } else if (authStore.error) {
        ElMessage.error(authStore.error)
      }
    }
  })
}

const resetTotpStep = () => {
  totpStep.value = false
  authStore.totpRequired = false
  loginForm.totpCode = ''
}

// 找回密码逻辑
const isResetMode = ref(false)
const forgotFormRef = ref(null)
const resetLoading = ref(false)
const forgotForm = reactive({
  username: '',
  answer: '',
  newPassword: '',
  confirmPassword: ''
})

const validateConfirm = (rule, value, callback) => {
  if (value !== forgotForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const forgotRules = {
  answer: [{ required: true, message: '请输入安全口令', trigger: 'blur' }],
  newPassword: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

const switchToReset = () => {
  Object.assign(forgotForm, {
    username: loginForm.username || 'admin',
    answer: '',
    newPassword: '',
    confirmPassword: ''
  })
  isResetMode.value = true
}

const switchToLogin = () => {
  isResetMode.value = false
}

const submitForgot = async () => {
  if (!forgotFormRef.value) return
  await forgotFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const API_URL = import.meta.env.VITE_API_BASE_URL || '/api'
      const payload = {
        username: forgotForm.username,
        answer: forgotForm.answer,
        new_password: forgotForm.newPassword
      }
      resetLoading.value = true
      const resp = await axios.post(`${API_URL}/forgot-password`, payload)
      ElMessage.success(resp.data?.message || '密码重置成功')
      isResetMode.value = false
    } catch (e) {
      const msg = e.response?.data?.error || '重置失败，请检查输入'
      ElMessage.error(msg)
    } finally {
      resetLoading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 28%),
    radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.1), transparent 24%),
    linear-gradient(135deg, #f2f7fc 0%, #fbfdff 52%, #f1f8fb 100%);
  position: relative;
  overflow: hidden;
  z-index: 0;
}

.login-container::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #1a1a1a 0%, #000000 100%);
  opacity: 0;
  z-index: -1;
  transition: opacity 0.5s ease-in-out;
}

/* 动态背景形状 */
.background-shapes .shape {
  position: absolute;
  filter: blur(70px);
  z-index: 0;
  animation: float 22s infinite;
}
.shape-1 {
  top: -8%;
  left: -8%;
  width: 42vw;
  height: 42vw;
  background: linear-gradient(to right, rgba(37, 99, 235, 0.22), rgba(20, 184, 166, 0.12));
  border-radius: 50%;
  opacity: 0.72;
}
.shape-2 {
  bottom: -12%;
  right: -8%;
  width: 44vw;
  height: 44vw;
  background: linear-gradient(to left, rgba(20, 184, 166, 0.18), rgba(59, 130, 246, 0.1));
  border-radius: 44%;
  opacity: 0.68;
  animation-delay: -5s;
}
.shape-3 {
  top: 28%;
  left: 36%;
  width: 24vw;
  height: 24vw;
  background: linear-gradient(to bottom, rgba(59, 130, 246, 0.1), rgba(20, 184, 166, 0.06));
  border-radius: 32%;
  opacity: 0.62;
  animation-delay: -10s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  33% { transform: translate(30px, -50px) rotate(10deg); }
  66% { transform: translate(-20px, 20px) rotate(-5deg); }
}

/* 玻璃卡片 */
.login-card {
  width: 900px;
  height: 550px;
  display: flex;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.16);
  z-index: 1;
  overflow: hidden;
}

/* 左侧品牌区 */
.card-left {
  flex: 1;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.18), transparent 30%),
    linear-gradient(135deg, #2563eb 0%, #14b8a6 100%);
  color: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px;
  position: relative;
  overflow: hidden;
  z-index: 0;
}

.card-left::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
  opacity: 0;
  z-index: -1;
  transition: opacity 0.5s ease-in-out;
}

.brand-content {
  position: relative;
  z-index: 2;
  text-align: center;
}

.logo-circle {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  backdrop-filter: blur(10px);
}

.logo-icon {
  font-size: 38px;
}

.welcome-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 10px;
}

.welcome-desc {
  font-size: 14px;
  opacity: 0.92;
  font-weight: 400;
}

.decoration-circles .circle {
  position: absolute;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}
.c1 { width: 200px; height: 200px; top: -50px; left: -50px; }
.c2 { width: 150px; height: 150px; bottom: -30px; right: -30px; }

/* 右侧表单区 */
.card-right {
  flex: 1.2;
  padding: 50px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: rgba(255, 255, 255, 0.56);
}

.form-header {
  margin-bottom: 30px;
  text-align: center;
}
.form-header h2 {
  font-size: 24px;
  color: #0f172a;
  margin-bottom: 8px;
}
.sub-text {
  color: #64748b;
  font-size: 14px;
}

.custom-form :deep(.el-input__wrapper) {
  border-radius: 12px;
  box-shadow: 0 0 0 1px #dbe3ef inset;
  padding: 8px 15px;
  background: rgba(255, 255, 255, 0.92);
}
.custom-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #2563eb inset !important;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  font-size: 14px;
}
.form-options.center {
  justify-content: center;
}

.forgot-link, .back-link {
  color: #2563eb;
  cursor: pointer;
  transition: color 0.2s;
}
.forgot-link:hover, .back-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #2563eb 0%, #14b8a6 100%);
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}
.submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.16);
}

/* 响应式适配 */
.theme-switch {
  position: absolute;
  top: 20px;
  z-index: 10;
}

.theme-switch {
  right: 20px;
}

@media (max-width: 900px) {
  .login-card {
    width: 90%;
    height: auto;
    flex-direction: column;
  }
  .card-left {
    padding: 30px;
    flex: 0 0 auto;
  }
  .card-right {
    padding: 30px;
  }
  .logo-circle {
    width: 60px;
    height: 60px;
  }
  .logo-icon { font-size: 30px; }
  .welcome-title { font-size: 24px; }
}

/* 动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.fade-slide-leave-to {
    opacity: 0;
    transform: translateX(-20px);
  }
</style>

<!-- 非 scoped 样式，确保优先级和覆盖范围 -->
<style>
/* 
  Dark Mode Overlays 
  使用绝对定位的 div 层来实现平滑的背景切换
  解决 linear-gradient 不支持 transition 的问题
*/
.dark-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #1a1a1a 0%, #000000 100%);
  opacity: 0;
  z-index: 0; /* 在 shapes 之上 (DOM 顺序)，但在 card 之下 */
  pointer-events: none;
  transition: opacity 0.3s ease-in-out;
}

html.dark .dark-overlay {
  opacity: 1;
}

.card-left-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
  opacity: 0;
  z-index: 1; /* 在 card-left 背景之上，但在 brand-content (z-index: 2) 之下 */
  pointer-events: none;
  transition: opacity 0.3s ease-in-out;
}

html.dark .card-left-overlay {
  opacity: 1;
}

/* Dark Mode Styles for other elements */
/* 添加通用 transition 确保平滑过渡 */
#login-page .login-card,
#login-page .card-right,
#login-page .form-header h2,
#login-page .sub-text,
#login-page .logo-circle,
#login-page .theme-switch :deep(.theme-mode-trigger) {
  transition: all 0.3s ease-in-out !important;
}

html.dark #login-page .login-card {
  background: rgba(15, 23, 42, 0.76) !important;
  border: 1px solid rgba(148, 163, 184, 0.12) !important;
  box-shadow: 0 24px 50px rgba(2, 6, 23, 0.5) !important;
}

html.dark #login-page .card-right {
  background: rgba(15, 23, 42, 0.34) !important;
}

html.dark #login-page .form-header h2 {
  color: #e5eaf3 !important;
}

html.dark #login-page .sub-text {
  color: #94a3b8 !important;
}

html.mobile-mode #login-page {
  align-items: stretch;
  padding: 20px 14px 14px;
  box-sizing: border-box;
}

html.mobile-mode #login-page .theme-switch {
  right: 20px;
}

html.mobile-mode #login-page .login-card {
  width: 100%;
  max-width: none;
  height: auto;
  min-height: calc(100vh - 34px);
  border-radius: 28px;
  flex-direction: column;
  margin-top: 56px;
}

html.mobile-mode #login-page .card-left {
  flex: 0 0 auto;
  padding: 28px 24px;
}

html.mobile-mode #login-page .card-right {
  padding: 28px 22px 24px;
}

html.mobile-mode #login-page .welcome-title {
  font-size: 26px;
}

html.mobile-mode #login-page .welcome-desc {
  font-size: 13px;
}

html.mobile-mode #login-page .logo-circle {
  width: 64px;
  height: 64px;
}

html.mobile-mode #login-page .logo-icon {
  font-size: 30px;
}

html.dark #login-page .custom-form .el-input__wrapper {
  background: rgba(15, 23, 42, 0.7) !important;
  box-shadow: 0 0 0 1px #334155 inset !important;
}

html.dark #login-page .custom-form .el-input__inner {
  color: #e5eaf3 !important;
}

html.dark #login-page .logo-circle {
  background: rgba(255, 255, 255, 0.1) !important;
}

</style>
