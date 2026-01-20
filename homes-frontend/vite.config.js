import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  define: {
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false'
  },
  // 在 dev 打印日志，在生产构建移除所有 console/debugger
  esbuild: {
    drop: mode === 'production' ? ['console', 'debugger'] : []
  },
  // 降低生产模式下的 CLI 噪音（dev 保持 info）
  logLevel: mode === 'development' ? 'info' : 'silent'
}))
