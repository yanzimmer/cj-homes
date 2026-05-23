<template>
  <el-dropdown trigger="click" placement="bottom-end" @command="handleCommand">
    <el-button class="theme-mode-trigger" :class="{ 'theme-mode-trigger--floating': floating }" text>
      <el-icon class="theme-mode-trigger__icon">
        <component :is="triggerIcon" />
      </el-icon>
      <span class="theme-mode-trigger__text">{{ triggerText }}</span>
      <el-icon class="theme-mode-trigger__caret"><ArrowDown /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu class="theme-mode-menu">
        <el-dropdown-item command="auto">
          <div class="theme-mode-item">
            <strong>自动</strong>
            <span>按本地时区时间自动切换</span>
          </div>
        </el-dropdown-item>
        <el-dropdown-item command="light">
          <div class="theme-mode-item">
            <strong>手动浅色</strong>
            <span>固定使用浅色主题</span>
          </div>
        </el-dropdown-item>
        <el-dropdown-item command="dark">
          <div class="theme-mode-item">
            <strong>手动深色</strong>
            <span>固定使用深色主题</span>
          </div>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowDown, Moon, Sunny, Timer } from '@element-plus/icons-vue'
import { applyTheme, getAutoTheme, getPreferredTheme, getThemeMode, setManualTheme, setThemeMode } from '../utils/theme'

const props = defineProps({
  floating: {
    type: Boolean,
    default: false,
  },
})

const currentMode = ref('auto')
const currentTheme = ref('light')
let autoRefreshTimeout = null
let autoRefreshInterval = null

const triggerIcon = computed(() => {
  if (currentMode.value === 'auto') return Timer
  return currentTheme.value === 'dark' ? Moon : Sunny
})

const triggerText = computed(() => {
  if (currentMode.value === 'auto') return '自动'
  return currentTheme.value === 'dark' ? '手动深色' : '手动浅色'
})

const clearAutoRefresh = () => {
  if (autoRefreshTimeout) {
    clearTimeout(autoRefreshTimeout)
    autoRefreshTimeout = null
  }
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval)
    autoRefreshInterval = null
  }
}

const syncThemeState = (transition = false) => {
  currentMode.value = getThemeMode()
  const nextTheme = currentMode.value === 'auto' ? getAutoTheme() : getPreferredTheme()
  currentTheme.value = nextTheme
  applyTheme(nextTheme, { transition, persist: true, mode: currentMode.value })
}

const scheduleAutoRefresh = () => {
  clearAutoRefresh()
  if (currentMode.value !== 'auto') return

  const now = new Date()
  const nextMinute = new Date(now)
  nextMinute.setSeconds(0, 0)
  nextMinute.setMinutes(now.getMinutes() + 1)
  const delay = Math.max(1000, nextMinute.getTime() - now.getTime())

  autoRefreshTimeout = window.setTimeout(() => {
    syncThemeState(false)
    autoRefreshInterval = window.setInterval(() => {
      syncThemeState(false)
    }, 60 * 1000)
  }, delay)
}

const handleCommand = (command) => {
  if (command === 'auto') {
    setThemeMode('auto', { transition: true })
  } else {
    setManualTheme(command === 'dark' ? 'dark' : 'light', { transition: true })
  }
  syncThemeState(false)
  scheduleAutoRefresh()
}

onMounted(() => {
  syncThemeState(false)
  scheduleAutoRefresh()
})

onBeforeUnmount(() => {
  clearAutoRefresh()
})
</script>

<style scoped>
.theme-mode-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 8px 12px;
  border-radius: 999px;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.22);
  border: 1px solid var(--surface-border);
  backdrop-filter: blur(10px);
  transition: all 0.25s ease;
}

.theme-mode-trigger:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(64, 158, 255, 0.45);
}

.theme-mode-trigger--floating {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.3);
}

.theme-mode-trigger__icon,
.theme-mode-trigger__caret {
  font-size: 16px;
}

.theme-mode-trigger__text {
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}

.theme-mode-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 180px;
}

.theme-mode-item strong {
  font-size: 13px;
  color: var(--text-main);
}

.theme-mode-item span {
  font-size: 12px;
  color: var(--text-secondary);
}

html.dark .theme-mode-trigger {
  background: rgba(15, 23, 42, 0.36);
}

html.dark .theme-mode-trigger:hover {
  background: rgba(30, 41, 59, 0.55);
}

html.dark .theme-mode-trigger--floating {
  background: rgba(15, 23, 42, 0.44);
  border-color: rgba(148, 163, 184, 0.24);
}
</style>
