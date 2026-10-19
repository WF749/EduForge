import { createRouter, createWebHistory } from 'vue-router'

/**
 * 路由表。
 *
 * 与后端能力一一对应，**不设任何前端虚构的页面**。每个一级入口都能在后端找到
 * 支撑它的接口；反过来后端已有的接口也都有页面消费（scripts/smoke_api_contract.py
 * 会校验前端写的路径确实存在于后端路由表）。
 *
 * `/preview/:taskId` 是 PPT 按任务预览的唯一入口，保留。
 */
const routes = [
  {
    // 首页即工作台：打开就进入"这一节课"，不再先经过一个介绍页
    path: '/',
    name: 'Workbench',
    component: () => import('@/views/WorkbenchView.vue')
  },
  { path: '/workbench', redirect: '/' },

  {
    path: '/lessons',
    name: 'Lessons',
    component: () => import('@/views/LessonsView.vue')
  },

  // 生成中心：教案 / 课件（六阶段）/ PPT / 动画 / 游戏，共用一张表单骨架
  { path: '/generate', redirect: '/generate/lesson-plan' },
  {
    path: '/generate/:type',
    name: 'Generate',
    component: () => import('@/views/GenerateView.vue'),
    props: true
  },

  {
    path: '/assistant',
    name: 'Assistant',
    component: () => import('@/views/AssistantView.vue')
  },

  {
    path: '/library',
    name: 'Library',
    component: () => import('@/views/LibraryView.vue')
  },

  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeView.vue')
  },

  {
    path: '/compliance',
    name: 'Compliance',
    component: () => import('@/views/ComplianceView.vue')
  },

  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue')
  },

  {
    path: '/system',
    name: 'System',
    component: () => import('@/views/SystemView.vue')
  },

  {
    path: '/preview/:taskId',
    name: 'Preview',
    component: () => import('@/views/PreviewView.vue')
  },

  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 换页回到顶部：内容长的页面（资源库）翻到底再跳转，否则会停在半空中
  scrollBehavior() {
    return { top: 0 }
  }
})

export default router
