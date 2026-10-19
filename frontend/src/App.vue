<template>
  <div class="shell" :class="{ 'shell--collapsed': collapsed }">
    <!-- 侧边导航：桌面常驻，移动端换成底部 Tab -->
    <aside class="shell__nav" :aria-label="'主导航'">
      <div class="brand" @click="$router.push('/')">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
            <path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M5 11v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </span>
        <span v-show="!collapsed" class="brand__text">
          <b>EduForge</b>
          <small>教铸 · 备课工作台</small>
        </span>
      </div>

      <nav class="nav">
        <template v-for="group in navGroups" :key="group.label">
          <p v-show="!collapsed" class="nav__group">{{ group.label }}</p>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav__item"
            :class="{ 'is-active': isActive(item) }"
            :title="collapsed ? item.name : ''"
          >
            <el-icon :size="18"><component :is="item.icon" /></el-icon>
            <span v-show="!collapsed" class="nav__label">{{ item.name }}</span>
            <span v-show="!collapsed && item.ops" class="nav__ops">运维</span>
          </router-link>
        </template>
      </nav>

      <button
        class="nav__collapse"
        type="button"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        :aria-expanded="!collapsed"
        @click="collapsed = !collapsed"
      >
        <el-icon :size="16"><component :is="collapsed ? Expand : Fold" /></el-icon>
        <span v-show="!collapsed">收起</span>
      </button>
    </aside>

    <div class="shell__body">
      <!-- 顶栏：只放全局状态，不放页面操作（页面操作在各页自己的 PageHeader 里） -->
      <header class="topbar">
        <div class="topbar__left">
          <span class="topbar__crumb">{{ currentName }}</span>
        </div>
        <div class="topbar__right">
          <!--
            生成中指示：只要工作台在跑生成任务，任何页面都能看到。
            生成会长时间占用后端，别的页面因此变慢 —— 不说清原因，
            教师只会觉得"系统卡了/坏了"。这是对"为什么慢"的解释，不是装饰。
          -->
          <span v-if="runningKinds.length" class="topbar__chip is-running" role="status">
            <i class="topbar__spinner" aria-hidden="true" />
            正在生成{{ runningKinds.join('、') }}<span class="topbar__chip-extra"> · 其他页面可能响应较慢</span>
          </span>

          <!-- 数据流向常驻：让"数据去了哪"每次都看得见 -->
          <DataFlowBadge />
          <span class="topbar__chip" :class="{ 'is-demo': !hasApiKey }">
            <i class="topbar__dot" aria-hidden="true" />
            {{ hasApiKey ? '模型已配置' : '演示模式' }}
          </span>
          <el-dropdown trigger="click" @command="onTheme">
            <button class="icon-btn" type="button" aria-label="外观设置">
              <el-icon :size="18"><component :is="themeIcon" /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="light" :disabled="theme.mode === 'light'">
                  浅色
                </el-dropdown-item>
                <el-dropdown-item command="dark" :disabled="theme.mode === 'dark'">
                  深色
                </el-dropdown-item>
                <el-dropdown-item command="system" :disabled="theme.mode === 'system'">
                  跟随系统
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <router-link to="/settings" class="icon-btn" aria-label="设置">
            <el-icon :size="18"><Setting /></el-icon>
          </router-link>
        </div>
      </header>

      <!-- 演示模式横幅：不配置 Key 时生成结果是假的，必须提前说清 -->
      <div v-if="!hasApiKey && !demoDismissed" class="banner" role="status">
        <el-icon><InfoFilled /></el-icon>
        <span>
          当前未配置模型服务的 API Key，生成类功能会返回演示内容。
          <router-link to="/settings">去设置</router-link>
        </span>
        <button class="banner__close" type="button" aria-label="关闭提示" @click="demoDismissed = true">
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </div>

      <main class="shell__main" :class="{ 'shell__main--flush': isWorkbench }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <keep-alive :include="KEEP_ALIVE">
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </main>

      <footer class="shell__footer">
        <span>EduForge · 多模态 AI 互动式教学智能体</span>
        <span class="wb-muted">Vue 3 · FastAPI · RAG</span>
      </footer>
    </div>

    <!-- 移动端底部 Tab -->
    <nav class="tabbar" aria-label="底部导航">
      <router-link
        v-for="item in mobileTabs"
        :key="item.path"
        :to="item.path"
        class="tabbar__item"
        :class="{ 'is-active': isActive(item) }"
      >
        <el-icon :size="20"><component :is="item.icon" /></el-icon>
        <span>{{ item.name }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Collection, FolderOpened,
  Reading, Setting, Expand, Fold, Close, InfoFilled, Sunny, Moon, Monitor
} from '@element-plus/icons-vue'
import DataFlowBadge from '@/components/DataFlowBadge.vue'
import { useAppStore } from '@/store/app'
import { useThemeStore } from '@/store/theme'
import { ARTIFACTS, useLessonStore } from '@/store/lesson'

/**
 * 应用外壳：导航 + 顶栏 + 内容 + 页脚。
 *
 * 两条刻意的取舍：
 *  1. **顶栏不放页面操作**。旧版顶栏又是课程切换又是生成按钮，页面自己的
 *     操作却藏在卡片里，教师要在两个地方找按钮。现在顶栏只放全局状态，
 *     页面操作一律进各页的 PageHeader。
 *  2. **工作台不吃外层滚动**（`shell__main--flush`）。工作台是三栏自滚动布局，
 *     再套一层滚动条会出现"滚到底还有一截"。
 */
const route = useRoute()
const store = useAppStore()
const theme = useThemeStore()

const collapsed = ref(false)
const demoDismissed = ref(false)

/**
 * 一级导航只留三组。
 *
 * 「生成中心」和「通用问答」**故意不在这里**：
 * 它们与工作台做的是同一件事（生成四类产物 / 提问），并列会让新手
 * 第一件事就是"判断该去哪个页面"。两个路由都保留、都能直接访问，
 * 但入口降为工作台里的次级操作（高级生成设置 / 对话模式切换）。
 */
const navGroups = [
  {
    label: '备课',
    items: [
      { path: '/', name: '工作台', icon: HomeFilled },
      { path: '/lessons', name: '我的备课', icon: Collection }
    ]
  },
  {
    label: '资源',
    items: [
      { path: '/library', name: '资源库', icon: FolderOpened },
      { path: '/knowledge', name: '知识库', icon: Reading }
    ]
  },
  {
    label: '系统',
    items: [
      { path: '/compliance', name: '合规中心', icon: 'Lock' },
      { path: '/settings', name: '设置', icon: Setting },
      { path: '/system', name: '系统监控', icon: 'Odometer', ops: true }
    ]
  }
]

const mobileTabs = [
  { path: '/', name: '工作台', icon: HomeFilled },
  { path: '/lessons', name: '我的备课', icon: Collection },
  { path: '/library', name: '资源库', icon: FolderOpened },
  { path: '/knowledge', name: '知识库', icon: Reading },
  { path: '/settings', name: '设置', icon: Setting }
]

// 工作台内部自己滚，外层容器不能再垫 padding
const isWorkbench = computed(() => route.path === '/' || route.path === '/workbench')

const KEEP_ALIVE = ['WorkbenchView', 'LessonsView', 'LibraryView', 'GenerateView', 'AssistantView']

const currentName = computed(() => {
  const all = navGroups.flatMap(g => g.items)
  const hit = all.find(i => isActive(i))
  return hit ? hit.name : ''
})

const themeIcon = computed(() => {
  if (theme.mode === 'system') return Monitor
  return theme.isDark ? Moon : Sunny
})

const hasApiKey = computed(() => store.hasApiKey)

/**
 * 正在生成的产物名。
 *
 * 直接读备课台账里的 running 状态，不另建一套"忙碌标记" ——
 * 两套状态迟早会不一致（一个说在跑、一个说空闲），
 * 而这里的唯一职责就是如实反映"后端正在忙"。
 */
const lesson = useLessonStore()
const runningKinds = computed(() =>
  ARTIFACTS.filter(a => lesson.artifacts[a.id]?.status === 'running').map(a => a.name))

function isActive(item) {
  // /generate 与它的五个子类型都算命中"生成中心"
  if (item.path === '/generate') return route.path.startsWith('/generate')
  if (item.path === '/') return route.path === '/' || route.path === '/workbench'
  return route.path === item.path || route.path.startsWith(item.path + '/')
}

function onTheme(cmd) {
  theme.setMode(cmd)
}

onMounted(() => store.fetchConfig())
// 换了模型配置要立刻反映到顶栏的"演示模式"标识上
watch(() => store.hasApiKey, () => { demoDismissed.value = false })
</script>

<style scoped>
.shell {
  display: flex;
  height: 100%;
  background: var(--wb-bg);
}

/* ---------------- 侧边导航 ---------------- */
.shell__nav {
  width: var(--nav-w);
  flex: 0 0 var(--nav-w);
  background: var(--wb-surface);
  border-right: 1px solid var(--wb-border);
  display: flex;
  flex-direction: column;
  transition: width var(--dur) var(--ease), flex-basis var(--dur) var(--ease);
}

.shell--collapsed .shell__nav {
  width: var(--nav-w-collapsed);
  flex-basis: var(--nav-w-collapsed);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: var(--topbar-h);
  padding: 0 var(--sp-4);
  cursor: pointer;
  border-bottom: 1px solid var(--wb-border);
}

.brand__mark {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-soft-2);
  color: var(--brand-text);
}


.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  overflow: hidden;
}

.brand__text b { font-size: var(--fs-md); color: var(--wb-text); }
.brand__text small { font-size: 11px; color: var(--wb-text-3); }

.nav {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--sp-3) var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav__group {
  margin: var(--sp-3) var(--sp-2) var(--sp-1);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--wb-text-3);
}

.nav__item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 9px var(--sp-3);
  border-radius: var(--radius-sm);
  color: var(--wb-text-2);
  font-size: var(--fs-base);
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}

.nav__item:hover {
  background: var(--wb-hover);
  color: var(--wb-text);
}

.nav__item.is-active {
  background: var(--wb-active);
  color: var(--brand-text);
  font-weight: 600;
}


.nav__label { flex: 1 1 auto; overflow: hidden; white-space: nowrap; }

.nav__ops {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: var(--wb-surface-3);
  color: var(--wb-text-3);
}

.nav__collapse {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin: var(--sp-2);
  padding: 8px var(--sp-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--wb-text-3);
  font-size: var(--fs-sm);
  cursor: pointer;
}

.nav__collapse:hover { background: var(--wb-hover); color: var(--wb-text); }

/* ---------------- 主体 ---------------- */
.shell__body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: var(--topbar-h);
  flex: 0 0 var(--topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: 0 var(--sp-5);
  background: var(--wb-surface);
  border-bottom: 1px solid var(--wb-border);
}

.topbar__crumb { font-size: var(--fs-md); font-weight: 600; color: var(--wb-text); }
.topbar__right { display: flex; align-items: center; gap: var(--sp-3); }

.topbar__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-xs);
  background: var(--success-bg);
  color: var(--wb-ok-text);
}

.topbar__chip.is-demo {
  background: var(--warning-bg);
  color: var(--wb-warn-text);
}

.topbar__chip.is-running {
  background: var(--brand-soft);
  color: var(--brand-text);
}

.topbar__spinner {
  width: 10px;
  height: 10px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: topbar-spin 0.8s linear infinite;
}

@keyframes topbar-spin {
  to { transform: rotate(360deg); }
}

/* 窄屏保留"正在生成 X"，只砍掉解释性的后半句 —— 状态本身不能藏起来 */
@media (max-width: 900px) {
  .topbar__chip-extra { display: none; }
}

.topbar__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--wb-text-2);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}

.icon-btn:hover { background: var(--wb-hover); color: var(--wb-text); }

/* 演示模式横幅 */
.banner {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-5);
  background: var(--warning-bg);
  color: var(--wb-warn-text);
  font-size: var(--fs-sm);
  border-bottom: 1px solid var(--wb-border);
}

.banner a { color: inherit; font-weight: 600; text-decoration: underline; }

.banner__close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
}

.shell__main {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}

/* 工作台自己管理滚动，外层不垫 */
.shell__main--flush { overflow: hidden; }

.shell__footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-5);
  border-top: 1px solid var(--wb-border);
  background: var(--wb-surface);
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
}

/* ---------------- 移动端 ---------------- */
.tabbar { display: none; }

@media (max-width: 768px) {
  .shell__nav { display: none; }

  .topbar { padding: 0 var(--sp-3); }
  .topbar__right :deep(.wb-flow-badge) { display: none; }

  .shell__footer { display: none; }

  .tabbar {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    background: var(--wb-surface);
    border-top: 1px solid var(--wb-border);
    padding-bottom: env(safe-area-inset-bottom);
  }

  .tabbar__item {
    flex: 1 1 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 0;
    font-size: 11px;
    color: var(--wb-text-3);
  }

  .tabbar__item.is-active { color: var(--brand-text); font-weight: 600; }

  .shell__main { padding-bottom: 56px; }
}
</style>
