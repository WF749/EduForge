import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 课件（六阶段流程）+ 产物文件管理。
 *
 * 六阶段：`analyze → outline → detailed → visual → full`。
 * 分步接口存在的意义是让教师**在生成文件之前**就能改大纲 / 改风格，
 * 而不是等一整份 PPTX 出来再重来一遍。
 *
 * 注意：动画与游戏的生成接口也在这个域下（后端路由在 api/courseware.py），
 * 但它们的封装在 `api/lessonArtifacts.js`，那里与工作台的产物状态机绑在一起。
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

// ---- 六阶段 ---------------------------------------------------------------

export async function analyzeCoursewareRequirements(payload) {
  return readJson(await post('/courseware/analyze-requirements', payload), '需求解析失败')
}

export async function generateCoursewareOutline(requirements) {
  return readJson(await post('/courseware/generate-outline', { requirements }), '大纲生成失败')
}

export async function generateCoursewareDetailed({ outline, requirements }) {
  return readJson(
    await post('/courseware/generate-detailed-content', { outline, requirements }),
    '详细内容生成失败'
  )
}

export async function generateCoursewareVisualStyle({ topic, subject, audience }) {
  return readJson(
    await post('/courseware/generate-visual-style', { topic, subject, audience }),
    '视觉风格生成失败'
  )
}

export async function generateCoursewareFull(payload) {
  return readJson(await post('/courseware/generate-full', payload), '课件生成失败')
}

/** 直接生成（PPTX + DOCX 一步到位） */
export async function generateCourseware(payload) {
  return readJson(await post('/courseware/generate', payload), '课件生成失败')
}

// ---- 模板与预览 -----------------------------------------------------------

export async function fetchCoursewareTemplates() {
  const data = await readJson(
    await trackedFetch(`${BASE()}/courseware/templates`),
    '模板列表读取失败'
  )
  return Array.isArray(data.templates) ? data.templates : []
}

/** 只看大纲，不生成文件 —— 用来快速判断这个主题值不值得往下做 */
export async function previewCoursewareOutline(topic) {
  return readJson(
    await trackedFetch(`${BASE()}/courseware/preview?topic=${encodeURIComponent(topic)}`),
    '大纲预览失败'
  )
}

// ---- 产物文件 -------------------------------------------------------------

/**
 * 历史作品列表。
 *
 * 返回的是 courseware.py 里那份**带课程归属**的结构（含 download_url /
 * preview_url / delete_url / lesson）。后端有两处同名路由，先注册的生效，
 * 前端按这一份取数，不要照着 api_routes 那份的字段写。
 */
export async function listGeneratedFiles(topic = '') {
  const qs = topic ? `?topic=${encodeURIComponent(topic)}` : ''
  const data = await readJson(
    await trackedFetch(`${BASE()}/courseware/files${qs}`),
    '文件列表读取失败'
  )
  return Array.isArray(data.files) ? data.files : []
}

/** deleteUrl 由后端给出（带 source 参数），前端不要自己拼，避免拼错目录 */
export async function deleteGeneratedDir(deleteUrl) {
  return readJson(await trackedFetch(deleteUrl, { method: 'DELETE' }), '删除失败')
}

export function coursewareDownloadUrl({ fileType, taskDir, topic }) {
  const params = new URLSearchParams()
  if (taskDir) params.set('task_dir', taskDir)
  if (topic) params.set('topic', topic)
  const qs = params.toString()
  return `${BASE()}/courseware/download/${encodeURIComponent(fileType)}${qs ? '?' + qs : ''}`
}

export function animationDownloadUrl({ taskId, taskDir }) {
  const params = new URLSearchParams()
  if (taskId) params.set('task_id', taskId)
  if (taskDir) params.set('task_dir', taskDir)
  return `${BASE()}/courseware/animation/download?${params.toString()}`
}

export function gameDownloadUrl({ taskId, taskDir }) {
  const params = new URLSearchParams()
  if (taskId) params.set('task_id', taskId)
  if (taskDir) params.set('task_dir', taskDir)
  return `${BASE()}/courseware/game/download?${params.toString()}`
}

export async function fetchAnimationStyles() {
  const data = await readJson(
    await trackedFetch(`${BASE()}/courseware/animation/styles`),
    '动画风格读取失败'
  )
  return Array.isArray(data.styles) ? data.styles : []
}

export async function fetchGameTypes() {
  const data = await readJson(
    await trackedFetch(`${BASE()}/courseware/game/types`),
    '游戏类型读取失败'
  )
  return Array.isArray(data.types) ? data.types : []
}
