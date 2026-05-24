<template>
  <el-button class="display-mode-trigger" :class="{ 'display-mode-trigger--floating': floating }" text @click="handleToggle">
    <el-icon class="display-mode-trigger__icon">
      <component :is="currentMode === 'mobile' ? Iphone : Monitor" />
    </el-icon>
    <span class="display-mode-trigger__text">
      {{ currentMode === 'mobile' ? '桌面模式' : '手机模式' }}
    </span>
  </el-button>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Iphone, Monitor } from '@element-plus/icons-vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode, toggleDisplayMode } from '../utils/displayMode'

const props = defineProps({
  floating: {
    type: Boolean,
    default: false,
  },
})

const currentMode = ref('desktop')

const syncDisplayMode = () => {
  currentMode.value = getPreferredDisplayMode()
}

const handleToggle = () => {
  toggleDisplayMode()
  syncDisplayMode()
}

onMounted(() => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})
</script>

<style scoped>
.display-mode-trigger {
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

.display-mode-trigger:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(64, 158, 255, 0.45);
}

.display-mode-trigger--floating {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.3);
}

.display-mode-trigger__icon {
  font-size: 16px;
}

.display-mode-trigger__text {
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}

html.dark .display-mode-trigger {
  background: rgba(15, 23, 42, 0.36);
}

html.dark .display-mode-trigger:hover {
  background: rgba(30, 41, 59, 0.55);
}

html.dark .display-mode-trigger--floating {
  background: rgba(15, 23, 42, 0.44);
  border-color: rgba(148, 163, 184, 0.24);
}
</style>
