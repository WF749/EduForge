import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 课程内嵌对话（区别于 /chat 那个通用对话页）。
 *
 * 只负责"把这句话交给后端的对话管理器，把它的追问/确认带回来"，
 * 生成与修改动作不经过这里 —— 那些有各自的接口，走哪条由 chatAction.js 判定。
 */
const BASE = () => resolveApiBaseURL()

export async function postDialogue(conversationId, message) {
  const res = await trackedFetch(`${BASE()}/chat/dialogue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message })
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail || data?.message || '对话失败')
  return {
    action: data.action || 'execute',
    message: data.message || '',
    missingFields: Array.isArray(data.missing_fields) ? data.missing_fields : [],
    suggestions: Array.isArray(data.followup_suggestions) ? data.followup_suggestions : [],
    intentType: data.intent_type || ''
  }
}
