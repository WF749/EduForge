import { defineStore } from 'pinia'
import { ref, reactive, computed, watch } from 'vue'
import { upsertTask, fetchTask, putArtifact, fetchTasks, archiveTask } from '@/api/lessonTasks'

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
  // 后端台账里的课程任务 ID。空表示还没建过（要等主题填了才建，避免留下一堆空课）。
  const taskId = ref('')
  const syncedAt = ref(0)
  // 最近课程（未归档），用于课程切换器
  const recentTasks = ref([])

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
        taskId: taskId.value,
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
      if (typeof saved.taskId === 'string') taskId.value = saved.taskId
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

  // ---- 后端台账同步 -------------------------------------------------------
  // 先读本地存档保证首屏立刻有内容，再异步去后端拉权威版本覆盖。
  // 顺序不能反：等网络返回再渲染，用户会看到一屏空白。
  let syncTimer = null

  function scheduleSync() {
    if (!topic.value.trim()) return
    clearTimeout(syncTimer)
    syncTimer = setTimeout(syncContext, 800)
  }

  async function syncContext() {
    if (!topic.value.trim()) return
    try {
      const task = await upsertTask({
        id: taskId.value || undefined,
        topic: topic.value,
        subject: subject.value,
        grade: grade.value,
        duration: duration.value,
        difficulty: difficulty.value,
        keyPoints: keyPoints.value,
        references: referenceFiles.value,
        options: {
          pptTheme: pptTheme.value,
          animationMinutes: animationMinutes.value,
          gameType: gameType.value
        }
      })
      const isNew = !taskId.value
      taskId.value = task.id
      syncedAt.value = Date.now()
      // 只在"第一次建课"时刷新列表：之后每次输入都刷会让接口被防抖流淹没
      if (isNew) await loadRecent()
    } catch {
      /* 台账写不进去不影响本地备课，静默降级 */
    }
  }

  /** 生成结束（成功或失败）后把产物状态记进台账 */
  async function pushArtifact(id) {
    if (!artifacts[id]) return
    // 生成耗时一般远超 800ms 防抖，但"填完主题立刻点生成"会赶在落库之前 ——
    // 这时先补一次建课，否则这条产物会无处可记。
    if (!taskId.value) await syncContext()
    if (!taskId.value) return
    try {
      await putArtifact(taskId.value, id, artifacts[id])
    } catch {
      /* 同上：记账失败不打断备课 */
    }
  }

  /** 拉取最近课程（未归档），用于课程切换器 */
  async function loadRecent(limit = 12) {
    try {
      recentTasks.value = await fetchTasks(limit, false)
    } catch {
      recentTasks.value = []
    }
    return recentTasks.value
  }

  /**
   * 切换到另一节课。
   * 顺序很关键：**先**把当前课同步回台账，**再**改 taskId ——
   * 反了的话当前课的上下文会写进即将切换到的那节课上，直接覆盖掉它。
   */
  async function switchTask(id) {
    if (!id || id === taskId.value) return true
    if (topic.value.trim()) await syncContext()
    taskId.value = id
    const ok = await restoreFromServer()
    await loadRecent()
    return ok
  }

  /** 归档/取消归档当前课。归档后清空工作台，方便开始下一节。 */
  async function setArchived(archived) {
    if (!taskId.value) return false
    try {
      await archiveTask(taskId.value, archived)
      if (archived) resetLesson()
      await loadRecent()
      return true
    } catch {
      return false
    }
  }

  /** 从后端台账恢复这一节课；返回是否成功 */
  async function restoreFromServer() {
    if (!taskId.value) return false
    try {
      const task = await fetchTask(taskId.value)
      if (!task) return false
      if (typeof task.topic === 'string') topic.value = task.topic
      if (typeof task.subject === 'string') subject.value = task.subject
      if (typeof task.grade === 'string') grade.value = task.grade
      if (Number.isFinite(task.duration)) duration.value = task.duration
      if (typeof task.difficulty === 'string') difficulty.value = task.difficulty
      if (typeof task.keyPoints === 'string') keyPoints.value = task.keyPoints
      if (Array.isArray(task.references)) referenceFiles.value = task.references
      if (task.options) {
        if (typeof task.options.pptTheme === 'string') pptTheme.value = task.options.pptTheme
        if (Number.isFinite(task.options.animationMinutes)) {
          animationMinutes.value = task.options.animationMinutes
        }
        if (typeof task.options.gameType === 'string') gameType.value = task.options.gameType
      }
      if (task.artifacts) {
        for (const a of ARTIFACTS) {
          const src = task.artifacts[a.id]
          if (!src) continue
          // 服务端的 running 一律降级：那意味着上一次生成是被中断的（进程重启），
          // 没有后台任务在跑，恢复成 running 会永远转圈。
          Object.assign(artifacts[a.id], emptyArtifact(), src,
            src.status === 'running' ? { status: 'idle', error: '上次生成被中断，请重新生成' } : {})
        }
      }
      return true
    } catch {
      return false
    }
  }

  watch([topic, subject, grade, duration, difficulty, keyPoints, referenceFiles,
    pptTheme, animationMinutes, gameType], scheduleSync)

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
    taskId.value = ''
    syncedAt.value = 0
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
    pptTheme, animationMinutes, gameType, taskId, syncedAt,
    ready, difficultyLabel, level, referenceIds, keyPointList, requirementsText,
    doneCount, runningCount,
    recentTasks,
    setContext, resetLesson, addReference, removeReference,
    setArtifact, resetArtifact, applyQuery, toQuery, persist,
    syncContext, pushArtifact, restoreFromServer,
    loadRecent, switchTask, setArchived
  }
})
