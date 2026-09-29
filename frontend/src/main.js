import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './store/theme'
import './assets/styles/main.scss'

const app = createApp(App)

// 注册Pinia
const pinia = createPinia()
app.use(pinia)

// 主题必须在挂载**之前**定好：否则首帧会先按深色画一遍再跳成浅色，
// 教师看到的是一次闪屏。
useThemeStore(pinia).init()

// 注册路由
app.use(router)

// 注册Element Plus
app.use(ElementPlus)

// 注册Element Plus Icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
