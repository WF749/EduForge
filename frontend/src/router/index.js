import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    // 首页即工作台：打开就进入"这一节课"，不再先经过一个介绍页
    path: '/',
    name: 'Workbench',
    component: () => import('@/views/WorkbenchView.vue')
  },
  {
    path: '/workbench',
    redirect: '/'
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue')
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeView.vue')
  },
  {
    path: '/courseware',
    name: 'Courseware',
    component: () => import('@/views/CoursewareView.vue')
  },
  {
    path: '/animation',
    name: 'Animation',
    component: () => import('@/views/AnimationView.vue')
  },
  {
    path: '/game',
    name: 'Game',
    component: () => import('@/views/GameView.vue')
  },
  {
    path: '/preview/:taskId',
    name: 'Preview',
    component: () => import('@/views/PreviewView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue')
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/HistoryView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
