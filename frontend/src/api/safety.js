import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 数据出校合规（L1–L5）。
 *
 * 与「教学合规 R1–R8」是两套东西，别混：
 * 这里管的是"这段内容能不能发到校外"，那边管的是"这份教案合不合教学规范"。
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

/** 当前策略：模式、阻断级别、目标是否出校。 */
export async function fetchSafetyStatus() {
  return readJson(await trackedFetch(`${BASE()}/safety/status`), '合规状态读取失败')
}

/**
 * 本地预检：定级 + 路由决策 + 可选脱敏预览。
 *
 * 全程不联网、不调模型 —— 所以可以放心在教师还没点生成时就跑，
 * 让他提前知道"这段内容会按 L几 处理"，而不是等生成被拦下来再解释。
 */
export async function scanSafety({ text, previewRedact = false }) {
  return readJson(await post('/safety/scan', {
    text,
    preview_redact: previewRedact
  }), '预检失败')
}
