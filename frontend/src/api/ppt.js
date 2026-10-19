import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * PPT 的任务态操作。
 *
 * 生成本身（/ppt/generate + /ppt/status 轮询）在 `api/lessonArtifacts.js`，
 * 因为它是工作台产物状态机的一环。这里放的是**生成之后**的动作：
 * 精修、修改、版本、回退。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(res, fallback) {
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data || {}
}

function post(path, body) {
  return trackedFetch(`${BASE()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

export function pptDownloadUrl(taskId) {
  return `${BASE()}/ppt/download/${encodeURIComponent(taskId)}`
}

/** 在线预览：拿的是 ppt_data.json（结构化内容），不是文件流 */
export async function fetchPptPreview(taskId) {
  return readJson(
    await trackedFetch(`${BASE()}/ppt/preview/${encodeURIComponent(taskId)}`),
    'PPT 数据读取失败'
  )
}

/** 按指令精修（refine）：与 modify 的区别是它走模型重写，不要求先给 modifications 结构 */
export async function refinePpt(taskId, instruction) {
  return readJson(
    await post(`/ppt/refine/${encodeURIComponent(taskId)}`, { instruction }),
    'PPT 精修失败'
  )
}

/** 结构化修改：modifications 是 { 页码: 改动说明 } 之类的后端约定结构 */
export async function modifyPpt(taskId, modifications) {
  return readJson(
    await post(`/ppt/modify/${encodeURIComponent(taskId)}`, { modifications }),
    'PPT 修改失败'
  )
}

export async function fetchPptVersions(taskId) {
  return readJson(
    await trackedFetch(`${BASE()}/ppt/versions/${encodeURIComponent(taskId)}`),
    '版本列表读取失败'
  )
}

/** 回退是非破坏性的：把目标版本复制成一个新版本，历史不会被截断 */
export async function revertPpt(taskId, version) {
  return readJson(
    await post(`/ppt/revert/${encodeURIComponent(taskId)}`, { version }),
    '回退失败'
  )
}
