import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 主题：浅色 / 深色 / 跟随系统。
 *
 * 为什么要有这个 store（而不是直接改 CSS class）：
 *  1. **刷新后要保持选择** —— 教师切换一次就该一直生效，不该每次进来重来；
 *  2. 切换要**同时**改 Element Plus 的 `dark` class 与本项目的语义变量。
 *     只改一边会出现"面板变浅了、弹窗还是黑的"这种半吊子状态；
 *  3. "跟随系统"不是一次性读值，而是要**监听系统变化** —— 教师白天用浅色、
 *     晚上系统转深色，界面应该跟着变，而不是等他手动切。
 *
 * 落地方式：只在 `<html>` 上写 `data-theme` 与 `dark` class，
 * 具体颜色一律由 CSS 变量给，组件不再各自硬编码。
 */

const KEY = 'eduforge.theme'
/** system 是默认值：新用户第一次打开就是这个，不需要先做选择 */
const MODES = ['light', 'dark', 'system']

function readSaved() {
  try {
    const saved = localStorage.getItem(KEY)
    if (MODES.includes(saved)) return saved
  } catch {
    /* 隐私模式：退回默认 */
  }
  return 'system'
}

function systemPrefersDark() {
  try {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches === true
  } catch {
    return false
  }
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref('system')
  /** 系统当前的深浅倾向（仅 mode==='system' 时影响实际呈现） */
  const systemDark = ref(false)

  /** 实际生效的主题：写进 data-theme 的就是这个值 */
  const resolved = computed(() => {
    if (mode.value === 'system') return systemDark.value ? 'dark' : 'light'
    return mode.value
  })
  const isDark = computed(() => resolved.value === 'dark')

  let media = null

  function apply() {
    const root = document.documentElement
    root.dataset.theme = resolved.value
    // Element Plus 自己的暗色变量靠这个 class
    root.classList.toggle('dark', isDark.value)
    // 兼容既有写法：老代码里是用 `:root.light` 区分的
    root.classList.toggle('light', !isDark.value)
  }

  function onSystemChange(e) {
    systemDark.value = e.matches === true
    apply()
  }

  function setMode(next) {
    if (!MODES.includes(next)) next = 'system'
    mode.value = next
    persist()
    apply()
  }

  function toggle() {
    // 切的是"明确值"：从跟随系统里点一下，落到与当前相反的那一侧
    setMode(isDark.value ? 'light' : 'dark')
  }

  function persist() {
    try {
      localStorage.setItem(KEY, mode.value)
    } catch {
      /* 隐私模式：本次会话内仍有效，不必打断 */
    }
  }

  function init() {
    mode.value = readSaved()
    systemDark.value = systemPrefersDark()
    try {
      media = window.matchMedia('(prefers-color-scheme: dark)')
      // Safari < 14 只有 addListener
      if (media.addEventListener) media.addEventListener('change', onSystemChange)
      else if (media.addListener) media.addListener(onSystemChange)
    } catch {
      /* 老浏览器没有 matchMedia：保持一次性读值即可 */
    }
    // 必须在挂载**之前**定好：否则首帧会先按另一套色画一遍再跳过去，教师看到闪屏
    apply()
  }

  return { mode, resolved, isDark, systemDark, init, setMode, toggle }
})
