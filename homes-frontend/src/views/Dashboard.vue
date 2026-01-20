<template>
  <div class="dashboard-container">
    <el-container class="main-layout">
      <el-aside :width="isCollapse ? '64px' : '240px'" class="sidebar-container">
        <div class="logo-container">
          <div class="logo">
            <span v-if="!isCollapse">房屋登记系统</span>
            <span v-else>房</span>
          </div>
          <el-icon class="collapse-icon" @click="toggleSidebar">
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
        </div>
        
        <el-scrollbar class="menu-scrollbar">
          <el-menu
            router
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
        
        <div class="collapse-indicator" @click="toggleSidebar">
          <div class="arrow-container">
            <el-icon :class="{'rotate-arrow': !isCollapse}">
              <ArrowLeft />
            </el-icon>
          </div>
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
          <router-view v-slot="{ Component }">
            <transition name="fade-transform" mode="out-in">
              <component :is="Component" />
            </transition>
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
  UserFilled
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 主题切换逻辑
const isDark = ref(false)

const toggleTheme = () => {
  isDark.value = !isDark.value
  const htmlEl = document.documentElement
  if (isDark.value) {
    htmlEl.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    htmlEl.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
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
        const response = await fetch('http://192.168.0.163:5000/api/change-password', {
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
}

.main-layout {
  height: 100%;
}

.sidebar-container {
  background-color: var(--card-bg);
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  transition: width 0.3s, background-color 0.3s;
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

.collapse-indicator {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 50px;
  background-color: #1890ff;
  border-radius: 0 4px 4px 0;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  z-index: 100;
  transition: all 0.3s;
}

.arrow-container {
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
}

.rotate-arrow {
  transform: rotate(180deg);
}

.collapse-indicator:hover {
  background-color: #40a9ff;
  width: 20px;
}

.menu-scrollbar {
  flex: 1;
  height: calc(100% - 60px);
}

.logo-container {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  overflow: hidden;
  border-bottom: 1px solid var(--el-border-color-light, #f0f0f0);
}

.logo {
  font-size: 30px;
  font-weight: 600;
  color: #1890ff;
  white-space: nowrap;
  overflow: hidden;
}

.collapse-icon {
  font-size: 18px;
  cursor: pointer;
  color: #909399;
}

.sidebar-menu {
  border-right: none !important;
}

.menu-item {
  margin: 4px 0;
  font-size: 16px;
  text-transform: uppercase;
}

/* 确保菜单项内容居中 */
.sidebar-menu .el-menu-item span {
  display: block;
  text-align: center;
  width: 100%;
}

/* 确保图标也居中 */
.sidebar-menu:not(.el-menu--collapse) .el-menu-item .el-icon {
  margin-right: 0;
  width: 100%;
  text-align: center;
  margin-bottom: 0;
  display: inline-block;
}

/* 修改为水平布局 */
.sidebar-menu:not(.el-menu--collapse) .el-menu-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
}

.sidebar-menu:not(.el-menu--collapse) .el-menu-item .el-icon {
  margin-right: 8px;
  width: auto;
}

.main-container {
  background-color: var(--bg-color);
}

.main-header {
  background-color: var(--card-bg);
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  transition: background-color 0.3s;
}

.breadcrumb {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.time-display {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 14px;
  color: #409EFF;
}

.time-display .el-icon {
  color: #409EFF;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 0 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

html.dark .user-info:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  background-color: #1890ff;
  margin-right: 8px;
}

.username {
  margin-right: 8px;
  font-size: 14px;
}

.content-area {
  padding: 20px;
  overflow-y: auto;
}
</style>