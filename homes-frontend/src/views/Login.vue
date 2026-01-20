<template>
  <div class="login-container">
    <div class="background-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>
    
    <div class="login-card glass-effect">
      <div class="card-left">
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
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Key } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()

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
      const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api'
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