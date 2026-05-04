<template>
  <div class="dashboard-container">
    <el-container class="main-layout">
      <el-aside :width="isCollapse ? 'var(--sidebar-width-collapsed)' : 'var(--sidebar-width)'" class="sidebar-container">
        <div class="logo-container">
          <div class="logo">
            <span v-if="!isCollapse">从江房屋登记系统</span>
            <span v-else>从</span>
          </div>
          <el-icon class="collapse-icon" @click="toggleSidebar">
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
        </div>
        
        <el-scrollbar class="menu-scrollbar">
          <el-menu
            :key="activeMenu"
            @select="handleMenuSelect"
            :default-active="activeMenu"
            :collapse="isCollapse"
            class="sidebar-menu"
            :collapse-transition="false">
            <el-menu-item index="/dashboard" class="menu-item">
              <el-icon><HomeFilled /></el-icon>
              <template #title>
                <span>首页</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/rooms" class="menu-item">
              <el-icon><House /></el-icon>
              <template #title>
                <span>房间管理</span>
              </template>
            </el-menu-item>
            
            <el-menu-item index="/dashboard/tenants" class="menu-item">
              <el-icon><User /></el-icon>
              <template #title>
                <span>租户管理</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/contract-templates" class="menu-item">
              <el-icon><Document /></el-icon>
              <template #title>
                <span>合同模板</span>
              </template>
            </el-menu-item>
            

            <el-menu-item index="/dashboard/moves" class="menu-item">
              <el-icon><Van /></el-icon>
              <template #title>
                <span>搬迁管理</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/repair-records" class="menu-item">
              <el-icon><Tools /></el-icon>
              <template #title>
                <span>维修记录</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/procurement" class="menu-item">
              <el-icon><ShoppingCart /></el-icon>
              <template #title>
                <span>采购管理</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/warehouse" class="menu-item">
              <el-icon><ShoppingCart /></el-icon>
              <template #title>
                <span>库存管理</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/notify" class="menu-item">
              <el-icon><Bell /></el-icon>
              <template #title>
                <span>通知配置</span>
              </template>
            </el-menu-item>
            <el-menu-item index="/dashboard/system" class="menu-item">
              <el-icon><Setting /></el-icon>
              <template #title>
                <span>系统维护</span>
              </template>
            </el-menu-item>
          </el-menu>
          
        </el-scrollbar>
        
        <div class="collapse-bottom" @click="toggleSidebar">
          <el-icon :size="20" :class="{'is-collapsed': isCollapse}">
            <ArrowLeft />
          </el-icon>
        </div>
      </el-aside>
      
      <el-container class="main-container">
        <el-header class="main-header">
          <div class="breadcrumb">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item>首页</el-breadcrumb-item>
              <el-breadcrumb-item>{{ getMenuTitle(activeMenu) }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          
          <div class="header-right">
            <el-button 
              circle 
              text
              @click="toggleTheme" 
              style="margin-right: 8px; font-size: 18px;"
              :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
            >
              <el-icon>
                <Sunny v-if="isDark" />
                <Moon v-else />
              </el-icon>
            </el-button>

            <div class="time-display">
              <el-icon><Timer /></el-icon>
              <span>{{ currentTime }}</span>
            </div>
            <el-dropdown trigger="click">
              <div class="user-info">
                <el-avatar :size="32" class="user-avatar" :style="{ backgroundColor: '#409eff' }">{{ getUserInitials() }}</el-avatar>
                <span class="username">{{ user?.fullName || '管理员' }}</span>
                <el-icon><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openChangePasswordDialog">
                    <el-icon><Key /></el-icon>
                    <span>修改密码</span>
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleLogout">
                    <el-icon><SwitchButton /></el-icon>
                    <span>退出登录</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        
        <el-main class="content-area">
          <router-view v-slot="{ Component, route: currentRoute }">
            <component v-if="Component" :is="Component" :key="currentRoute.fullPath" />
          </router-view>
        </el-main>
      </el-container>
    </el-container>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="changePasswordDialogVisible"
      title="修改密码"
      width="400px"
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input
            v-model="passwordForm.oldPassword"
            type="password"
            placeholder="请输入旧密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="changePasswordDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitChangePassword">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authApi } from '../api/index.js'
import {
  House, 
  User, 
  Van, 
  Bell, 
  Fold, 
  Expand, 
  ArrowDown, 
  SwitchButton, 
  Tools, 
  ArrowLeft, 
  Key, 
  HomeFilled, 
  Timer, 
  Document,
  Sunny,
  Moon,
  Setting,
  UserFilled,
  ShoppingCart
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 主题切换逻辑
const isDark = ref(false)

const toggleTheme = () => {
  const htmlEl = document.documentElement
  htmlEl.classList.add('theme-transitioning')
  
  isDark.value = !isDark.value
  if (isDark.value) {
    htmlEl.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    htmlEl.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }

  requestAnimationFrame(() => {
    htmlEl.classList.remove('theme-transitioning')
  })
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

const isCollapse = ref(false)
const user = computed(() => authStore.user)
const activeMenu = computed(() => route.path)
const changePasswordDialogVisible = ref(false)

// 时间显示相关
const currentTime = ref('')
const updateTime = () => {
  const now = new Date()
  const options = { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: false
  }
  currentTime.value = now.toLocaleString('zh-CN', options).replace(/\//g, '-')
}

// 定时更新时间
let timeInterval
onMounted(() => {
  initTheme()
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onBeforeUnmount(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
const passwordFormRef = ref(null)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordForm.value.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const openChangePasswordDialog = () => {
  changePasswordDialogVisible.value = true
  passwordForm.value = {
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  }
}

const submitChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
        const response = await fetch(`${apiBaseUrl}/change-password`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authStore.token}`
          },
          body: JSON.stringify({
            old_password: passwordForm.value.oldPassword,
            new_password: passwordForm.value.newPassword
          })
        })
        
        const data = await response.json()
        
        if (response.ok) {
          ElMessage.success('密码修改成功')
          changePasswordDialogVisible.value = false
        } else {
          ElMessage.error(data.error || '密码修改失败')
        }
      } catch (error) {
        ElMessage.error('网络错误，请稍后重试')
        console.error('修改密码出错:', error)
      }
    }
  })
}

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

const handleMenuSelect = (index) => {
  if (typeof index !== 'string' || !index) return
  if (index === route.path) return
  router.push(index).catch(() => {})
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

const getUserInitials = () => {
  const name = user.value?.fullName || '管理员'
  return name.charAt(0).toUpperCase()
}

const getMenuTitle = (path) => {
  const menuMap = {
    '/dashboard/rooms': '房间管理',
    '/dashboard/tenants': '租户管理',
    '/dashboard/moves': '搬迁管理',
    '/dashboard/procurement': '采购管理',
    '/dashboard/warehouse': '库存管理',
    '/dashboard/notify': '通知配置',
    '/dashboard/repair-records': '维修记录',
    '/dashboard/contract-templates': '合同模板',
    '/dashboard/system': '系统维护'
  }
  return menuMap[path] || '首页'
}

// 轻量用户活动心跳：有活动则调用后台校验接口，触发后端续期并从响应头接收新令牌
let lastPing = 0
const MIN_PING_INTERVAL_MS = 120000 // 2分钟最小心跳间隔，避免过于频繁
const pingOnActivity = () => {
  const now = Date.now()
  const token = localStorage.getItem('token')
  if (!token) return
  if (now - lastPing < MIN_PING_INTERVAL_MS) return
  lastPing = now
  authApi.verifyToken().catch(() => {})
}

// 监听常见的用户活动事件
const activityHandler = () => pingOnActivity()
onMounted(() => {
  window.addEventListener('mousemove', activityHandler)
  window.addEventListener('keydown', activityHandler)
  window.addEventListener('click', activityHandler)
  window.addEventListener('scroll', activityHandler, { passive: true })
  window.addEventListener('touchstart', activityHandler, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', activityHandler)
  window.removeEventListener('keydown', activityHandler)
  window.removeEventListener('click', activityHandler)
  window.removeEventListener('scroll', activityHandler)
  window.removeEventListener('touchstart', activityHandler)
})
</script>

<style scoped>
.dashboard-container {
  height: 100vh;
  overflow: hidden;
  background: var(--bg-color);
}

.main-layout {
  height: 100%;
}

.sidebar-container {
  background: var(--sidebar-bg);
  box-shadow: var(--sidebar-shadow);
  transition:
    width 0.3s ease,
    background var(--theme-transition-duration) ease-in-out,
    box-shadow var(--theme-transition-duration) ease-in-out;
  z-index: 10;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}

.sidebar-collapse-btn {
  position: absolute;
  right: -15px;
  top: 50%;
  transform: translateY(-50%);
  width: 30px;
  height: 30px;
  background-color: #409EFF;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  z-index: 100;
}

.collapse-bottom {
  height: 54px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  border-top: 1px solid var(--sidebar-divider);
  color: var(--sidebar-text-muted);
  transition:
    background-color var(--theme-transition-duration) ease-in-out,
    color var(--theme-transition-duration) ease-in-out,
    border-color var(--theme-transition-duration) ease-in-out;
  background-color: transparent;
}

.collapse-bottom:hover {
  background-color: var(--sidebar-hover);
  color: var(--sidebar-hover-text);
}

.collapse-bottom .el-icon {
  transition: transform 0.3s;
}

.collapse-bottom .el-icon.is-collapsed {
  transform: rotate(180deg);
}

html.dark .collapse-bottom {
  border-top: 1px solid #363637;
}

html.dark .collapse-bottom:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.menu-scrollbar {
  flex: 1;
  overflow: hidden;
}

.logo-container {
  height: 66px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 18px;
  overflow: hidden;
  border-bottom: 1px solid var(--sidebar-divider);
  position: relative;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  color: var(--sidebar-text);
  letter-spacing: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-align: center;
  width: 100%;
}

.collapse-icon {
  font-size: 18px;
  cursor: pointer;
  color: var(--sidebar-text-muted);
  position: absolute;
  right: 18px;
}

.collapse-icon:hover {
  color: var(--sidebar-hover-text);
}

.sidebar-menu {
  border-right: none !important;
  padding: 12px;
  background: transparent;
}

.menu-item {
  margin: 8px 0;
  font-size: 15px;
  height: 44px;
  border-radius: 10px;
  color: var(--sidebar-text);
}

:deep(.sidebar-menu .el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.9), rgba(56, 189, 248, 0.75));
  color: #ffffff;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.28);
}

:deep(.sidebar-menu .el-menu-item:hover) {
  background: var(--sidebar-hover);
  color: var(--sidebar-hover-text);
}

/* 确保菜单项内容居中 */
:deep(.sidebar-menu:not(.el-menu--collapse) .el-menu-item) {
  justify-content: flex-start;
  padding: 0 14px;
}

:deep(.sidebar-menu:not(.el-menu--collapse) .el-menu-item .el-icon) {
  margin-right: 10px;
}

:deep(.sidebar-menu:not(.el-menu--collapse) .el-menu-item span) {
  text-align: left;
  width: auto;
}

:deep(.sidebar-menu.el-menu--collapse .el-menu-item) {
  justify-content: center;
  width: 48px;
  margin: 8px auto;
  border-radius: 12px;
  padding: 0 !important;
  height: 44px;
}

:deep(.sidebar-menu.el-menu--collapse .el-menu-item .el-tooltip__trigger) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.sidebar-menu.el-menu--collapse .el-menu-item .el-icon) {
  margin-right: 0 !important;
  font-size: 18px;
}

:deep(.sidebar-menu.el-menu--collapse .el-menu-item > span) {
  display: none;
}

.main-container {
  background: var(--bg-color);
}

.main-header {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 64px;
  transition:
    background var(--theme-transition-duration) ease-in-out,
    border-color var(--theme-transition-duration) ease-in-out,
    box-shadow var(--theme-transition-duration) ease-in-out;
  border-bottom: 1px solid var(--surface-border);
}

html.dark .main-header {
  background: rgba(15, 23, 42, 0.85);
}

.breadcrumb {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.time-display {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--el-color-primary);
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.time-display .el-icon {
  color: var(--el-color-primary);
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 999px;
  transition:
    background-color var(--theme-transition-duration) ease-in-out,
    border-color var(--theme-transition-duration) ease-in-out;
  border: 1px solid transparent;
}

.user-info:hover {
  background-color: var(--surface-muted);
  border-color: var(--surface-border);
}

html.dark .user-info:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  margin-right: 8px;
}

.username {
  margin-right: 8px;
  font-size: 14px;
}

.content-area {
  padding: 24px;
  overflow-y: auto;
  background: var(--bg-color);
}

</style>
