<template>
  <div class="wb-page">
    <PageHeader
      :title="current.name"
      :description="current.desc"
      :badge="`第 ${stepIndex + 1} / ${steps.length} 步`"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" @click="$router.push('/')">回工作台</el-button>
      </template>
    </PageHeader>

    <!-- 类型切换 -->
    <el-tabs v-model="activeType" type="card" class="type-tabs" @tab-change="onTypeChange">
      <el-tab-pane v-for="t in TYPES" :key="t.id" :label="t.name" :name="t.id" />
    </el-tabs>

    <p class="type-note">
      「课件（六阶段）」和「PPT 课件」的区别：前者中途能看到并修改大纲与视觉风格，
      后者一步出成品。只是想快速拿到一份，选 PPT 课件。
      <br>
      这里是高级单项生成；日常备课直接在工作台说一句话就行，产物会自动归入那一节备课。
    </p>

    <div class="layout">
      <!-- 左：表单 -->
      <section class="wb-card wb-card-pad form">
        <div class="form__head">
          <b>生成参数</b>
          <el-button text size="small" @click="useCurrent">
            <el-icon><Refresh /></el-icon>
            用当前工作台的备课
          </el-button>
        </div>

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="教学主题" required>
            <el-input
              v-model="f.topic"
              placeholder="例如：浮力 / 二次函数的应用"
              maxlength="60"
              :class="{ 'is-invalid': touched && !f.topic.trim() }"
            />
            <p v-if="touched && !f.topic.trim()" class="field-error">请填写教学主题</p>
          </el-form-item>

          <div class="wb-row" style="gap: var(--sp-3)">
            <el-form-item label="学科 / 专业" class="wb-grow">
              <el-select v-model="f.subject" filterable allow-create>
                <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="年级 / 受众" class="wb-grow">
              <el-select v-model="f.grade" filterable allow-create>
                <el-option v-for="g in GRADES" :key="g" :label="g" :value="g" />
                <el-option label="大学生" value="大学生" />
              </el-select>
            </el-form-item>
            <el-form-item label="时长（分钟）" class="wb-grow">
              <el-input-number v-model="f.duration" :min="15" :max="180" :step="5" />
            </el-form-item>
          </div>

          <!-- 教案专属：大学专业配置 -->
          <el-form-item v-if="activeType === 'lesson-plan'">
            <template #label>
              大学专业配置
              <el-tooltip content="只有大学阶段的教案需要；选定后会带出该专业的培养定位。" placement="top">
                <el-icon class="wb-muted"><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
            <div class="wb-row" style="gap: var(--sp-2)">
              <el-select
                v-model="discipline"
                placeholder="学科门类"
                clearable
                style="width: 160px"
                @change="onDiscipline"
              >
                <el-option v-for="d in disciplines" :key="d.code" :label="d.name" :value="d.code" />
              </el-select>
              <el-select v-model="major" placeholder="专业" clearable style="width: 200px" @change="onMajor">
                <el-option v-for="m in majors" :key="m.name || m" :label="m.name || m" :value="m.name || m" />
              </el-select>
            </div>
            <p v-if="majorConfig" class="wb-muted" style="font-size: var(--fs-xs)">
              {{ majorConfig.summary || majorConfig.description || '已载入该专业配置' }}
            </p>
          </el-form-item>

          <el-form-item :label="current.contentLabel">
            <el-input
              v-model="f.teachingContent"
              type="textarea"
              :rows="3"
              :placeholder="current.contentPlaceholder"
            />
          </el-form-item>

          <!-- 类型专属参数 -->
          <div class="wb-row" style="gap: var(--sp-3)">
            <el-form-item v-if="activeType === 'ppt'" label="主题色" class="wb-grow">
              <el-select v-model="f.themeColor">
                <el-option v-for="c in THEME_COLORS" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="activeType === 'ppt'" label="风格" class="wb-grow">
              <el-select v-model="f.stylePreference">
                <el-option v-for="s in STYLES" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="activeType === 'animation'" label="动画风格" class="wb-grow">
              <el-select v-model="f.animStyle">
                <el-option v-for="s in animStyles" :key="s.value || s" :label="s.label || s" :value="s.value || s" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="activeType === 'animation'" label="动画时长（分钟）" class="wb-grow">
              <el-input-number v-model="f.animMinutes" :min="1" :max="15" />
            </el-form-item>
            <el-form-item v-if="activeType === 'game'" label="游戏类型" class="wb-grow">
              <el-select v-model="f.gameType">
                <el-option v-for="g in gameTypes" :key="g.value || g" :label="g.label || g" :value="g.value || g" />
              </el-select>
            </el-form-item>
          </div>

          <!-- 参考资料 -->
          <el-form-item label="参考资料">
            <el-select
              v-model="f.referenceFiles"
              multiple
              clearable
              placeholder="（可选）选择已上传的资料"
              style="width: 100%"
              :loading="loadingFiles"
            >
              <el-option v-for="file in files" :key="file.file_id" :label="file.filename" :value="file.file_id" />
            </el-select>
            <p class="wb-muted" style="font-size: var(--fs-xs)">
              在「知识库」里上传的资料会出现在这里。选中后本页生成会带上它们的内容。
            </p>
          </el-form-item>

          <el-form-item label="知识库范围">
            <el-radio-group v-model="f.scope">
              <el-radio value="both">内置 + 我的资料</el-radio>
              <el-radio value="system">仅内置</el-radio>
              <el-radio value="personal">仅我的资料</el-radio>
              <el-radio value="none">不使用</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>

        <div class="form__foot">
          <el-button
            type="primary"
            size="large"
            :loading="running"
            :disabled="running"
            @click="onGenerate"
          >
            {{ running ? '生成中…' : current.actionText }}
          </el-button>
          <span class="wb-muted" style="font-size: var(--fs-xs)">
            {{ current.timeHint }}
          </span>
        </div>
      </section>

      <!-- 右：结果 -->
      <section class="wb-card wb-card-pad result">
        <div class="wb-row wb-row-between">
          <b>生成结果</b>
          <StatusTag v-if="resultStatus" :status="resultStatus" />
        </div>

        <el-progress
          v-if="running && activeType === 'ppt'"
          :percentage="pptProgress"
          :stroke-width="8"
          style="margin-top: var(--sp-3)"
        />
        <p v-if="running" class="wb-muted" style="font-size: var(--fs-sm)">
          {{ pptStep || '正在生成，请稍候…' }}
        </p>

        <StateBlock
          :loading="false"
          :error="resultError"
          :empty="!running && !resultError && !result"
          :empty-title="current.emptyTitle"
          :empty-description="current.emptyDesc"
          :retryable="false"
        >
          <div v-if="result" class="wb-stack">
            <!-- 通用：摘要 -->
            <div v-if="result.summary" class="wb-row">
              <span class="wb-dim" style="font-size: var(--fs-sm)">{{ result.summary }}</span>
            </div>

            <!-- 教案：正文预览 + 导出 -->
            <template v-if="activeType === 'lesson-plan'">
              <div class="preview" v-html="lessonPlanHtml" />
              <div class="wb-row">
                <el-button :loading="exporting" @click="onExportLessonPlan">
                  <el-icon><Download /></el-icon>
                  导出 Word
                </el-button>
                <el-button v-if="downloadUrl" text @click="openUrl(downloadUrl)">打开已导出文件</el-button>
              </div>
            </template>

            <!-- 课件六阶段：分步结果 -->
            <template v-if="activeType === 'courseware'">
              <el-collapse v-model="openPanels">
                <el-collapse-item v-if="result.requirements" title="① 需求说明书" name="req">
                  <pre class="dump">{{ dump(result.requirements) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="result.outline" title="② 大纲" name="outline">
                  <pre class="dump">{{ dump(result.outline) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="result.detailed" title="③ 详细内容" name="detail">
                  <pre class="dump">{{ dump(result.detailed) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="result.style" title="④ 视觉风格" name="style">
                  <pre class="dump">{{ dump(result.style) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="result.files" title="⑤ 生成的文件" name="files">
                  <ul class="file-list">
                    <li v-for="(v, k) in result.files" :key="k">
                      <span>{{ k }}</span>
                      <el-button size="small" text @click="openUrl(coursewareDownloadUrl({ fileType: k, taskDir: result.taskDir, topic: f.topic }))">
                        下载
                      </el-button>
                    </li>
                  </ul>
                </el-collapse-item>
              </el-collapse>
            </template>

            <!-- PPT -->
            <template v-if="activeType === 'ppt'">
              <p class="wb-dim" style="font-size: var(--fs-sm)">
                共 {{ slideCount }} 页 · 主题色 {{ f.themeColor }}
              </p>
              <div class="wb-row">
                <el-button @click="openUrl(pptDownloadUrl(result.taskId))">
                  <el-icon><Download /></el-icon>
                  下载 PPTX
                </el-button>
                <el-button @click="$router.push(`/preview/${result.taskId}`)">
                  <el-icon><View /></el-icon>
                  在线预览
                </el-button>
              </div>
              <el-divider content-position="left">按指令调整</el-divider>
              <el-input
                v-model="pptInstruction"
                type="textarea"
                :rows="2"
                placeholder="例如：把第三页的例子换成生活里的浮力现象"
              />
              <div class="wb-row">
                <el-button size="small" :loading="refining" :disabled="!pptInstruction.trim()" @click="onRefine">
                  精修
                </el-button>
              </div>
            </template>

            <!-- 动画 / 游戏：HTML 可直接预览 -->
            <template v-if="['animation', 'game'].includes(activeType)">
              <div class="wb-row">
                <el-button @click="onPreviewHtml">
                  <el-icon><View /></el-icon>
                  预览
                </el-button>
                <el-button @click="openUrl(result.downloadUrl)">
                  <el-icon><Download /></el-icon>
                  下载 HTML
                </el-button>
              </div>
              <p class="wb-muted" style="font-size: var(--fs-xs)">
                下载到的 HTML 不依赖网络，可直接拷到教室电脑打开。
              </p>
            </template>

            <ComplianceCard v-if="result.compliance" :report="result.compliance" />
          </div>
        </StateBlock>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download, QuestionFilled, Refresh, View } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ComplianceCard from '@/components/workbench/ComplianceCard.vue'
import { SUBJECTS, GRADES, THEME_COLORS, useLessonStore } from '@/store/lesson'
import { listUploadedFiles } from '@/api/upload'
import {
  fetchAnimationStyles, fetchGameTypes, generateCoursewareFull,
  analyzeCoursewareRequirements, generateCoursewareOutline,
  generateCoursewareDetailed, generateCoursewareVisualStyle,
  coursewareDownloadUrl
} from '@/api/courseware'
import { fetchPptPreview, pptDownloadUrl, refinePpt } from '@/api/ppt'
import {
  fetchUniversityDisciplines, fetchMajorsByDiscipline, fetchMajorConfig
} from '@/api/lessonPlan'
import { notifyError, notifySuccess, notifyWarn } from '@/utils/notify'

/**
 * 生成中心。
 *
 * 与工作台的分工：工作台是"边聊边做"，这里是"我就是要一份东西"——
 * 直接给表单、直接给结果，不用先开始一段对话。
 * 参数与工作台共用 store 的口径（学科/年级/时长/主题色…），
 * 因为后端四路生成本来就是同一套入参。
 */
const route = useRoute()
const router = useRouter()
const store = useLessonStore()

const TYPES = [
  {
    id: 'lesson-plan', name: '教案', desc: '完整教案（含教学目标、过程、评价），可导出 Word。',
    actionText: '生成教案', timeHint: '通常需要 1–2 分钟',
    contentLabel: '补充要求', contentPlaceholder: '例如：要多一些生活实例；检测题不超过 5 道',
    emptyTitle: '还没有生成教案', emptyDesc: '填好主题后点「生成教案」，结果会显示在这里。'
  },
  {
    id: 'courseware', name: '课件（六阶段）',
    desc: '需求 → 大纲 → 详细内容 → 视觉风格 → 成稿，每一步都能先看再改。适合还想调整结构的课。',
    actionText: '按六阶段生成', timeHint: '阶段多，通常需要 2–4 分钟',
    contentLabel: '核心知识点', contentPlaceholder: '一行一个知识点',
    emptyTitle: '还没有生成课件', emptyDesc: '六阶段会依次产出需求说明书、大纲、详细内容与视觉风格。'
  },
  {
    id: 'ppt', name: 'PPT 课件',
    desc: '一步出一份 PPTX，可在线预览、下载、按指令精修。适合已经想清楚、只要成品的时候。',
    actionText: '生成 PPT', timeHint: '通常需要 1–3 分钟',
    contentLabel: '核心知识点', contentPlaceholder: '一行一个知识点',
    emptyTitle: '还没有生成 PPT', emptyDesc: '生成过程中这里会显示进度与当前步骤。'
  },
  {
    id: 'animation', name: '动画演示', desc: '生成一个可直接打开的 HTML5 动画，不依赖网络。',
    actionText: '生成动画', timeHint: '通常需要 1 分钟',
    contentLabel: '教学内容', contentPlaceholder: '要演示什么过程？例如：浮力随排开体积变化的动画',
    emptyTitle: '还没有生成动画', emptyDesc: '生成后可预览，也可下载成单个 HTML 文件。'
  },
  {
    id: 'game', name: '互动游戏', desc: '生成一个可玩的 HTML5 小游戏，适合课堂练习。',
    actionText: '生成游戏', timeHint: '通常需要 1 分钟',
    contentLabel: '教学内容', contentPlaceholder: '要练哪些知识点？例如：浮力判断题 10 道',
    emptyTitle: '还没有生成游戏', emptyDesc: '生成后可预览，也可下载成单个 HTML 文件。'
  }
]

const STYLES = ['专业严谨', '活泼生动', '简约清晰', '学术深度']

const activeType = ref(String(route.params.type || 'lesson-plan'))
const current = computed(() => TYPES.find(t => t.id === activeType.value) || TYPES[0])

// 步骤条：教案与课件是分步流程，其余一步到位
const steps = computed(() => {
  if (activeType.value === 'courseware') return ['需求解析', '大纲', '详细内容', '视觉风格', '生成文件']
  if (activeType.value === 'lesson-plan') return ['需求解析', '大纲', '详细内容', '合规校验', '导出']
  return ['提交参数', '生成', '完成']
})
const stepIndex = ref(0)

const f = ref({
  topic: '', subject: '数学', grade: '七年级', duration: 45,
  teachingContent: '', themeColor: '蓝色系', stylePreference: '专业严谨',
  animStyle: 'auto', animMinutes: 5, gameType: '', scope: 'both',
  referenceFiles: []
})

const touched = ref(false)
const running = ref(false)
const exporting = ref(false)
const refining = ref(false)
const result = ref(null)
const resultError = ref('')
const resultStatus = ref('')
const downloadUrl = ref('')
const pptProgress = ref(0)
const pptStep = ref('')
const pptInstruction = ref('')
const openPanels = ref(['req', 'outline', 'detail', 'style', 'files'])

const files = ref([])
const loadingFiles = ref(false)
const animStyles = ref([])
const gameTypes = ref([])

const disciplines = ref([])
const majors = ref([])
const discipline = ref('')
const major = ref('')
const majorConfig = ref(null)

const slideCount = computed(() => {
  const o = result.value?.pptContent?.outline
  return Array.isArray(o) ? o.length : 0
})

const lessonPlanHtml = computed(() => {
  const lp = result.value?.lessonPlan
  if (!lp) return ''
  // 教案是嵌套字典，按模块摊平成可读的段落，而不是直接 dump repr
  return Object.entries(lp).map(([k, v]) => {
    const body = typeof v === 'string' ? v : dump(v)
    return `<h4>${escapeHtml(k)}</h4><div>${escapeHtml(body).replace(/\n/g, '<br>')}</div>`
  }).join('')
})

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))
}

function dump(v) {
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}

function openUrl(url) {
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

function useCurrent() {
  if (!store.topic) {
    notifyWarn('工作台还没有备课，去工作台说一句要备什么课')
    return
  }
  f.value.topic = store.topic
  f.value.subject = store.subject
  f.value.grade = store.grade
  f.value.duration = store.duration
  f.value.teachingContent = store.keyPoints || ''
  f.value.themeColor = store.pptTheme
  f.value.gameType = store.gameType
  notifySuccess('已带入工作台的这节课')
}

function onTypeChange(name) {
  router.replace(`/generate/${name}`)
  result.value = null
  resultError.value = ''
  resultStatus.value = ''
  stepIndex.value = 0
  if (name === 'animation' && !animStyles.value.length) loadAnimStyles()
  if (name === 'game' && !gameTypes.value.length) loadGameTypes()
}

// ---- 大学专业 -------------------------------------------------------------
async function loadDisciplines() {
  try { disciplines.value = await fetchUniversityDisciplines() } catch { disciplines.value = [] }
}

async function onDiscipline(code) {
  major.value = ''
  majorConfig.value = null
  if (!code) { majors.value = []; return }
  try { majors.value = await fetchMajorsByDiscipline(code) } catch { majors.value = [] }
}

async function onMajor(name) {
  majorConfig.value = null
  if (!name) return
  f.value.subject = name
  try { majorConfig.value = await fetchMajorConfig(name) } catch { majorConfig.value = null }
}

async function loadAnimStyles() {
  try { animStyles.value = await fetchAnimationStyles() } catch { animStyles.value = [] }
}

async function loadGameTypes() {
  try { gameTypes.value = await fetchGameTypes() } catch { gameTypes.value = [] }
}

// ---- 生成 -----------------------------------------------------------------

function keyPointList() {
  return f.value.teachingContent.split('\n').map(s => s.trim()).filter(Boolean)
}

function commonPayload() {
  return {
    topic: f.value.topic.trim(),
    subject: f.value.subject,
    grade: f.value.grade,
    audience: f.value.grade,
    duration: f.value.duration,
    key_points: keyPointList(),
    reference_docs: f.value.referenceFiles,
    reference_files: f.value.referenceFiles,
    knowledge_scope: f.value.scope,
    lesson_id: store.taskId || undefined
  }
}

async function onGenerate() {
  touched.value = true
  if (!f.value.topic.trim()) {
    notifyWarn('请先填写教学主题')
    return
  }
  if (running.value) return   // 防重复提交：生成很贵，连点会跑两份

  running.value = true
  resultError.value = ''
  result.value = null
  resultStatus.value = 'running'
  stepIndex.value = 0

  try {
    if (activeType.value === 'lesson-plan') {
      await runLessonPlan()
    } else if (activeType.value === 'courseware') {
      await runCourseware()
    } else if (activeType.value === 'ppt') {
      await runPpt()
    } else if (activeType.value === 'animation') {
      await runAnimation()
    } else {
      await runGame()
    }
    resultStatus.value = 'done'
  } catch (e) {
    resultError.value = e?.message || '生成失败'
    resultStatus.value = 'failed'
    notifyError(e?.message || '生成失败')
  } finally {
    running.value = false
    pptProgress.value = 0
    pptStep.value = ''
  }
}

async function runLessonPlan() {
  stepIndex.value = 1
  const data = await generateLessonPlanFull()
  stepIndex.value = 4
  result.value = {
    lessonPlan: data.lesson_plan,
    compliance: data.compliance || null,
    summary: '教案已生成，可导出 Word'
  }
}

/** 走完整链路并在本页拿到结构化结果（不落到工作台台账） */
async function generateLessonPlanFull() {
  const { resolveApiBaseURL } = await import('@/api/baseUrl')
  const { trackedFetch } = await import('@/api/dataFlow')
  const res = await trackedFetch(`${resolveApiBaseURL()}/lesson-plan/generate-full`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      level: levelOf(f.value.grade),
      subject: f.value.subject,
      grade: f.value.grade,
      topic: f.value.topic.trim(),
      duration: f.value.duration,
      requirements: f.value.teachingContent,
      reference_files: f.value.referenceFiles,
      knowledge_scope: f.value.scope,
      lesson_id: store.taskId || undefined
    })
  })
  const data = await res.json()
  if (!res.ok || data?.success === false) {
    throw new Error(data?.message || data?.detail || '教案生成失败')
  }
  return data
}

function levelOf(grade) {
  if (/^[一二三四五六]年级$/.test(grade)) return '小学'
  if (/^[七八九]年级$/.test(grade)) return '初中'
  if (/^高[一二三]$/.test(grade)) return '普通高中'
  if (grade === '大学生') return '大学'
  return '普通高中'
}

async function onExportLessonPlan() {
  if (!result.value?.lessonPlan || exporting.value) return
  exporting.value = true
  try {
    const { resolveApiBaseURL } = await import('@/api/baseUrl')
    const { trackedFetch } = await import('@/api/dataFlow')
    const res = await trackedFetch(`${resolveApiBaseURL()}/lesson-plan/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lesson_plan: result.value.lessonPlan,
        export_format: 'docx',
        topic: f.value.topic.trim()
      })
    })
    const data = await res.json()
    if (!res.ok || !data?.download_url) throw new Error(data?.message || '导出失败')
    downloadUrl.value = data.download_url
    notifySuccess('已导出 Word')
  } catch (e) {
    notifyError(e?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function runCourseware() {
  const base = commonPayload()
  stepIndex.value = 0
  const req = await analyzeCoursewareRequirements({
    topic: base.topic, audience: base.grade, duration: base.duration,
    key_points: base.key_points, reference_docs: base.reference_docs, subject: base.subject
  })
  const requirements = req.requirements
  stepIndex.value = 1

  const out = await generateCoursewareOutline(requirements)
  const outline = out.outline
  stepIndex.value = 2

  const det = await generateCoursewareDetailed({ outline, requirements })
  stepIndex.value = 3

  const st = await generateCoursewareVisualStyle({
    topic: base.topic, subject: base.subject, audience: base.grade
  })
  stepIndex.value = 4

  const full = await generateCoursewareFull({
    topic: base.topic, audience: base.grade, duration: base.duration,
    key_points: base.key_points, reference_docs: base.reference_docs, subject: base.subject
  })

  result.value = {
    requirements,
    outline,
    detailed: det.detailed_content,
    style: st.style,
    files: full.result?.files || {},
    taskDir: full.result?.task_dir || '',
    compliance: full.compliance || null,
    summary: '六阶段已跑完，文件在下方'
  }
}

async function runPpt() {
  stepIndex.value = 1
  const { generatePpt } = await import('@/api/lessonArtifacts')
  const patch = await generatePpt(
    {
      topic: f.value.topic.trim(),
      subject: f.value.subject,
      grade: f.value.grade,
      duration: f.value.duration,
      keyPoints: keyPointList(),
      referenceIds: f.value.referenceFiles,
      knowledgeScope: f.value.scope,
      lessonId: store.taskId || '',
      teachingIntent: undefined,
      teachingBlueprint: undefined
    },
    {
      themeColor: f.value.themeColor,
      onProgress: (p, s) => { pptProgress.value = p; pptStep.value = s }
    }
  )
  stepIndex.value = 2
  // 页数从预览数据里取，不用正则猜"第N页"
  let pptContent = null
  try {
    const pv = await fetchPptPreview(patch.taskId)
    pptContent = pv.ppt_data || null
  } catch { /* 预览取不到不影响下载 */ }

  result.value = {
    ...patch,
    pptContent,
    summary: patch.summary || 'PPT 已生成'
  }
}

async function runAnimation() {
  stepIndex.value = 1
  const { generateAnimation } = await import('@/api/lessonArtifacts')
  const patch = await generateAnimation(
    {
      topic: f.value.topic.trim(),
      subject: f.value.subject,
      grade: f.value.grade,
      teachingContent: f.value.teachingContent,
      knowledgeScope: f.value.scope,
      lessonId: store.taskId || ''
    },
    { minutes: f.value.animMinutes }
  )
  stepIndex.value = 2
  result.value = { ...patch, summary: patch.summary || '动画已生成' }
}

async function runGame() {
  stepIndex.value = 1
  const { generateGame } = await import('@/api/lessonArtifacts')
  const patch = await generateGame(
    {
      topic: f.value.topic.trim(),
      grade: f.value.grade,
      teachingContent: f.value.teachingContent,
      knowledgeScope: f.value.scope,
      lessonId: store.taskId || ''
    },
    { gameType: f.value.gameType || undefined }
  )
  stepIndex.value = 2
  result.value = { ...patch, summary: patch.summary || '游戏已生成' }
}

async function onRefine() {
  if (!pptInstruction.value.trim() || refining.value) return
  refining.value = true
  try {
    await refinePpt(result.value.taskId, pptInstruction.value.trim())
    notifySuccess('已提交精修，稍后可在预览里查看')
    pptInstruction.value = ''
  } catch (e) {
    notifyError(e?.message || '精修失败')
  } finally {
    refining.value = false
  }
}

/** HTML 产物预览：下载接口带 attachment，必须转成 Blob 再看 */
async function onPreviewHtml() {
  const url = result.value?.previewUrl || result.value?.downloadUrl
  if (!url) return
  try {
    const { trackedFetch } = await import('@/api/dataFlow')
    const res = await trackedFetch(url)
    if (!res.ok) throw new Error(`预览失败（HTTP ${res.status}）`)
    const blob = await res.blob()
    const objUrl = URL.createObjectURL(new Blob([blob], { type: 'text/html;charset=utf-8' }))
    window.open(objUrl, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(objUrl), 60000)
  } catch (e) {
    notifyError(e?.message || '预览失败')
  }
}

onMounted(async () => {
  loadingFiles.value = true
  try { files.value = await listUploadedFiles() } catch { files.value = [] } finally { loadingFiles.value = false }
  if (activeType.value === 'animation') loadAnimStyles()
  if (activeType.value === 'game') loadGameTypes()
  if (activeType.value === 'lesson-plan') loadDisciplines()
  // 工作台已有课程时默认带入，教师不用再打一遍
  if (store.topic) useCurrent()
})

watch(() => route.params.type, v => {
  if (v && v !== activeType.value) {
    activeType.value = String(v)
    onTypeChange(String(v))
  }
})
</script>

<style scoped>
.type-tabs { margin-bottom: var(--sp-2); }

.type-note {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  line-height: 1.8;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--sp-4);
  align-items: start;
}

.form__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}

.form__foot {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--wb-border);
}

.result { min-height: 320px; }

.field-error {
  margin: 4px 0 0;
  font-size: var(--fs-xs);
  color: var(--wb-risk-text);
}

.is-invalid :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger) inset !important;
}

.dump {
  margin: 0;
  max-height: 260px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  line-height: 1.6;
  background: var(--wb-code-bg);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  color: var(--wb-text-2);
  white-space: pre-wrap;
  word-break: break-word;
}

.preview {
  max-height: 420px;
  overflow: auto;
  font-size: var(--fs-sm);
  line-height: 1.75;
  color: var(--wb-text);
}

.preview :deep(h4) {
  margin: var(--sp-3) 0 var(--sp-1);
  font-size: var(--fs-base);
  color: var(--brand-text);
}


.file-list { list-style: none; margin: 0; padding: 0; }
.file-list li { display: flex; justify-content: space-between; padding: 4px 0; }

@media (max-width: 1024px) {
  .layout { grid-template-columns: 1fr; }
}
</style>
