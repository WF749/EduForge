import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 通用 AI 对话（区别于工作台里那一条带课程语境的 /lesson-chat/ask）。
 *
 * 五种模式对应五个后端端点，差别在**服务端怎么加工这句话**：
 *   stream        原样问答
 *   vision        视觉链路
 *   deep-thinking 前置"请逐步思考"
 *   search        先联网检索再回答
 *   deep-search   联网检索 + 要求标注哪些来自检索、哪些是推断
 * 网络不通时后端会在消息里注入"当前网络环境无法访问外部资源"，
 * 由服务端如实说明，前端不自己编造提示。
 */

const BASE = () => resolveApiBaseURL()

export const CHAT_MODES = [
  { value: 'stream', label: '普通问答', endpoint: '/chat/stream', hint: '直接回答，速度最快' },
  { value: 'vision', label: '视觉理解', endpoint: '/chat/vision', hint: '适合带图像理解的提问' },
  { value: 'deep-thinking', label: '深度思考', endpoint: '/chat/deep-thinking', hint: '先逐步推理再给结论，慢但更稳' },
  { value: 'search', label: '联网检索', endpoint: '/chat/search', hint: '先检索外部资料再回答，需要能上网' },
  { value: 'deep-search', label: '深度检索', endpoint: '/chat/deep-search', hint: '检索 + 逐步推理，并标注来源与推断' }
]

/**
 * 流式对话。
 *
 * 为什么自己解析 SSE 而不用 EventSource：EventSource 只能发 GET，
 * 而这里必须 POST（消息内容与附件都放在 body 里）。
 */
export async function streamChat({
  mode = 'stream',
  message,
  history = [],
  conversationId = '',
  useKnowledge = true,
  attachmentIds = [],
  signal,
  onDelta
}) {
  const def = CHAT_MODES.find(m => m.value === mode) || CHAT_MODES[0]

  const res = await trackedFetch(`${BASE()}${def.endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId,
      use_knowledge: useKnowledge,
      attachment_ids: attachmentIds
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
          // 单条事件解析失败不该中断整段回答
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
  return text
}

/** 把一段对话压成结构化需求（topic / audience / duration / difficulty / key_points） */
export async function summarizeRequirements(conversationId) {
  const res = await trackedFetch(`${BASE()}/chat/summarize-requirements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId })
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail || data?.message || '需求提取失败')
  return data?.requirements || null
}

/** 意图识别：courseware_generation / knowledge_qa / general / chitchat */
export async function understandIntent(message) {
  const res = await trackedFetch(`${BASE()}/chat/understand-intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail || '意图识别失败')
  return { intent: data?.intent || 'general', details: data?.details || {} }
}

export async function listConversations() {
  const res = await trackedFetch(`${BASE()}/chat/conversations`)
  const data = await res.json().catch(() => null)
  return Array.isArray(data?.conversations) ? data.conversations : []
}

export async function fetchHistory(conversationId) {
  if (!conversationId) return []
  const res = await trackedFetch(
    `${BASE()}/chat/history?conversation_id=${encodeURIComponent(conversationId)}`
  )
  const data = await res.json().catch(() => null)
  return Array.isArray(data?.history) ? data.history : []
}

export async function saveHistory(conversationId, history) {
  await trackedFetch(`${BASE()}/chat/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, history })
  })
}

export async function deleteConversation(conversationId) {
  await trackedFetch(
    `${BASE()}/chat/history?conversation_id=${encodeURIComponent(conversationId)}`,
    { method: 'DELETE' }
  )
}
