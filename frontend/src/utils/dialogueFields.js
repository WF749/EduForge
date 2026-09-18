/**
 * 把后端对话管理器给的"缺字段"翻成教师看得懂的中文。
 *
 * 为什么不能只写一张对照表：
 *   missing_fields 是**模型自由生成**的，不是固定的枚举。实测同一句"帮我设计一节关于浮力的课"，
 *   两次返回分别给了 ['course_name','grade_level','subject_area','learning_objectives','duration']
 *   和 ['grade_level','class_duration','learning_objectives','student_background',
 *       'available_resources_or_lab_equipment']。
 *   写死表必然漏，所以整名映射优先、剩下按 snake_case 逐词兜底。
 *
 * 兜底原则：翻不出来的**原样返回**，不猜、不编。教师看到一两个英文词，
 * 比看到一个自作主张译错的说法更不容易误解。
 */

/** 整名映射：覆盖实测出现过以及意图模板里声明的字段 */
const WHOLE = {
  course_name: '课程名称',
  subject: '学科',
  subject_area: '学科领域',
  grade: '年级',
  grade_level: '年级',
  class_duration: '课时时长',
  duration: '课时时长',
  learning_objectives: '学习目标',
  teaching_objectives: '教学目标',
  objectives: '教学目标',
  key_points: '重点',
  topic: '主题',
  theme: '主题',
  knowledge_points: '知识点',
  target_audience: '教学对象',
  student_background: '学生基础',
  students: '学生情况',
  available_resources_or_lab_equipment: '可用资源/实验器材',
  resources: '可用资源',
  requirements: '具体要求',
  resource_type: '资源类型',
  specific_question: '具体问题',
  specific_issue: '具体问题',
  difficulty: '难度',
  assessment: '评价方式',
  teaching_method: '教学方法',
  time_allocation: '时间分配'
}

/** 词级兜底：整名没命中时拆开逐词译 */
const WORD = {
  course: '课程', name: '名称', subject: '学科', area: '领域',
  grade: '年级', level: '水平', class: '课时', duration: '时长',
  time: '时间', allocation: '分配', learning: '学习', teaching: '教学',
  objective: '目标', objectives: '目标', goal: '目标', goals: '目标',
  point: '要点', points: '要点', key: '重点', topic: '主题', theme: '主题',
  target: '教学', audience: '对象', student: '学生', students: '学生',
  background: '基础', available: '可用', resource: '资源', resources: '资源',
  lab: '实验', equipment: '器材', requirement: '要求', requirements: '要求',
  safety: '安全', rule: '规则', rules: '规则',
  type: '类型', specific: '具体', question: '问题', issue: '问题',
  difficulty: '难度', assessment: '评价', method: '方法',
  content: '内容', knowledge: '知识点', activity: '活动', activities: '活动'
}

/** 连词/介词，拆词时丢掉，否则会译出"可用/资源/或/实验/器材"这种怪东西 */
const STOP = new Set(['or', 'and', 'the', 'of', 'for', 'with', 'a', 'an', 'in', 'on', 'to'])

/**
 * @param {string} name 后端给的字段名（英文 snake_case，也可能是模型自己造的）
 * @returns {string} 中文标签；翻不出来则原样返回
 */
export function fieldLabel(name) {
  const raw = String(name ?? '').trim()
  if (!raw) return ''

  const lower = raw.toLowerCase()
  if (WHOLE[lower]) return WHOLE[lower]
  // 中文直接返回：模型也可能直接给中文字段名
  if (/[一-龥]/.test(raw)) return raw

  const words = lower.split(/[^a-z0-9]+/).filter((w) => w && !STOP.has(w))
  const translated = words.map((w) => WORD[w] || '')
  // 一个词都译不出来就别硬凑，原样返回让教师看到后端真实给的东西
  if (!translated.some(Boolean)) return raw
  return translated.filter(Boolean).join('')
}

/**
 * 一组字段名 → 去重后的中文标签列表（保持原顺序）。
 * @param {string[]} fields
 */
export function fieldLabels(fields) {
  const out = []
  for (const f of Array.isArray(fields) ? fields : []) {
    const label = fieldLabel(f)
    if (label && !out.includes(label)) out.push(label)
  }
  return out
}
