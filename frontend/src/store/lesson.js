import { defineStore } from 'pinia'
import { ref, reactive, computed, watch } from 'vue'

/**
 * 「一节课」的上下文与产物台账。
 *
 * 存在的理由：工作台围绕一节课工作，四类产物（教案/PPT/动画/游戏）共用同一份
 * 主题、学科、年级、时长、参考资料，不应该在每个面板里各存一份。
 *
 * 设计取舍：
 *  1. 只存"指针"不存"正文" —— 产物落盘在后端，这里只记 taskId / downloadUrl / 合规结论，
 *     刷新后能按图索骥找回，不会因为 localStorage 塞满正文而爆掉配额。
 *  2. 持久化失败一律静默 —— 隐私模式/配额满时不该让备课流程中断。
 *  3. 与 URL query 双向同步 —— 老页面（/courseware）仍能把需求带过来，不做孤岛。
 */

const STORAGE_KEY = 'eduforge.lesson.v1'

export const SUBJECTS = [
  '语文', '数学', '英语', '物理', '化学', '生物',
  '历史', '地理', '道德与法治', '科学', '信息科技', '艺术', '体育与健康'
]

export const GRADES = [
  '一年级', '二年级', '三年级', '四年级', '五年级', '六年级',
  '七年级', '八年级', '九年级', '高一', '高二', '高三'
]

export const DIFFICULTIES = [
  { value: 'easy', label: '入门级' },
  { value: 'medium', label: '中等难度' },
  { value: 'hard', label: '进阶深入' }
]

export const THEME_COLORS = ['蓝色系', '绿色系', '红色系', '紫色系', '橙色系']

/** 四类产物。id 与后端 artifact_type 对齐，顺序即批量生成顺序。 */
export const ARTIFACTS = [
  { id: 'lesson_plan', name: '教案', ext: 'docx', icon: 'Files', grad: 'files' },
  { id: 'ppt', name: 'PPT 课件', ext: 'pptx', icon: 'Document', grad: 'ppt' },
  { id: 'animation', name: '动画演示', ext: 'html', icon: 'VideoCamera', grad: 'anim' },
  { id: 'game', name: '互动游戏', ext: 'html', icon: 'TrophyBase', grad: 'game' }
]

function emptyArtifact() {
  return {
    status: 'idle', // idle | running | done | failed
    taskId: '',
    downloadUrl: '',
    previewUrl: '',
    previewRoute: '',
    compliance: null,
    summary: '',
    error: '',
    at: 0
  }
}

function emptyArtifacts() {
  return ARTIFACTS.reduce((acc, a) => {
    acc[a.id] = emptyArtifact()
    return acc
  }, {})
}

function levelForGrade(grade) {
  if (/^[一二三四五六]年级$/.test(grade || '')) return '小学'
  if (/^[七八九]年级$/.test(grade || '')) return '初中'
  return '普通高中'
}

export const useLessonStore = defineStore('lesson', () => {
  const topic = ref('')
  const subject = ref('数学')
  const grade = ref('七年级')
  const duration = ref(45)
  const difficulty = ref('medium')
  const keyPoints = ref('')
  const referenceFiles = ref([]) // [{ file_id, name }]
  const artifacts = reactive(emptyArtifacts())

  // 面板级选项也放在这里：批量生成要用和单个面板完全相同的参数，
  // 否则"一键生成全部"和"进面板单独生成"会产出两套东西。
  const pptTheme = ref('蓝色系')
  const animationMinutes = ref(5)
  const gameType = ref('选择题')

  // ---- 持久化 -------------------------------------------------------------
  let hydrated = false

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        topic: topic.value,
        subject: subject.value,
        grade: grade.value,
        duration: duration.value,
        difficulty: difficulty.value,
        keyPoints: keyPoints.value,
        referenceFiles: referenceFiles.value,
        pptTheme: pptTheme.value,
        animationMinutes: animationMinutes.value,
        gameType: gameType.value,
        artifacts
      }))
    } catch {
      /* 配额满或隐私模式：静默降级，不打断备课 */
    }
  }

  function hydrate() {
    if (hydrated) return
    hydrated = true
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw)
      if (typeof saved.topic === 'string') topic.value = saved.topic
      if (typeof saved.subject === 'string') subject.value = saved.subject
      if (typeof saved.grade === 'string') grade.value = saved.grade
      if (Number.isFinite(saved.duration)) duration.value = saved.duration
      if (typeof saved.difficulty === 'string') difficulty.value = saved.difficulty
      if (typeof saved.keyPoints === 'string') keyPoints.value = saved.keyPoints
      if (Array.isArray(saved.referenceFiles)) referenceFiles.value = saved.referenceFiles
      if (typeof saved.pptTheme === 'string') pptTheme.value = saved.pptTheme
      if (Number.isFinite(saved.animationMinutes)) animationMinutes.value = saved.animationMinutes
      if (typeof saved.gameType === 'string') gameType.value = saved.gameType
      if (saved.artifacts) {
        for (const a of ARTIFACTS) {
          const src = saved.artifacts[a.id]
          if (!src) continue
          // running 状态不恢复：进程早就没了，恢复成 running 会永久转圈
          Object.assign(artifacts[a.id], emptyArtifact(), src,
            src.status === 'running' ? { status: 'idle' } : {})
        }
      }
    } catch {
      /* 存档损坏：当作第一次使用 */
    }
  }

  hydrate()
  watch([topic, subject, grade, duration, difficulty, keyPoints, referenceFiles,
    pptTheme, animationMinutes, gameType, artifacts], persist, { deep: true })

  // ---- 派生 ---------------------------------------------------------------
  const ready = computed(() => !!topic.value.trim())
  const difficultyLabel = computed(
    () => (DIFFICULTIES.find(d => d.value === difficulty.value) || DIFFICULTIES[1]).label
  )
  const level = computed(() => levelForGrade(grade.value))
  const referenceIds = computed(() => referenceFiles.value.map(f => f.file_id).filter(Boolean))
  /** keyPoints 按行拆成要点数组，并把难度一并带下去（后端确实会用到） */
  const keyPointList = computed(() => {
    const lines = keyPoints.value.split('\n').map(s => s.trim()).filter(Boolean)
    lines.push(`内容难度：${difficultyLabel.value}`)
    return lines
  })
  const requirementsText = computed(() => {
    const base = keyPoints.value.trim()
    return base ? `${base}\n内容难度：${difficultyLabel.value}` : `内容难度：${difficultyLabel.value}`
  })

  const doneCount = computed(
    () => ARTIFACTS.filter(a => artifacts[a.id].status === 'done').length
  )
  const runningCount = computed(
    () => ARTIFACTS.filter(a => artifacts[a.id].status === 'running').length
  )

  // ---- 操作 ---------------------------------------------------------------
  function setContext(patch = {}) {
    for (const [k, v] of Object.entries(patch)) {
      if (k === 'topic') topic.value = v
      else if (k === 'subject') subject.value = v
      else if (k === 'grade') grade.value = v
      else if (k === 'duration') duration.value = v
      else if (k === 'difficulty') difficulty.value = v
      else if (k === 'keyPoints') keyPoints.value = v
    }
  }

  /** 换一节课：上下文与产物台账一起清空 */
  function resetLesson() {
    topic.value = ''
    subject.value = '数学'
    grade.value = '七年级'
    duration.value = 45
    difficulty.value = 'medium'
    keyPoints.value = ''
    referenceFiles.value = []
    pptTheme.value = '蓝色系'
    animationMinutes.value = 5
    gameType.value = '选择题'
    for (const a of ARTIFACTS) Object.assign(artifacts[a.id], emptyArtifact())
  }

  function addReference(file) {
    if (!file?.file_id) return
    if (referenceFiles.value.some(f => f.file_id === file.file_id)) return
    referenceFiles.value.push({ file_id: file.file_id, name: file.name || file.file_id })
  }

  function removeReference(fileId) {
    referenceFiles.value = referenceFiles.value.filter(f => f.file_id !== fileId)
  }

  function setArtifact(id, patch) {
    if (!artifacts[id]) return
    Object.assign(artifacts[id], patch)
  }

  function resetArtifact(id) {
    if (artifacts[id]) Object.assign(artifacts[id], emptyArtifact())
  }

  /** 从 URL query 恢复（老页面 /courseware 传参过来时用） */
  function applyQuery(q = {}) {
    if (q.topic) topic.value = q.topic
    if (q.subject) subject.value = q.subject
    if (q.audience || q.grade) grade.value = q.audience || q.grade
    if (q.duration) duration.value = parseInt(q.duration, 10) || duration.value
    if (q.difficulty) difficulty.value = q.difficulty
    if (q.key_points) keyPoints.value = q.key_points
    if (q.reference_files) {
      const ids = String(q.reference_files).split(',').filter(Boolean)
      const names = String(q.reference_names || '').split(',')
      referenceFiles.value = ids.map((file_id, i) => ({ file_id, name: names[i] || file_id }))
    }
  }

  function toQuery() {
    return {
      topic: topic.value,
      subject: subject.value,
      audience: grade.value,
      duration: String(duration.value),
      difficulty: difficulty.value,
      key_points: keyPoints.value,
      reference_files: referenceIds.value.join(','),
      reference_names: referenceFiles.value.map(f => f.name).join(',')
    }
  }

  return {
    topic, subject, grade, duration, difficulty, keyPoints, referenceFiles, artifacts,
    pptTheme, animationMinutes, gameType,
    ready, difficultyLabel, level, referenceIds, keyPointList, requirementsText,
    doneCount, runningCount,
    setContext, resetLesson, addReference, removeReference,
    setArtifact, resetArtifact, applyQuery, toQuery, persist
  }
})
