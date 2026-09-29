import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 深浅色主题。
 *
 * 为什么要有这个 store（而不是直接改 CSS class）：
 *  1. **刷新后要保持选择** —— 教师切换一次就该一直生效，不该每次进工作台都重来；
 *  2. 切换要**同时**改 Element Plus 的 `dark` class 与本项目的语义变量，
 *     只改一边会出现"面板变浅了、弹窗还是黑的"这种半吊子状态。
 *
 * 落地方式：只在 `<html>` 上写 `data-theme` 与 `dark` class，
 * 具体颜色一律由 CSS 变量给，组件不再各自硬编码 —— 否则加多少开关都是假的。
 */
const KEY = 'eduforge.theme'

function initial() {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* 隐私模式：退回默认 */
  }
  // 没选过就跟随系统；系统也没表态就用深色（与既有默认观感一致）
  try {
    if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light'
  } catch {
    /* 老浏览器没有 matchMedia */
  }
  return 'dark'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref('dark')

  const isDark = computed(() => theme.value !== 'light')

  function apply(next) {
    theme.value = next === 'light' ? 'light' : 'dark'
    const root = document.documentElement
    root.dataset.theme = theme.value
    // Element Plus 自己的暗色变量靠这个 class
    root.classList.toggle('dark', theme.value === 'dark')
    // 兼容既有写法：老代码里是用 `:root.light` 区分的
    root.classList.toggle('light', theme.value === 'light')
  }

  function toggle() {
    apply(theme.value === 'light' ? 'dark' : 'light')
    persist()
  }

  function setTheme(next) {
    apply(next)
    persist()
  }

  function persist() {
    try {
      localStorage.setItem(KEY, theme.value)
    } catch {
      /* 隐私模式：本次会话内仍有效，不必打断 */
    }
  }

  function init() {
    apply(initial())
  }

  return { theme, isDark, init, toggle, setTheme }
})
