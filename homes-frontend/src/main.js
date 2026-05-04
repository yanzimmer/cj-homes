import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './assets/styles/global.css'
import { applyTheme, getPreferredTheme } from './utils/theme'

applyTheme(getPreferredTheme())

const app = createApp(App)
app.use(router)
app.use(createPinia())
app.use(ElementPlus, {
  locale: zhCn
})
app.mount('#app')

// Remove no-transition class after mount to enable transitions
requestAnimationFrame(() => {
  document.documentElement.classList.remove('no-transition')
})
