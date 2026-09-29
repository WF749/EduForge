import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 四类产物的生成调用。集中在这里，是为了让"课程上下文 → 请求体"只有一份映射，
 * 工作台面板和老页面不会各自长出一套略有差异的字段。
 *
 * 约定：
 *  1. 一律抛 Error(message)，由 useArtifactRunner 收进 artifact.error。
 *  2. 只回传"指针"（taskId / downloadUrl / previewUrl），不回传正文。
 *  3. 所有请求走 trackedFetch，数据出校观测头不会漏采（红线 7）。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(response, fallback) {
  const data = await response.json()
  if (!response.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data
}

function post(path, body) {
  return trackedFetch(`${BASE()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

// ---- 教案 -----------------------------------------------------------------
export async function generateLessonPlan(ctx) {
  const created = await readJson(await post('/lesson-plan/generate-full', {
    level: ctx.level,
    subject: ctx.subject,
    grade: ctx.grade,
    topic: ctx.topic,
    duration: ctx.duration,
    requirements: ctx.requirements,
    reference_files: ctx.referenceIds,
    // 给了课程 id，后端会把成品落为该课教案的 v1 —— 之后的"按指令修改"才有基线
    lesson_id: ctx.lessonId || undefined,
    // 教学意图 / 蓝图 / 知识库范围：四路共用同一份，保证口径一致
    teaching_intent: ctx.teachingIntent,
    teaching_blueprint: ctx.teachingBlueprint,
    knowledge_scope: ctx.knowledgeScope
  }), '教案生成失败')

  if (!created.lesson_plan) throw new Error(created.message || '教案内容为空，请重试')

  // 只导出 docx：后端 llm_lesson_plan_all_stages.export_lesson_plan 对 pdf 的处理是
  // "PDF暂时生成docx"，给用户一个 PDF 选项是假的，所以这里不开这个口子。
  const exported = await readJson(await post('/lesson-plan/export', {
    lesson_plan: created.lesson_plan,
    export_format: 'docx',
    topic: ctx.topic
  }), '教案导出失败')

  if (!exported.download_url) throw new Error(exported.message || '教案导出未返回下载地址')

  return {
    downloadUrl: exported.download_url,
    // 教案是平铺文件（没有任务目录），用文件名作为归属依据
    fileName: exported.filename || '',
    compliance: created.compliance || null,
    summary: 'Word 教案已导出',
    // 引用与知识库使用情况：教师要知道这版依据了什么
    knowledge: created.knowledge || null,
    citations: Array.isArray(created.citations) ? created.citations.slice(0, 8) : [],
    contextMeta: created.teaching_blueprint || null
  }
}

// ---- 版本与迭代修改 --------------------------------------------------------

/**
 * 教案每一版的 docx 都是同一个文件名（按课题命名），所以改完重新导出会覆盖旧文件，
 * 下载链接保持不变、内容跟着更新 —— 不会出现"列表里是 v3、下载下来是 v1 的内容"。
 */
async function exportRevised(lessonPlan, topic, extra) {
  const exported = await readJson(await post('/lesson-plan/export', {
    lesson_plan: lessonPlan,
    export_format: 'docx',
    topic
  }), '教案导出失败')

  if (!exported.download_url) throw new Error(exported.message || '教案导出未返回下载地址')
  return {
    downloadUrl: exported.download_url,
    fileName: exported.filename || '',
    ...extra,
    summary: extra?.version?.version ? `第 ${extra.version.version} 版` : ''
  }
}

/**
 * 规则闸门之后的**可选**模型深度复查（默认关闭、手动触发、只报告）。
 *
 * 与生成接口不同：它不会改写任何内容，只是把"规则查不出来的问题"说给教师听。
 * 未开启时后端返回 enabled=false + reason，前端如实显示，不要假装审查过。
 */
export async function deepReview({ lessonId, kind = 'lesson_plan', ctx }) {
  const data = await readJson(await post('/teaching-compliance/review', {
    lesson_id: lessonId || undefined,
    kind,
    meta: {
      level: ctx?.level || '',
      topic: ctx?.topic || '',
      duration: ctx?.duration || undefined
    }
  }), '深度复查失败')

  const r = data.review || {}
  return {
    enabled: r.enabled === true,
    reason: r.reason || '',
    summary: r.summary || '',
    findings: Array.isArray(r.findings) ? r.findings : [],
    raw: r.raw === true
  }
}

/** 按教师的一句话指令修改教案（结果记为新版本，旧版本仍可回退） */
export async function reviseLessonPlan({ lessonId, instruction, ctx }) {
  const data = await readJson(await post('/lesson-plan/revise', {
    lesson_id: lessonId,
    instruction,
    level: ctx.level,
    subject: ctx.subject,
    grade: ctx.grade,
    duration: ctx.duration
  }), '教案修改失败')

  if (!data.lesson_plan) throw new Error(data.message || '修改结果为空，已保留原版本')

  return exportRevised(data.lesson_plan, ctx.topic, {
    version: data.version || null,
    changeLog: Array.isArray(data.change_log) ? data.change_log : [],
    compliance: data.compliance || null,
    message: data.message || ''
  })
}

export async function listVersions(lessonId, kind) {
  const q = `?lesson_id=${encodeURIComponent(lessonId)}&kind=${encodeURIComponent(kind)}`
  const data = await readJson(
    await trackedFetch(`${BASE()}/artifacts/versions${q}`),
    '版本历史读取失败'
  )
  return {
    current: Number(data.current || 0),
    versions: Array.isArray(data.versions) ? data.versions : []
  }
}

/** 回退到某一版。回退本身也是一个新版本，所以历史不会被截断。 */
export async function revertVersion({ lessonId, kind, version, ctx }) {
  const data = await readJson(await post('/artifacts/revert', {
    lesson_id: lessonId, kind, version
  }), '回退失败')

  // 回退只回元信息，正文要再取一次才能重新导出 docx
  const got = await readJson(
    await trackedFetch(
      `${BASE()}/artifacts/content?lesson_id=${encodeURIComponent(lessonId)}`
      + `&kind=${encodeURIComponent(kind)}&version=${Number(version)}`
    ),
    '读取回退后的内容失败'
  )
  if (!got.content) throw new Error('回退后的内容为空')

  return exportRevised(got.content, ctx.topic, {
    version: data.version || null,
    message: data.message || ''
  })
}

// ---- PPT ------------------------------------------------------------------
const PPT_MAX_ATTEMPTS = 300

/** 从后端给的绝对路径里取目录名，用于把产物归到某一节课 */
function dirNameOf(path) {
  const p = String(path || '').replace(/\\/g, '/').replace(/\/+$/, '')
  return p ? p.split('/').pop() : ''
}

export async function generatePpt(ctx, { themeColor = '蓝色系', onProgress } = {}) {
  const created = await readJson(await post('/ppt/generate', {
    topic: ctx.topic,
    duration: ctx.duration,
    audience: ctx.grade,
    subject: ctx.subject,
    theme_color: themeColor,
    // 后端默认与 prompt 里用的都是中文值，传英文会让 prompt 出现"风格偏好：professional"
    style_preference: '专业严谨',
    key_points: ctx.keyPoints,
    reference_docs: ctx.referenceIds,
    template: 'standard',
    teaching_intent: ctx.teachingIntent,
    teaching_blueprint: ctx.teachingBlueprint,
    knowledge_scope: ctx.knowledgeScope,
    lesson_id: ctx.lessonId || undefined
  }), 'PPT 任务创建失败')

  if (!created.task_id) throw new Error(created.message || 'PPT 任务创建失败')

  for (let i = 0; i < PPT_MAX_ATTEMPTS; i++) {
    const status = await readJson(
      await trackedFetch(`${BASE()}/ppt/status/${encodeURIComponent(created.task_id)}`),
      'PPT 状态读取失败'
    )
    if (typeof onProgress === 'function') {
      onProgress(Number(status.progress || 0), status.current_step || '')
    }
    if (status.status === 'completed' && status.result) {
      return {
        taskId: created.task_id,
        downloadUrl: `${BASE()}/ppt/download/${encodeURIComponent(created.task_id)}`,
        previewRoute: `/preview/${encodeURIComponent(created.task_id)}`,
        originDir: dirNameOf(status.result.task_dir),
        compliance: status.result.compliance || null,
        summary: `共 ${countSlides(status.result)} 页`,
        // 引用在发起时就确定了（快照），所以取发起时的那一份即可
        knowledge: created.knowledge || null,
        citations: Array.isArray(created.citations) ? created.citations.slice(0, 8) : [],
        contextMeta: created.context_meta || null
      }
    }
    if (status.status === 'failed' || status.status === 'unknown') {
      throw new Error(status.error || 'PPT 任务失败或已过期')
    }
    await new Promise(r => setTimeout(r, 1000))
  }
  throw new Error('PPT 生成超时（5 分钟），请稍后重试')
}

function countSlides(result) {
  const content = result.ppt_content
  if (!content) return 0
  if (Array.isArray(content.outline)) return content.outline.length
  if (Array.isArray(content.detailed_content)) return content.detailed_content.length
  if (Array.isArray(content.slides)) return content.slides.length
  return 0
}

// ---- 动画 -----------------------------------------------------------------
export async function generateAnimation(ctx, { minutes = 5 } = {}) {
  const data = await readJson(await post('/courseware/animation/generate', {
    topic: ctx.topic,
    subject: ctx.subject,
    audience: ctx.grade,
    teaching_content: ctx.teachingContent,
    duration: minutes,
    style: 'auto',
    teaching_intent: ctx.teachingIntent,
    teaching_blueprint: ctx.teachingBlueprint,
    knowledge_scope: ctx.knowledgeScope,
    lesson_id: ctx.lessonId || undefined
  }), '动画生成失败')

  const a = data.animation || {}
  if (!a.task_id && !a.task_dir) throw new Error(data.message || '动画生成未返回任务标识')

  const downloadUrl = a.task_id
    ? `${BASE()}/courseware/animation/download?task_id=${encodeURIComponent(a.task_id)}`
    : `${BASE()}/courseware/animation/download?task_dir=${encodeURIComponent(a.task_dir)}`

  return {
    taskId: a.task_id || '',
    downloadUrl,
    previewUrl: downloadUrl,
    originDir: dirNameOf(a.task_dir),
    compliance: data.compliance || null,
    offline: data.offline || null,
    summary: a.scenes?.length ? `${a.scenes.length} 个场景` : 'HTML5 动画',
    knowledge: data.knowledge || null,
    citations: Array.isArray(data.citations) ? data.citations.slice(0, 8) : [],
    contextMeta: data.context_meta || null
  }
}

// ---- 游戏 -----------------------------------------------------------------
export async function generateGame(ctx, { gameType } = {}) {
  const data = await readJson(await post('/courseware/game/generate', {
    topic: ctx.topic,
    audience: ctx.grade,
    teaching_content: ctx.teachingContent,
    game_type: gameType || undefined,
    teaching_intent: ctx.teachingIntent,
    teaching_blueprint: ctx.teachingBlueprint,
    knowledge_scope: ctx.knowledgeScope,
    lesson_id: ctx.lessonId || undefined
  }), '游戏生成失败')

  const g = data.game || {}
  if (!g.task_id && !g.task_dir) throw new Error(data.message || '游戏生成未返回任务标识')

  const downloadUrl = g.task_id
    ? `${BASE()}/courseware/game/download?task_id=${encodeURIComponent(g.task_id)}`
    : `${BASE()}/courseware/game/download?task_dir=${encodeURIComponent(g.task_dir)}`

  const count = g.game_data?.questions?.length || g.game_data?.cards?.length || 0
  return {
    taskId: g.task_id || '',
    downloadUrl,
    previewUrl: downloadUrl,
    originDir: dirNameOf(g.task_dir),
    compliance: data.compliance || null,
    offline: data.offline || null,
    summary: count ? `${count} 道题` : 'HTML5 可玩游戏',
    knowledge: data.knowledge || null,
    citations: Array.isArray(data.citations) ? data.citations.slice(0, 8) : [],
    contextMeta: data.context_meta || null
  }
}

/** 把 store 里的课程上下文映射成生成接口需要的形状 */
export function contextPayload(store) {
  const teachingContent = store.keyPoints.trim()
    ? `${store.keyPoints.trim()}\n内容难度：${store.difficultyLabel}`
    : store.topic
  return {
    lessonId: store.taskId || '',
    topic: store.topic.trim(),
    subject: store.subject,
    grade: store.grade,
    level: store.level,
    duration: store.duration,
    requirements: store.requirementsText,
    keyPoints: store.keyPointList,
    referenceIds: store.referenceIds,
    teachingContent,
    // 四路共用同一份教学意图 / 蓝图 / 知识库范围 ——
    // 不传的话四路各按自己的理解生成，同一节课给出四套说法。
    teachingIntent: store.intentPayload ? store.intentPayload() : undefined,
    teachingBlueprint: store.teachingBlueprint || undefined,
    knowledgeScope: store.knowledgeScope || 'both'
  }
}

/** 课程信息是否填完整；不完整的错误提示统一由这里给出 */
export function assertContext(store) {
  if (!store.topic.trim()) throw new Error('请先在这节课的顶部填写教学主题')
  if (!store.subject) throw new Error('请先选择学科')
  if (!store.grade) throw new Error('请先选择年级')
  return true
}
