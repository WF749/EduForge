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
