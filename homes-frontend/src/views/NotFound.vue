<template>
  <div class="not-found-container">
    <div class="content">
      <h1 class="error-code">404</h1>
      <h2 class="error-title">页面未找到</h2>
      <p class="error-desc">您访问的页面不存在或已被移除。</p>
      <div class="countdown-box">
        <p>
          将在 <span class="seconds">{{ countdown }}</span> 秒后自动返回首页
        </p>
      </div>
      <div class="actions">
        <el-button type="primary" @click="goHome">立即返回首页</el-button>
        <el-button @click="goBack">返回上一页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const countdown = ref(5)
let timer = null

const goHome = () => {
  router.push('/')
}

const goBack = () => {
  router.go(-1)
}

onMounted(() => {
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
      goHome()
    }
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.not-found-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: var(--bg-color);
  color: var(--text-main);
  text-align: center;
}

.content {
  padding: 40px;
  background: var(--card-bg);
  border-radius: var(--card-radius);
  box-shadow: var(--card-shadow);
  max-width: 500px;
  width: 90%;
}

.error-code {
  font-size: 120px;
  font-weight: bold;
  color: var(--el-color-primary);
  margin: 0;
  line-height: 1.2;
  text-shadow: 4px 4px 0px rgba(64, 158, 255, 0.1);
}

.error-title {
  font-size: 30px;
  margin: 10px 0 20px;
  color: var(--text-main);
}

.error-desc {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 30px;
}

.countdown-box {
  margin-bottom: 30px;
  font-size: 16px;
  color: var(--text-regular);
}

.seconds {
  color: var(--el-color-danger);
  font-weight: bold;
  font-size: 20px;
  margin: 0 4px;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}
</style>
