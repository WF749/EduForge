import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 「一节课」台账的读写。
 *
 * 存在的理由：localStorage 只属于这一台浏览器的这一个 profile，
 * 换电脑、清缓存、换浏览器，"这一节课"和它的四类产物就一起失联了。
 * 后端台账是真源，localStorage 退化为离线兜底。
 *
 * 约定：台账读写失败一律不打断备课——它只是记账，不是生成链路的一环。
 */

const BASE = () => resolveApiBaseURL()

async function request(url, options = {}) {
  const res = await trackedFetch(url, options)
  const data = await res.json().catch(() => null)
  if (!res.ok || !data?.success) {
    throw new Error(data?.detail || data?.message || `请求失败（HTTP ${res.status}）`)
  }
  return data
}

function json(method, body) {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  }
}

export async function upsertTask(payload) {
  const data = await request(`${BASE()}/lesson-tasks`, json('POST', payload))
  return data.task
}

export async function fetchTask(taskId) {
  if (!taskId) throw new Error('缺少课程任务 ID')
  const data = await request(`${BASE()}/lesson-tasks/${encodeURIComponent(taskId)}`)
  return data.task
}

export async function fetchTasks(limit = 20, archived = null) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (archived !== null) params.set('archived', archived ? 'true' : 'false')
  const data = await request(`${BASE()}/lesson-tasks?${params.toString()}`)
  return data.tasks || []
}

/** 归档/取消归档。归档只影响列表可见性，文件与产物链接都还在。 */
export async function archiveTask(taskId, archived = true) {
  return request(
    `${BASE()}/lesson-tasks`,
    json('POST', { id: taskId, archived })
  )
}

export async function deleteTask(taskId) {
  return request(`${BASE()}/lesson-tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' })
}

export async function putArtifact(taskId, artifactType, artifact) {
  const data = await request(
    `${BASE()}/lesson-tasks/${encodeURIComponent(taskId)}/artifacts/${encodeURIComponent(artifactType)}`,
    json('PUT', artifact)
  )
  return data.artifact
}
