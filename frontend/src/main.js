import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/main.scss'

const app = createApp(App)

// 注册Pinia
app.use(createPinia())

// 注册路由
app.use(router)

// 注册Element Plus
app.use(ElementPlus)

// 注册Element Plus Icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
