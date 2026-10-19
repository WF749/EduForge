import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 教案域里工作台没直接用到的部分：大学专业配置、分步流程、文件列表。
 *
 * 生成 / 修改 / 导出在 `api/lessonArtifacts.js`（与产物状态机绑定），这里不重复。
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

// ---- 大学专业配置 ---------------------------------------------------------

export async function fetchUniversityMajors() {
  const d = await readJson(
    await trackedFetch(`${BASE()}/lesson-plan/university/majors`),
    '专业列表读取失败'
  )
  return Array.isArray(d.majors) ? d.majors : []
}

export async function fetchUniversityDisciplines() {
  const d = await readJson(
    await trackedFetch(`${BASE()}/lesson-plan/university/disciplines`),
    '学科门类读取失败'
  )
  return Array.isArray(d.disciplines) ? d.disciplines : []
}

export async function fetchMajorsByDiscipline(disciplineCode) {
  const d = await readJson(
    await trackedFetch(
      `${BASE()}/lesson-plan/university/majors-by-discipline?discipline_code=${encodeURIComponent(disciplineCode)}`
    ),
    '专业列表读取失败'
  )
  return Array.isArray(d.majors) ? d.majors : []
}

export async function fetchMajorConfig(majorName) {
  const d = await readJson(
    await trackedFetch(
      `${BASE()}/lesson-plan/university/major-config?major_name=${encodeURIComponent(majorName)}`
    ),
    '专业配置读取失败'
  )
  return d.config || null
}

// ---- 分步流程 -------------------------------------------------------------

export async function analyzeLessonPlanRequirements(payload) {
  return readJson(await post('/lesson-plan/analyze-requirements', payload), '需求解析失败')
}

export async function generateLessonPlanOutline(requirements) {
  return readJson(await post('/lesson-plan/generate-outline', { requirements }), '大纲生成失败')
}

export async function generateLessonPlanDetailed({ outline, requirements }) {
  return readJson(
    await post('/lesson-plan/generate-detailed-content', { outline, requirements }),
    '详细内容生成失败'
  )
}

export async function validateLessonPlanCompliance({ lessonPlan, level, subject }) {
  return readJson(
    await post('/lesson-plan/validate-compliance', {
      lesson_plan: lessonPlan,
      level,
      subject
    }),
    '合规校验失败'
  )
}

/** 从已有 PPT 内容反推教案：PPT 先做完了，教案要跟它对得上时用 */
export async function generateLessonPlanFromPpt(payload) {
  return readJson(await post('/lesson-plan/generate-from-ppt', payload), '从 PPT 生成教案失败')
}

// ---- 文件 -----------------------------------------------------------------

export async function listLessonPlanFiles() {
  const d = await readJson(
    await trackedFetch(`${BASE()}/lesson-plan/files`),
    '教案文件列表读取失败'
  )
  return Array.isArray(d.files) ? d.files : []
}

export function lessonPlanDownloadUrl(filename) {
  return `${BASE()}/lesson-plan/download?filename=${encodeURIComponent(filename)}`
}
