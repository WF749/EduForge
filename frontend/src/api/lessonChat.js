import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 课程内嵌对话（区别于 /chat 那个通用对话页）。
 *
 * 只负责"把这句话交给后端的对话管理器，把它的追问/确认带回来"，
 * 生成与修改动作不经过这里 —— 那些有各自的接口，走哪条由 chatAction.js 判定。
 *
 * ⚠️ 路径别改：后端真实路由是 `/api/chat/analyze`（api_routes.py 里 router 自带
 * prefix="/api"），不是 `/chat/dialogue`。曾写成后者，POST 打到 SPA 兜底路由上
 * 返回 405，而前端只提示"对话服务没响应"——静默坏了整条澄清链路。
 * scripts/smoke_api_contract.py 会逐个校验这里写的路径确实存在。
 */
const BASE = () => resolveApiBaseURL()

/** 后端 dialogue_manager 的返回是"对话动作"而不是内容，所以按 action 分开带回来 */
function normalize(data) {
  return {
    action: data.action || 'execute',
    message: data.message || '',
    missingFields: Array.isArray(data.missing_fields) ? data.missing_fields : [],
    fields: data.extracted_fields && typeof data.extracted_fields === 'object'
      ? data.extracted_fields
      : {},
    suggestions: Array.isArray(data.followup_suggestions) ? data.followup_suggestions : [],
    intentType: data.intent_type || '',
    confirmed: data.confirmed === true
  }
}

export async function postDialogue(conversationId, message) {
  const res = await trackedFetch(`${BASE()}/chat/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail || data?.message || '对话失败')
  return normalize(data)
}

/**
 * 清空对话时也要清后端上下文。
 * 否则教师点了"清空"，本地气泡没了但服务端还停在 CONFIRMING，
 * 下一句回答会被当成"对上一个需求的确认"。
 */
export async function resetDialogue(conversationId) {
  const res = await trackedFetch(`${BASE()}/chat/reset-dialogue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId })
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.detail || '重置对话失败')
  }
  return true
}

/**
 * 取回「智能体眼里的这节课」—— 界面用它如实展示系统记住了什么、每轮发给模型什么。
 *
 * 刻意由服务端返回原文，而不是前端按同样的格式自己拼一份：
 * 拼一份的话迟早与真正发出去的那份走偏，那就成了更糟的"看起来透明"。
 * 不调模型、不联网。
 */
export async function fetchLessonContext(lesson) {
  const res = await trackedFetch(`${BASE()}/lesson-chat/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail || data?.message || '读取上下文失败')
  return {
    context: data.context || '',
    system: data.system || '',
    historyTurns: Number(data.history_turns) || 0
  }
}

/**
 * 教学工作台问答（流式）。
 *
 * 与 `postDialogue` 的分工是这个模块存在的全部理由：
 *   - `postDialogue`（/chat/analyze）是**状态机** —— 判"这句话要生成什么、还缺哪些信息"；
 *   - 本函数（/lesson-chat/ask）是**真的回答问题** —— 教师问「什么是三角函数」要拿到解释。
 * 工作台以前只有前者，于是提问被当成"需求没说全"，一路反问到
 * 「你直接说要生成什么」。两条路都要有，不能拿一条去顶另一条。
 *
 * 流式而不是等整段返回：教师盯着对话框，首字延迟就是"卡不卡"的体感。
 */
export async function askLessonStream({
  conversationId,
  message,
  history = [],
  lesson = {},
  useKnowledge = true,
  signal,
  onDelta
}) {
  const res = await trackedFetch(`${BASE()}/lesson-chat/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      history,
      lesson,
      use_knowledge: useKnowledge
    })
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data?.detail || data?.message || `HTTP ${res.status}`)
  }
  if (!res.body) throw new Error('当前浏览器不支持流式响应')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let text = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      // SSE 以空行分隔事件；最后一段可能不完整，留在 buf 里等下一块
      const events = buf.split('\n\n')
      buf = events.pop() || ''
      for (const evt of events) {
        if (!evt.startsWith('data: ')) continue
        try {
          const d = JSON.parse(evt.slice(6))
          if (d.content) {
            text += d.content
            if (onDelta) onDelta(text)
          }
        } catch {
          // 单条事件解析失败不该中断整段回答：丢掉这一块，后面的照常收
        }
      }
    }
  } finally {
    // 主动中断（教师又发了下一句）也要释放连接，否则后端会继续跑到结束
    reader.cancel().catch(() => {})
  }
  return text
}
