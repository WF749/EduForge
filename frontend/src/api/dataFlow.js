/**
 * 数据流向追踪：把后端每次响应里的 X-Data-* 头记录下来，供界面展示。
 *
 * 为什么只做"记录"而不做拦截
 * --------------------------
 * 后端已经在发出请求之前完成了阻断（enforce 模式下请求根本没离开进程）。
 * 前端这里**不改变任何请求或响应**，只读取响应头 —— 这是纯观测，
 * 即使本模块出错也不可能影响生成功能。
 *
 * 为什么是拦截器而不是在每个调用点手写
 * ------------------------------------
 * 项目里有 4 个独立的 axios 实例（api/llm.js、store/app.js、
 * PreviewView.vue、SettingsView.vue）。在每个调用点读响应头会漏，
 * 装拦截器只需要在建实例的地方加一行。
 *
 * 用法：
 *   import { installDataFlowInterceptor } from '@/api/dataFlow'
 *   installDataFlowInterceptor(api)
 */

import { ref, computed } from 'vue'

// 后端写入的响应头（见 backend/app/core/middleware.py）
const HEADER_LEVEL = 'x-data-level'
const HEADER_ROUTE = 'x-data-route'
const HEADER_EGRESS = 'x-egress'
const HEADER_ACTION = 'x-data-action'
const HEADER_FINDINGS = 'x-data-findings'

/** 最近一次带流向信息的响应。null = 还没有发生过带判定的调用。 */
export const lastDataFlow = ref(null)

const LEVEL_TEXT = {
  L1: '公开数据',
  L2: '校内一般教学数据',
  L3: '敏感数据',
  L4: '重要数据',
  L5: '核心数据'
}

// action -> 展示文案与语义色（与项目"不静默、可自证"的取向一致）
const ACTION_META = {
  pass: { label: '未检测到敏感信息', tone: 'ok' },
  warn: { label: '已发往云端厂商', tone: 'warn' },
  redact: { label: '已脱敏后发往云端', tone: 'warn' },
  block: { label: '已拦截，未发出', tone: 'block' }
}

/** 给界面用的一句话结论。返回 null 表示还没有流向信息。 */
export const dataFlowSummary = computed(() => {
  const f = lastDataFlow.value
  if (!f || !f.level) return null

  const meta = ACTION_META[f.action] || ACTION_META.pass
  const inside = !f.egress
  return {
    ...f,
    levelText: LEVEL_TEXT[f.level] || f.level,
    actionLabel: meta.label,
    tone: meta.tone,
    // 校内处理永远是最安全的表述，优先级高于 action
    headline: inside
      ? '本次生成：校内处理，未出校'
      : f.action === 'redact'
        ? `本次生成：已发往云端厂商（已脱敏，定级 ${f.level}）`
        : f.action === 'block'
          ? `本次生成：已拦截，未发出（定级 ${f.level}）`
          : `本次生成：已发往云端厂商（定级 ${f.level}）`
  }
})

function _read(h, key) {
  const v = h?.[key]
  return typeof v === 'string' && v.trim() ? v.trim() : ''
}

/**
 * 给 axios 实例装上响应拦截器，记录数据流向。
 * 只读响应头，绝不修改 response —— 出错也只吞掉，不影响业务。
 */
export function installDataFlowInterceptor(instance) {
  if (!instance?.interceptors?.response) return instance

  instance.interceptors.response.use(
    (response) => {
      try {
        const h = response?.headers || {}
        const level = _read(h, HEADER_LEVEL)
        // 没有定级头 = 这次调用没经过合规判定（例如纯查询接口），不覆盖上一次结果
        if (level) {
          lastDataFlow.value = {
            level,
            route: _read(h, HEADER_ROUTE),
            egress: _read(h, HEADER_EGRESS) === 'true',
            action: _read(h, HEADER_ACTION) || 'pass',
            // 只放类型与数量（后端保证不放原文），这里原样透传
            findings: _read(h, HEADER_FINDINGS),
            at: Date.now()
          }
        }
      } catch {
        // 观测逻辑绝不阻断业务
      }
      return response
    },
    (error) => {
      // 403 阻断时 axios 走 error 分支，但响应头同样携带定级信息，必须也读一次
      try {
        const h = error?.response?.headers || {}
        const level = _read(h, HEADER_LEVEL)
        if (level) {
          lastDataFlow.value = {
            level,
            route: _read(h, HEADER_ROUTE),
            egress: _read(h, HEADER_EGRESS) === 'true',
            action: _read(h, HEADER_ACTION) || 'block',
            findings: _read(h, HEADER_FINDINGS),
            at: Date.now()
          }
        }
      } catch {
        /* 同上 */
      }
      return Promise.reject(error)
    }
  )
  return instance
}

/** 主动查询当前策略与出校目标（GET /api/safety/status）。 */
export async function fetchSafetyStatus(instance) {
  const res = await instance.get('/safety/status')
  return res?.data
}

/** 生成前预检（POST /api/safety/scan），本地执行、不调用模型。 */
export async function scanText(instance, text, { previewRedact = false } = {}) {
  const res = await instance.post('/safety/scan', {
    text,
    preview_redact: previewRedact
  })
  return res?.data
}
