import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8005',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://localhost:8005',
        changeOrigin: true
      },
      '/generated_courseware': {
        target: 'http://localhost:8005',
        changeOrigin: true
      },
      '/generated_games': {
        target: 'http://localhost:8005',
        changeOrigin: true
      },
      '/generated_animations': {
        target: 'http://localhost:8005',
        changeOrigin: true
      },
      '/generated_lesson_plans': {
        target: 'http://localhost:8005',
        changeOrigin: true
      }
    }
  },
  css: {
    preprocessorOptions: {
      sass: {
        api: 'modern'
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    // 体积告警阈值：分包后仍可能有大 chunk，这里按实际情况上调，避免噪音
    chunkSizeWarningLimit: 800,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        // 依赖分包：业务代码与第三方库分离，提升缓存命中率与并行加载
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('element-plus')) return 'vendor-element'
          if (id.includes('katex')) return 'vendor-katex'
          if (id.includes('highlight.js')) return 'vendor-hljs'
          if (id.includes('marked')) return 'vendor-marked'
          if (id.includes('echarts')) return 'vendor-echarts'
          if (
            id.includes('node_modules/vue') ||
            id.includes('vue-router') ||
            id.includes('pinia')
          ) {
            return 'vendor-vue'
          }
          return 'vendor'
        },
      },
    },
  },
})
