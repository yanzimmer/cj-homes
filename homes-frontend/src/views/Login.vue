<template>
  <div class="login-container" id="login-page">
    <div class="theme-switch">
      <el-button 
        circle 
        text
        @click="toggleTheme" 
        class="theme-btn"
        :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
      >
        <el-icon :size="20">
          <Sunny v-if="isDark" />
          <Moon v-else />
        </el-icon>
      </el-button>
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
            <span class="logo-icon">🏠</span>
          </div>
          <h1 class="welcome-title">欢迎回来</h1>
          <p class="welcome-desc">高效、智能的房屋租赁管理平台</p>
        </div>
        <div class="decoration-circles">
          <div class="circle c1"></div>
          <div class="circle c2"></div>
        </div>
      </div>

      <div class="card-right">
        <div class="form-header">
          <h2>{{ isResetMode ? '重置密码' : '账号登录' }}</h2>
          <p class="sub-text">{{ isResetMode ? '请输入您的安全口令以重置密码' : '请输入您的账号密码以继续' }}</p>
        </div>

        <transition name="fade-slide" mode="out-in">
          <!-- 登录表单 -->
          <el-form v-if="!isResetMode" :model="loginForm" :rules="rules" ref="loginFormRef" class="custom-form" size="large">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" :prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" @keyup.enter="handleLogin" />
            </el-form-item>
            
            <div class="form-options">
              <el-checkbox v-model="rememberMe">记住我</el-checkbox>
              <span class="forgot-link" @click="switchToReset">忘记密码？</span>
            </div>

            <el-button type="primary" :loading="loading" class="submit-btn" @click="handleLogin">
              立即登录
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Key, Sunny, Moon } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()

// 主题切换逻辑
const isDark = ref(false)

const toggleTheme = () => {
  const htmlEl = document.documentElement
  // 添加过渡类，确保所有元素平滑切换
  htmlEl.classList.add('theme-transitioning')
  
  isDark.value = !isDark.value
  if (isDark.value) {
    htmlEl.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    htmlEl.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
  
  // 移除过渡类，恢复原有性能
  setTimeout(() => {
    htmlEl.classList.remove('theme-transitioning')
  }, 300)
}

const initTheme = () => {
  const savedTheme = localStorage.getItem('theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
}

onMounted(() => {
  initTheme()
})

const loginFormRef = ref(null)
const loading = computed(() => authStore.loading)
const loginForm = reactive({
  username: '',
  password: ''
})
const rememberMe = ref(true)

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      const success = await authStore.login(loginForm.username, loginForm.password)
      if (success) {
        ElMessage.success('登录成功')
        router.push('/dashboard')
      }
    }
  })
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
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
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
  filter: blur(50px);
  z-index: 0;
  animation: float 20s infinite;
}
.shape-1 {
  top: -10%;
  left: -10%;
  width: 50vw;
  height: 50vw;
  background: linear-gradient(to right, #a1c4fd, #c2e9fb);
  border-radius: 50%;
  opacity: 0.5;
}
.shape-2 {
  bottom: -10%;
  right: -10%;
  width: 60vw;
  height: 60vw;
  background: linear-gradient(to left, #d4fc79, #96e6a1);
  border-radius: 40%;
  opacity: 0.5;
  animation-delay: -5s;
}
.shape-3 {
  top: 30%;
  left: 30%;
  width: 30vw;
  height: 30vw;
  background: linear-gradient(to bottom, #cfd9df, #e2ebf0);
  border-radius: 30%;
  opacity: 0.3;
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
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
  z-index: 1;
  overflow: hidden;
}

/* 左侧品牌区 */
.card-left {
  flex: 1;
  background: linear-gradient(135deg, #3a7bd5 0%, #3a6073 100%);
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
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  backdrop-filter: blur(5px);
}

.logo-icon {
  font-size: 40px;
}

.welcome-title {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 10px;
  letter-spacing: 1px;
}

.welcome-desc {
  font-size: 14px;
  opacity: 0.9;
  font-weight: 300;
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
  background: rgba(255, 255, 255, 0.4);
}

.form-header {
  margin-bottom: 30px;
  text-align: center;
}
.form-header h2 {
  font-size: 24px;
  color: #333;
  margin-bottom: 8px;
}
.sub-text {
  color: #666;
  font-size: 14px;
}

.custom-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  padding: 8px 15px;
  background: rgba(255, 255, 255, 0.8);
}
.custom-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #409eff inset !important;
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
  color: #409eff;
  cursor: pointer;
  transition: color 0.2s;
}
.forgot-link:hover, .back-link:hover {
  color: #3a7bd5;
  text-decoration: underline;
}

.submit-btn {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
  background: linear-gradient(90deg, #409eff, #3a7bd5);
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}
.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

/* 响应式适配 */
.theme-switch {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.theme-btn {
  font-size: 20px;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(5px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  width: 40px;
  height: 40px;
  transition: all 0.3s;
}

.theme-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: rotate(15deg);
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
#login-page .theme-btn {
  transition: all 0.3s ease-in-out !important;
}

html.dark #login-page .login-card {
  background: rgba(30, 30, 30, 0.7) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5) !important;
}

html.dark #login-page .card-right {
  background: rgba(0, 0, 0, 0.2) !important;
}

html.dark #login-page .form-header h2 {
  color: #e5eaf3 !important;
}

html.dark #login-page .sub-text {
  color: #a3a6ad !important;
}

html.dark #login-page .custom-form .el-input__wrapper {
  background: rgba(0, 0, 0, 0.3) !important;
  box-shadow: 0 0 0 1px #4c4d4f inset !important;
}

html.dark #login-page .custom-form .el-input__inner {
  color: #e5eaf3 !important;
}

html.dark #login-page .logo-circle {
  background: rgba(255, 255, 255, 0.1) !important;
}

html.dark #login-page .theme-btn {
  background: rgba(0, 0, 0, 0.3) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

html.dark #login-page .theme-btn:hover {
  background: rgba(0, 0, 0, 0.5) !important;
}
</style>
