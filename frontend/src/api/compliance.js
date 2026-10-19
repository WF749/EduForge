import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 教学合规校验器（R1–R8，纯规则离线，零额度）。
 *
 * 深度复查（review）是**可选**的模型能力，默认关闭且必须手动触发。
 * 未开启时后端返回 enabled=false + reason，这里原样带回，
 * 由界面如实显示"未开启" —— 不能假装审查过。
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

/** artifact_type: lesson_plan / ppt / courseware / game / animation */
export async function checkCompliance({ artifactType, content, meta }) {
  return readJson(await post('/teaching-compliance/check', {
    artifact_type: artifactType,
    content,
    meta: meta || {}
  }), '合规扫描失败')
}

/** 规则闸门之后的模型深度复查。content 留空时从版本链读当前版本。 */
export async function reviewArtifact({ artifactType = 'lesson_plan', content = '', lessonId, kind = 'lesson_plan', meta }) {
  return readJson(await post('/teaching-compliance/review', {
    artifact_type: artifactType,
    content,
    lesson_id: lessonId || undefined,
    kind,
    meta: meta || {}
  }), '深度复查失败')
}
