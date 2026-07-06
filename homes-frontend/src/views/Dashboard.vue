<template>
  <div class="dashboard-container" :class="{ 'dashboard-container--mobile': mobileMode }">
    <el-container class="main-layout">
      <el-aside :width="isCollapse ? 'var(--sidebar-width-collapsed)' : 'var(--sidebar-width)'" class="sidebar-container">
        <div class="logo-container">
          <div class="logo">
            <el-icon class="logo-mark"><House /></el-icon>
            <span v-if="!isCollapse">从江房屋登记系统</span>
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
            <el-menu-item v-for="item in navTabs" :key="item.path" :index="item.path" class="menu-item">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>
                <span>{{ item.title }}</span>
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
        <div class="workspace-header">
          <div class="workspace-header__main">
            <div class="workspace-header__left">
              <el-button v-if="mobileMode" class="mobile-menu-button" circle text @click="openMobileMenu">
                <el-icon><Operation /></el-icon>
              </el-button>
              <div v-if="mobileMode" class="mobile-page-title">{{ currentPage.title }}</div>
              <div class="breadcrumb">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item>
                  <span class="breadcrumb-project">
                    <el-icon class="breadcrumb-project__icon"><House /></el-icon>
                    <span>从江房屋登记系统</span>
                  </span>
                </el-breadcrumb-item>
                <el-breadcrumb-item>
                  <span class="breadcrumb-current">
                    <el-icon class="breadcrumb-current__icon">
                      <component :is="currentPage.icon" />
                    </el-icon>
                    <span>{{ currentPage.title }}</span>
                  </span>
                </el-breadcrumb-item>
              </el-breadcrumb>
            </div>
            </div>

            <div class="header-right">
              <DisplayModeSwitch v-if="!mobileMode" />
              <ThemeModeSwitch />
              <el-popover
                placement="bottom-end"
                :width="320"
                trigger="click"
                popper-class="session-event-popover"
                @show="markSessionEventsRead"
              >
                <template #reference>
                  <el-badge :value="unreadSessionEventCount" :hidden="!unreadSessionEventCount" :max="99">
                    <el-button class="session-event-button" circle text @click="markSessionEventsRead">
                      <el-icon><Bell /></el-icon>
                    </el-button>
                  </el-badge>
                </template>
                <div class="session-event-panel">
                  <div class="session-event-panel__head">
                    <strong>会话提醒</strong>
                    <el-button link type="primary" @click="fetchSessionEvents({ incremental: false, notify: false })">刷新</el-button>
                  </div>
                  <div v-if="sessionEvents.length" class="session-event-list">
                    <article v-for="item in sessionEvents" :key="item.id" class="session-event-item">
                      <div class="session-event-item__title">{{ item.title }}</div>
                      <div class="session-event-item__message">{{ item.message || '有新的登录会话变化' }}</div>
                      <div class="session-event-item__time">{{ item.created_at || '-' }}</div>
                    </article>
                  </div>
                  <div v-else class="session-event-empty">暂时没有新的会话提醒</div>
                </div>
              </el-popover>

              <div class="time-display">
                <el-icon><Timer /></el-icon>
                <span>{{ currentTime }}</span>
              </div>
              <el-dropdown trigger="click">
                <div class="user-info">
                  <el-avatar :size="32" class="user-avatar">{{ getUserInitials() }}</el-avatar>
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
                    <el-dropdown-item divided disabled class="version-dropdown-item">
                      <div class="version-dropdown">
                        <div class="version-dropdown__title">版本信息</div>
                        <div class="version-dropdown__row">前端 {{ frontendVersionLabel }}</div>
                        <div class="version-dropdown__row">后端 {{ backendVersionLabel }}</div>
                      </div>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
        
        <div class="content-area" :class="{ 'content-area--home': route.path === '/dashboard' }">
          <router-view v-slot="{ Component, route: currentRoute }">
            <component v-if="Component" :is="Component" :key="currentRoute.fullPath" />
          </router-view>
        </div>
      </el-container>
    </el-container>

    <el-drawer
      v-model="mobileMenuVisible"
      direction="ltr"
      size="82%"
      :with-header="false"
      class="mobile-nav-drawer"
    >
      <div class="mobile-drawer__header">
        <div>
          <div class="mobile-drawer__title">从江房屋登记系统</div>
          <div class="mobile-drawer__subtitle">当前：{{ currentPage.title }}</div>
        </div>
        <DisplayModeSwitch />
      </div>

      <el-scrollbar class="mobile-drawer__body">
        <el-menu
          :default-active="activeMenu"
          class="mobile-drawer__menu"
          @select="handleMenuSelect"
        >
          <el-menu-item v-for="item in navTabs" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </el-scrollbar>
    </el-drawer>

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
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { authApi, metaApi } from '../api/index.js'
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
  Setting,
  ShoppingCart,
  Coin,
  Operation
} from '@element-plus/icons-vue'
import DisplayModeSwitch from '../components/DisplayModeSwitch.vue'
import ThemeModeSwitch from '../components/ThemeModeSwitch.vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'
import { applyTheme, getPreferredTheme } from '../utils/theme'
import { formatVersionText, frontendVersionInfo } from '../utils/versionInfo'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isCollapse = ref(false)
const mobileMode = ref(false)
const mobileMenuVisible = ref(false)
const user = computed(() => authStore.user)
const activeMenu = computed(() => route.path)
const changePasswordDialogVisible = ref(false)
const sessionEvents = ref([])
const unreadSessionEventCount = ref(0)
const latestSessionEventId = ref(0)
const sessionEventReady = ref(false)
const backendVersionInfo = ref({
  version: '',
  commit: '',
})
let sessionEventTimer = null

const navTabs = [
  { path: '/dashboard', title: '首页', icon: HomeFilled },
  { path: '/dashboard/rooms', title: '房间管理', icon: House },
  { path: '/dashboard/tenants', title: '租户管理', icon: User },
  { path: '/dashboard/contract-templates', title: '合同模板', icon: Document },
  { path: '/dashboard/moves', title: '搬迁管理', icon: Van },
  { path: '/dashboard/repair-records', title: '维修记录', icon: Tools },
  { path: '/dashboard/procurement', title: '采购管理', icon: ShoppingCart },
  { path: '/dashboard/warehouse', title: '库存管理', icon: ShoppingCart },
  { path: '/dashboard/utility-bills', title: '水电费', icon: Coin },
  { path: '/dashboard/rent-ledger', title: '收租台账', icon: Coin },
  { path: '/dashboard/notify', title: '通知配置', icon: Bell },
  { path: '/dashboard/system', title: '系统维护', icon: Setting },
]

const navTabMap = Object.fromEntries(navTabs.map((item) => [item.path, item]))

const currentPage = computed(() => navTabMap[route.path] || navTabMap['/dashboard'])
const frontendVersionLabel = computed(() => formatVersionText(frontendVersionInfo.version))
const backendVersionLabel = computed(() => formatVersionText(backendVersionInfo.value.version))

const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
  if (!mobileMode.value) {
    mobileMenuVisible.value = false
  }
}

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
  applyTheme(getPreferredTheme(), { persist: true })
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
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
  if (mobileMode.value) {
    mobileMenuVisible.value = !mobileMenuVisible.value
    return
  }
  isCollapse.value = !isCollapse.value
}

const openMobileMenu = () => {
  mobileMenuVisible.value = true
}

const handleMenuSelect = (index) => {
  if (typeof index !== 'string' || !index) return
  if (mobileMode.value) {
    mobileMenuVisible.value = false
  }
  if (index === route.path) return
  router.push(index).catch(() => {})
}

const handleLogout = async () => {
  try {
    await authApi.logout()
  } catch (_) {
    // 忽略退出接口失败，仍然清理本地登录态
  } finally {
    authStore.logout()
    router.push('/login')
  }
}

const getUserInitials = () => {
  const name = user.value?.fullName || '管理员'
  return name.charAt(0).toUpperCase()
}

const sessionEventNotificationType = (eventType) => {
  if (eventType === 'login') return 'success'
  if (eventType === 'logout') return 'info'
  if (eventType === 'revoked' || eventType === 'replaced') return 'warning'
  if (eventType === 'expired') return 'error'
  return 'info'
}

const fetchVersionInfo = async () => {
  try {
    const response = await metaApi.getVersionInfo()
    backendVersionInfo.value = {
      version: response?.data?.backend?.version || '',
      commit: response?.data?.backend?.commit || '',
    }
  } catch (_) {
    backendVersionInfo.value = {
      version: '',
      commit: '',
    }
  }
}

const markSessionEventsRead = () => {
  unreadSessionEventCount.value = 0
}

const fetchSessionEvents = async ({ incremental = true, notify = true } = {}) => {
  try {
    const params = incremental && latestSessionEventId.value
      ? { after_id: latestSessionEventId.value, limit: 20 }
      : { limit: 12 }
    const response = await authApi.getSessionEvents(params)
    const events = Array.isArray(response?.data?.events) ? response.data.events : []
    if (!incremental) {
      sessionEvents.value = events.slice(-12).reverse()
      latestSessionEventId.value = response?.data?.latest_event_id || events.at(-1)?.id || latestSessionEventId.value || 0
      sessionEventReady.value = true
      return
    }
    if (!events.length) {
      sessionEventReady.value = true
      return
    }

    latestSessionEventId.value = response?.data?.latest_event_id || events.at(-1)?.id || latestSessionEventId.value
    const merged = [...sessionEvents.value].reverse()
    events.forEach((item) => {
      if (!merged.some(existing => existing.id === item.id)) {
        merged.push(item)
      }
    })
    sessionEvents.value = merged.slice(-12).reverse()

    if (sessionEventReady.value) {
      unreadSessionEventCount.value += events.length
      if (notify) {
        events.forEach((item) => {
          ElNotification({
            title: item.title || '会话提醒',
            message: item.message || '登录会话发生变化',
            type: sessionEventNotificationType(item.event_type),
            duration: 3200,
          })
        })
      }
    } else {
      sessionEventReady.value = true
    }
  } catch (_) {
    // 忽略提醒拉取异常，避免干扰主流程
  }
}

const startSessionEventPolling = () => {
  if (sessionEventTimer) {
    clearInterval(sessionEventTimer)
  }
  sessionEventTimer = setInterval(() => {
    fetchSessionEvents({ incremental: true, notify: true })
  }, 12000)
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
  fetchVersionInfo()
  fetchSessionEvents({ incremental: false, notify: false })
  startSessionEventPolling()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', activityHandler)
  window.removeEventListener('keydown', activityHandler)
  window.removeEventListener('click', activityHandler)
  window.removeEventListener('scroll', activityHandler)
  window.removeEventListener('touchstart', activityHandler)
  if (sessionEventTimer) {
    clearInterval(sessionEventTimer)
  }
})
</script>

<style scoped>
.dashboard-container {
  height: 100vh;
  overflow: hidden;
  background: var(--bg-color);
  padding: 8px;
  box-sizing: border-box;
}

.main-layout {
  height: 100%;
  gap: 10px;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  box-sizing: border-box;
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
  border-radius: 18px;
  border: 1px solid var(--sidebar-divider);
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
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--sidebar-text);
  letter-spacing: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-align: center;
  width: 100%;
}

.logo-mark {
  font-size: 18px;
  color: #60a5fa;
  flex-shrink: 0;
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
  padding: 14px;
  background: transparent;
}

.menu-item {
  margin: 8px 0;
  font-size: 14px;
  height: 44px;
  border-radius: 12px;
  color: var(--sidebar-text);
}

:deep(.sidebar-menu .el-menu-item.is-active) {
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #ffffff;
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.22);
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
  border-radius: 14px;
  padding: 0 !important;
  height: 44px;
}

:deep(.sidebar-menu.el-menu--collapse) {
  padding: 12px 6px;
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
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: transparent;
  border: none;
  border-radius: 0;
  overflow: hidden;
}

.workspace-header {
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(14px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  flex-shrink: 0;
  padding: 10px 14px 9px;
  transition:
    background var(--theme-transition-duration) ease-in-out,
    border-color var(--theme-transition-duration) ease-in-out,
    box-shadow var(--theme-transition-duration) ease-in-out;
  border: 1px solid var(--surface-border);
  margin: 0 2px;
  border-radius: 16px;
}

html.dark .workspace-header {
  background: rgba(11, 18, 32, 0.86);
}

.workspace-header__main {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-height: 34px;
}

.workspace-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.breadcrumb {
  font-size: 14px;
  min-width: 0;
  overflow: hidden;
}

.breadcrumb-current {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--el-color-primary);
  font-weight: 600;
}

.breadcrumb-current__icon {
  font-size: 13px;
}

.breadcrumb-project {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.breadcrumb-project__icon {
  color: var(--el-color-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.session-event-button {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  color: var(--text-main);
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.session-event-button:hover {
  color: var(--el-color-primary);
  border-color: rgba(64, 158, 255, 0.4);
}

.session-event-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.session-event-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.session-event-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 360px;
  overflow-y: auto;
}

.session-event-item {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
}

.session-event-item__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
}

.session-event-item__message {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.session-event-item__time {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.session-event-empty {
  padding: 18px 0 10px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}

:deep(.version-dropdown-item.is-disabled) {
  opacity: 1;
}

:deep(.version-dropdown-item.is-disabled .el-dropdown-menu__item) {
  cursor: default;
}

.version-dropdown {
  display: flex;
  min-width: 160px;
  flex-direction: column;
  gap: 4px;
  color: var(--text-main);
}

.version-dropdown__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
}

.version-dropdown__row {
  font-size: 12px;
  line-height: 1.5;
}

.mobile-menu-button {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: var(--text-main);
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.mobile-menu-button:hover {
  color: var(--el-color-primary);
  border-color: rgba(64, 158, 255, 0.4);
}

.time-display {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  color: #1d4ed8;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid var(--surface-border);
}

.time-display .el-icon {
  color: #1d4ed8;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 4px 8px;
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
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  margin-right: 8px;
}

.username {
  margin-right: 8px;
  font-size: 14px;
}

.content-area {
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
  padding: 14px 0 0;
  overflow-y: auto;
  background: transparent;
  margin: 0;
  border-radius: 0;
  border: none;
}

.content-area--home {
  padding: 18px 20px 20px;
  background: var(--card-bg);
  margin: 0 2px 2px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
}

:deep(.mobile-nav-drawer .el-drawer__body) {
  padding: 0;
}

.mobile-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 18px 14px;
  border-bottom: 1px solid var(--surface-border);
}

.mobile-drawer__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}

.mobile-drawer__subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.mobile-drawer__body {
  height: calc(100vh - 86px);
}

.mobile-drawer__menu {
  border-right: none !important;
  padding: 12px;
  background: transparent;
}

.dashboard-container--mobile {
  padding: 0;
}

.dashboard-container--mobile .main-layout {
  gap: 0;
  padding: 0;
  border: none;
  border-radius: 0;
}

.dashboard-container--mobile .sidebar-container {
  display: none;
}

.dashboard-container--mobile .workspace-header {
  margin: 0;
  padding: 12px 14px 10px;
  border-radius: 0 0 18px 18px;
}

.dashboard-container--mobile .workspace-header__main {
  align-items: center;
  flex-wrap: nowrap;
  gap: 10px;
}

.dashboard-container--mobile .breadcrumb-project > span:last-child {
  display: none;
}

.dashboard-container--mobile .breadcrumb {
  display: none;
}

.mobile-page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}

.dashboard-container--mobile .header-right {
  width: auto;
  margin-left: auto;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}

.dashboard-container--mobile .session-event-button {
  width: 36px;
  height: 36px;
}

.dashboard-container--mobile .user-info {
  margin-left: 2px;
  padding: 2px 4px;
}

.dashboard-container--mobile .time-display {
  display: none;
}

.dashboard-container--mobile .username {
  display: none;
}

.dashboard-container--mobile .content-area {
  margin: 0;
  padding: 12px;
  border: none;
  border-radius: 0;
  background: transparent;
}

.dashboard-container--mobile .content-area--home {
  margin: 0;
  padding: 12px;
  border: none;
  border-radius: 0;
  background: transparent;
}

</style>
