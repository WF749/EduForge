<template>
  <div class="app-wrapper">
    <!-- 背景效果 -->
    <div class="bg-grid"></div>
    <div class="bg-gradient"></div>
    <ParticleBackground />

    <!-- 顶部导航 -->
    <header class="app-header">
      <div class="header-left">
        <div class="logo-container">
          <div class="logo-icon">
            <svg viewBox="0 0 40 40" width="36" height="36">
              <defs>
                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#00c8ff"/>
                  <stop offset="50%" stop-color="#00ff88"/>
                  <stop offset="100%" stop-color="#7c3aed"/>
                </linearGradient>
              </defs>
              <circle cx="20" cy="20" r="18" fill="none" stroke="url(#logoGradient)" stroke-width="2.5"/>
              <circle cx="20" cy="20" r="10" fill="url(#logoGradient)" opacity="0.3"/>
              <circle cx="20" cy="20" r="5" fill="url(#logoGradient)"/>
              <circle cx="20" cy="12" r="2" fill="#fff" opacity="0.8"/>
            </svg>
          </div>
          <div class="logo-text">
            <span class="brand-name">EduForge</span>
            <span class="brand-tag">AI教学智能体</span>
          </div>
        </div>
      </div>

      <nav class="header-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.name }}</span>
          <div class="nav-indicator"></div>
        </router-link>
      </nav>

      <div class="header-right">
        <!-- 系统状态 -->
        <div class="system-status">
          <div class="status-item" :class="{ active: hasApiKey }">
            <span class="status-dot"></span>
            <span class="status-label">{{ hasApiKey ? '在线' : '演示' }}</span>
          </div>
          <!-- 数据流向：常驻展示，让"数据去了哪"每次都看得见 -->
          <DataFlowBadge />
          <div class="status-item">
            <el-icon :size="14"><Clock /></el-icon>
            <span class="status-label">{{ currentTime }}</span>
          </div>
        </div>

        <!-- 深浅色切换：放在顶栏，全站一致，不用每个页面各找一遍 -->
        <button
          class="theme-btn"
          type="button"
          :title="theme.isDark ? '切换到浅色' : '切换到深色'"
          :aria-label="theme.isDark ? '切换到浅色' : '切换到深色'"
          @click="theme.toggle()"
        >
          <el-icon :size="18"><component :is="theme.isDark ? Sunny : Moon" /></el-icon>
        </button>

        <!-- 设置按钮 -->
        <router-link to="/settings" class="settings-btn">
          <el-icon :size="20"><Setting /></el-icon>
        </router-link>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="slide-fade" mode="out-in">
          <keep-alive :include="['ChatView','CoursewareView','AnimationView','GameView','WorkbenchView']">
            <component :is="Component" />
          </keep-alive>
        </transition>
      </router-view>
    </main>

    <!-- 底部状态栏 -->
    <footer class="app-footer">
      <div class="footer-left">
        <div class="footer-brand">
          <svg viewBox="0 0 24 24" width="16" height="16" class="footer-icon">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="none" stroke="currentColor" stroke-width="2"/>
          </svg>
          <span>EduForge | AI 教学备课智能体</span>
        </div>
      </div>

      <div class="footer-center">
        <span class="copyright">© 2026 EduForge</span>
      </div>

      <div class="footer-right">
        <div class="tech-stack">
          <span class="tech-badge vue">Vue 3</span>
          <span class="tech-badge fastapi">FastAPI</span>
          <span class="tech-badge ai">AI</span>
          <span class="tech-badge rag">RAG</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/store/app'
import ParticleBackground from '@/components/ParticleBackground.vue'
import DataFlowBadge from '@/components/DataFlowBadge.vue'
import { useThemeStore } from '@/store/theme'
// 图标是全局注册的，这里导入只为导航栏数组使用
import { HomeFilled, Collection, Setting, Clock, Sunny, Moon } from '@element-plus/icons-vue'

const store = useAppStore()

const hasApiKey = computed(() => store.hasApiKey)
const currentTime = ref('')

// 导航只保留"围绕一节课"的入口。旧的功能页（/chat /courseware /animation /game）
// 路由仍然保留、可直接访问，只是不再占据导航栏——工作台出问题时有退路。
const theme = useThemeStore()

const navItems = [
  { path: '/', name: '备课工作台', icon: HomeFilled },
  { path: '/knowledge', name: '知识库', icon: Collection },
  { path: '/history', name: '历史作品', icon: Clock },
  { path: '/settings', name: '设置', icon: Setting }
]

// 更新时间
function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

let timeInterval = null

onMounted(async () => {
  await store.fetchConfig()
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style lang="scss" scoped>
.app-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

// 背景效果
.bg-grid {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image:
    linear-gradient(rgba(0, 200, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 200, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
  
  // 浅色主题适配
  :root.light & {
    background-image:
      linear-gradient(rgba(0, 200, 255, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 200, 255, 0.05) 1px, transparent 1px);
  }
}

.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(0, 200, 255, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(124, 58, 237, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(0, 255, 136, 0.04) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
  
  // 浅色主题适配 - 更淡的背景
  :root.light & {
    background:
      radial-gradient(ellipse at 20% 20%, rgba(0, 200, 255, 0.15) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(124, 58, 237, 0.08) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 50%, rgba(0, 255, 136, 0.05) 0%, transparent 70%);
  }
}

// 顶部导航
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 68px;
  padding: 0 28px;
  background: rgba(26, 31, 78, 0.98);
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  position: relative;
  z-index: 100;

  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%,
      rgba(0, 200, 255, 0.5) 20%,
      rgba(0, 255, 136, 0.5) 50%,
      rgba(124, 58, 237, 0.5) 80%,
      transparent 100%
    );
  }
}

.header-left {
  .logo-container {
    display: flex;
    align-items: center;
    gap: 14px;

    .logo-icon {
      position: relative;
      animation: logo-pulse 3s ease-in-out infinite;

      &::before {
        content: '';
        position: absolute;
        inset: -4px;
        background: radial-gradient(circle, rgba(0, 200, 255, 0.3) 0%, transparent 70%);
        border-radius: 50%;
        animation: logo-glow 2s ease-in-out infinite;
      }
    }

    .logo-text {
      display: flex;
      flex-direction: column;

      .brand-name {
        font-size: 20px;
        font-weight: 800;
        background: linear-gradient(135deg, #00c8ff 0%, #00ff88 50%, #7c3aed 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
        background-size: 200% auto;
        animation: text-gradient 4s ease infinite;
      }

      .brand-tag {
        font-size: 11px;
        color: var(--text-muted);
        letter-spacing: 1px;
      }
    }
  }
}

@keyframes logo-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}

@keyframes logo-glow {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.1); }
}

@keyframes text-gradient {
  0%, 100% { background-position: 0% center; }
  50% { background-position: 100% center; }
}

.header-nav {
  display: flex;
  gap: 6px;

  .nav-item {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 10px;
    color: #c8d0dc;
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.3s ease;

    .nav-indicator {
      position: absolute;
      bottom: 4px;
      left: 50%;
      transform: translateX(-50%) scaleX(0);
      width: 20px;
      height: 2px;
      background: linear-gradient(90deg, #00c8ff, #00ff88);
      border-radius: 1px;
      transition: transform 0.3s ease;
    }

    &:hover {
      background: rgba(0, 200, 255, 0.08);
      color: var(--primary);

      .nav-indicator {
        transform: translateX(-50%) scaleX(0.5);
      }
    }

    &.active {
      background: rgba(0, 200, 255, 0.12);
      color: var(--primary);

      .nav-indicator {
        transform: translateX(-50%) scaleX(1);
      }
    }
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;

  .system-status {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 6px 14px;
    background: rgba(0, 200, 255, 0.08);
    border: 1px solid rgba(0, 200, 255, 0.15);
    border-radius: 20px;

    .status-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #8b95a5;

      &.active {
        color: var(--accent);
      }

      .status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #ff6b6b;
        transition: background 0.3s ease;
      }

      &.active .status-dot {
        background: var(--accent);
        box-shadow: 0 0 8px var(--accent);
        animation: status-pulse 2s ease-in-out infinite;
      }

      .status-label {
        font-weight: 500;
      }
    }
  }

  // 主题切换按钮与设置按钮同一套尺寸与反馈，避免出现"看着像能点其实不能点"
  .theme-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    margin-right: 8px;
    padding: 0;
    border: 1px solid var(--wb-border);
    border-radius: 10px;
    background: var(--wb-surface-2);
    color: var(--wb-text-2);
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      color: var(--primary);
      border-color: var(--wb-border-strong);
      transform: translateY(-1px);
    }
    &:active {
      transform: translateY(0);
    }
  }

  .settings-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    color: #c8d0dc;
    text-decoration: none;
    transition: all 0.3s ease;

    &:hover {
      background: rgba(0, 200, 255, 0.1);
      color: var(--primary);
    }
  }
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// 主内容区
.app-main {
  flex: 1;
  overflow-y: auto;
  position: relative;
  z-index: 1;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 200, 255, 0.2);
    border-radius: 3px;
    &:hover {
      background: rgba(0, 200, 255, 0.4);
    }
  }
}

// 底部状态栏
.app-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 24px;
  background: rgba(26, 31, 78, 0.98);
  border-top: 1px solid rgba(0, 200, 255, 0.2);
  position: relative;
  z-index: 1;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%,
      rgba(0, 200, 255, 0.3) 30%,
      rgba(0, 255, 136, 0.3) 70%,
      transparent 100%
    );
  }

  .footer-left {
    .footer-brand {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #8b95a5;

      .footer-icon {
        color: var(--primary);
        opacity: 0.6;
      }
    }
  }

  .footer-center {
    .copyright {
      font-size: 11px;
      color: #8b95a5;
      opacity: 0.8;
    }
  }

  .footer-right {
    .tech-stack {
      display: flex;
      gap: 8px;

      .tech-badge {
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
        border-radius: 4px;
        letter-spacing: 0.5px;

        &.vue {
          background: rgba(66, 184, 131, 0.15);
          color: #42b883;
          border: 1px solid rgba(66, 184, 131, 0.3);
        }

        &.fastapi {
background: rgba(0, 150, 136, 0.15);
          color: #009688;
          border: 1px solid rgba(0, 150, 136, 0.3);
        }

        &.ai {
          background: rgba(124, 58, 237, 0.15);
          color: #a855f7;
          border: 1px solid rgba(124, 58, 237, 0.3);
        }

        &.rag {
          background: rgba(0, 200, 255, 0.15);
          color: var(--primary);
          border: 1px solid rgba(0, 200, 255, 0.3);
        }
      }
    }
  }
}

// 路由动画
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
