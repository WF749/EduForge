<template>
  <div class="courseware-view">
    <div class="courseware-container">
      <!-- 页面标题 -->
      <div class="page-header">
        <h1>
          <el-icon :size="28"><VideoPlay /></el-icon>
          课件智能生成中心
        </h1>
        <p class="subtitle">输入准确的课程信息，按需生成PPT课件和Word教案</p>
      </div>

      <!-- 主内容区域 -->
      <div class="main-content">
        <!-- 左侧：表单区域 -->
        <div class="form-panel">
          <!-- 基本信息卡片 -->
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Edit /></el-icon> 课程基本信息</h3>
            </div>

            <el-form label-position="top" size="large">
              <el-form-item label="教学主题" required>
                <el-input
                  v-model="form.topic"
                  placeholder="例如：Python编程基础、机器学习入门"
                  size="large"
                />
              </el-form-item>

              <div class="form-grid">
                <el-form-item label="学科" required>
                  <el-select v-model="form.subject" size="large" filterable allow-create>
                    <el-option v-for="subject in subjectOptions" :key="subject" :label="subject" :value="subject" />
                  </el-select>
                </el-form-item>

                <el-form-item label="年级" required>
                  <el-select v-model="form.target_audience" size="large">
                    <el-option v-for="grade in gradeOptions" :key="grade" :label="grade" :value="grade" />
                  </el-select>
                </el-form-item>
              </div>

              <el-form-item label="课时时长">
                <el-input-number v-model="form.duration" :min="15" :max="180" :step="15" size="large" />
              </el-form-item>
            </el-form>
          </div>

          <!-- 内容设置卡片 -->
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Document /></el-icon> 教学内容设置</h3>
            </div>

            <el-form label-position="top" size="large">
              <el-form-item label="教学内容描述（可不填）">
                <el-input
                  v-model="form.key_points_text"
                  type="textarea"
                  :rows="4"
                  placeholder="输入教学内容描述，系统将智能分析需求并生成PPT
例如：
1. 课程目标：让学生掌握Python基本语法
2. 重点内容：变量、数据类型、条件语句、循环
3. 教学风格：专业严谨，适合大一新生
4. 其他要求：包含互动练习和案例分析"
                />
              </el-form-item>

              <!-- 参考文档上传 -->
              <el-form-item label="参考资料上传（可选）">
                <el-upload
                  class="upload-demo"
                  drag
                  action="/api/upload/file"
                  :multiple="true"
                  :on-success="handleUploadSuccess"
                  :on-error="handleUploadError"
                  :file-list="uploadedFiles"
                  :limit="5"
                  accept=".pdf,.doc,.docx,.pptx,.txt"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
                  <template #tip>
                    <div class="el-upload__tip">
                      支持 PDF、Word、PPTX、TXT；生成时会读取其中可提取的文字内容
                    </div>
                  </template>
                </el-upload>
              </el-form-item>

              <div class="form-grid">
                <el-form-item label="难度等级">
                  <el-select v-model="form.difficulty" size="large">
                    <el-option label="入门级" value="easy" />
                    <el-option label="中等难度" value="medium" />
                    <el-option label="进阶深入" value="hard" />
                  </el-select>
                </el-form-item>

              </div>
            </el-form>
          </div>

          <!-- 自定义主题卡片 -->
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Palette /></el-icon> 自定义主题</h3>
            </div>

            <el-form label-position="top" size="large">
              <div class="form-grid">
                <el-form-item label="PPT主题色">
                  <el-select v-model="form.theme_color" size="large">
                    <el-option label="蓝色系" value="蓝色系" />
                    <el-option label="绿色系" value="绿色系" />
                    <el-option label="红色系" value="红色系" />
                    <el-option label="紫色系" value="紫色系" />
                    <el-option label="橙色系" value="橙色系" />
                  </el-select>
                </el-form-item>

              </div>
            </el-form>
          </div>

          <!-- 生成选项卡片 -->
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Setting /></el-icon> 生成内容选择</h3>
            </div>

            <div class="generation-options">
              <div class="option-item" :class="{ active: form.include_ppt }" @click="form.include_ppt = !form.include_ppt">
                <div class="option-icon">
                  <el-icon :size="28"><Document /></el-icon>
                </div>
                <div class="option-info">
                  <span class="option-title">PPT课件</span>
                  <span class="option-desc">.pptx 幻灯片文件</span>
                </div>
                <div class="option-check">
                  <el-icon v-if="form.include_ppt"><Check /></el-icon>
                </div>
              </div>

              <div class="option-item" :class="{ active: form.include_word }" @click="form.include_word = !form.include_word">
                <div class="option-icon">
                  <el-icon :size="28"><Files /></el-icon>
                </div>
                <div class="option-info">
                  <span class="option-title">Word教案</span>
                  <span class="option-desc">.docx 教案文档</span>
                </div>
                <div class="option-check">
                  <el-icon v-if="form.include_word"><Check /></el-icon>
                </div>
              </div>
            </div>
          </div>

          <!-- 生成按钮 -->
          <div class="generate-actions">
            <el-button size="large" @click="resetForm" :disabled="generating">重置</el-button>
            <el-button
              type="primary"
              size="large"
              :loading="generating"
              @click="startGeneration"
              class="generate-btn"
            >
              <el-icon :size="20"><VideoPlay /></el-icon>
              {{ generating ? '生成中...' : '开始生成' }}
            </el-button>
          </div>
        </div>

        <!-- 右侧：生成结果面板 -->
        <div class="result-panel">
          <!-- 当前生成状态 -->
          <div v-if="generating" class="generating-status">
            <div class="generating-header">
              <h3><el-icon class="is-loading"><Loading /></el-icon> 正在生成...</h3>
            </div>

            <!-- 生成过程可视化窗口 -->
            <div class="generation-visualization">
              <div class="visualization-header">
                <h4><el-icon><VideoCamera /></el-icon> 实际任务进度</h4>
              </div>
              <div class="visualization-body">
                <div v-if="currentSlide" class="slide-preview">
                  <div class="slide-content">
                    <h5>{{ currentSlide.title }}</h5>
                    <p v-if="currentSlide.content">{{ currentSlide.content }}</p>
                    <div v-if="currentSlide.type === 'cover'" class="cover-slide">
                      <h3>{{ currentSlide.title }}</h3>
                      <p>{{ form.target_audience }}</p>
                      <p>{{ form.duration }}分钟</p>
                    </div>
                  </div>
                </div>
                <div v-else class="preview-loading">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <p>正在等待后端返回真实生成状态...</p>
                </div>
              </div>
            </div>

            <div class="progress-steps">
              <div
                v-for="(step, index) in generationSteps"
                :key="index"
                class="progress-step"
                :class="{
                  active: currentProgressStep >= index,
                  current: currentProgressStep === index
                }"
              >
                <div class="step-icon">
                  <el-icon v-if="currentProgressStep > index"><Check /></el-icon>
                  <el-icon v-else-if="currentProgressStep === index" class="is-loading"><Loading /></el-icon>
                  <span v-else>{{ index + 1 }}</span>
                </div>
                <div class="step-info">
                  <span class="step-name">{{ step.name }}</span>
                  <span class="step-status">{{ step.status }}</span>
                  <span v-if="step.details" class="step-details">{{ step.details }}</span>
                </div>
              </div>
            </div>

            <el-progress
              :percentage="progressPercent"
              :stroke-width="8"
              :color="progressColors"
              :show-text="true"
              :format="formatProgress"
            />
          </div>

          <!-- 无生成结果显示 -->
          <div v-else-if="!currentResult" class="empty-state">
            <div class="empty-icon">
              <el-icon :size="64"><VideoPlay /></el-icon>
            </div>
            <h3>准备生成课件</h3>
            <p>填写左侧表单信息，点击"开始生成"按钮<br/>系统将为您生成专业的教学课件</p>

            <div class="feature-list">
              <div class="feature-item">
                <el-icon><Document /></el-icon>
                <span>PPT课件</span>
              </div>
              <div class="feature-item">
                <el-icon><Files /></el-icon>
                <span>Word教案</span>
              </div>
            </div>
          </div>

          <!-- 生成结果展示 -->
          <div v-else class="result-content">
            <div class="result-header">
              <h3>
                <el-icon><SuccessFilled /></el-icon>
                 {{ currentResult.generation_errors?.length ? '部分内容已完成' : '生成完成' }}
              </h3>
              <p>{{ currentResult.topic || '课件' }}</p>
              <el-button size="small" @click="router.push('/history')">
                <el-icon><Folder /></el-icon> 查看历史作品
              </el-button>
            </div>

            <!-- 出厂质检报告：后端生成完成时已附带，纯规则离线扫描 -->
            <ComplianceReport v-if="currentResult.compliance_reports?.ppt" :report="currentResult.compliance_reports.ppt" label="PPT课件" />
            <ComplianceReport v-if="currentResult.compliance_reports?.lesson_plan" :report="currentResult.compliance_reports.lesson_plan" label="Word教案" />

            <!-- 文件卡片列表 -->
            <div class="result-files">
              <!-- PPT课件 -->
              <div v-if="currentResult.files?.pptx || hasPptContent" class="file-card">
                <div class="file-icon pptx">
                  <el-icon :size="32"><Document /></el-icon>
                </div>
                <div class="file-info">
                  <span class="file-name">PPT课件</span>
                  <span class="file-size">{{ currentResult.files?.pptx ? '已生成' : '内容已生成' }}</span>
                </div>
                <div class="file-actions">
                  <el-button v-if="currentResult.files?.pptx" type="primary" size="small" @click="downloadFile('pptx')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  <el-tag v-else size="small" type="warning">内容已生成，文件不可用</el-tag>
                  <el-button size="small" @click="previewFile('pptx')">
                    <el-icon><View /></el-icon> 预览
                  </el-button>
                </div>
              </div>

              <!-- Word教案 -->
              <div v-if="currentResult.files?.docx || hasDocContent" class="file-card">
                <div class="file-icon docx">
                  <el-icon :size="32"><Files /></el-icon>
                </div>
                <div class="file-info">
                  <span class="file-name">Word教案</span>
                  <span class="file-size">{{ currentResult.files?.docx ? '已生成' : '内容已生成' }}</span>
                </div>
                <div class="file-actions">
                  <el-button v-if="currentResult.files?.docx" type="primary" size="small" @click="downloadFile('docx')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  <el-tag v-else size="small" type="warning">待重新导出</el-tag>
                </div>
              </div>

              <!-- 动画创意 -->
              <div v-if="currentResult.animation_result || currentResult.animation_ideas" class="file-card">
                <div class="file-icon animation">
                  <el-icon :size="32"><VideoCamera /></el-icon>
                </div>
                <div class="file-info">
                  <span class="file-name">动画创意</span>
                  <span class="file-size">HTML5 动画预览</span>
                </div>
                <div class="file-actions">
                  <el-button type="primary" size="small" @click="downloadFile('animation')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  <el-button size="small" @click="previewFile('animation')">
                    <el-icon><View /></el-icon> 预览
                  </el-button>
                </div>
              </div>

              <!-- 互动游戏 -->
              <div v-if="currentResult.game_result || currentResult.interactive_games" class="file-card">
                <div class="file-icon game">
                  <el-icon :size="32"><Connection /></el-icon>
                </div>
                <div class="file-info">
                  <span class="file-name">互动游戏</span>
                  <span class="file-size">HTML5 可玩游戏</span>
                </div>
                <div class="file-actions">
                  <el-button type="primary" size="small" @click="downloadFile('game')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  <el-button size="small" @click="previewFile('game')">
                    <el-icon><View /></el-icon> 预览
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 课程预览 -->
            <div class="course-preview">
              <div class="preview-header">
                <h4><el-icon><View /></el-icon> 课件内容预览</h4>
              </div>
              <div class="preview-body">
                <div v-if="slides.length > 0" class="slides-preview">
                  <div
                    v-for="(slide, index) in slides.slice(0, 5)"
                    :key="index"
                    class="slide-item"
                    :class="{ cover: index === 0 }"
                  >
                    <span class="slide-num">{{ index + 1 }}</span>
                    <span class="slide-title">{{ slide.title || '无标题' }}</span>
                  </div>
                  <div v-if="slides.length > 5" class="slide-more">
                    还有 {{ slides.length - 5 }} 页...
                  </div>
                </div>
                <div v-else class="preview-empty">
                  <p>暂无预览内容</p>
                </div>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="result-actions">
              <el-button size="large" @click="startNewGeneration">
                <el-icon><Plus /></el-icon>
                生成新课
              </el-button>
              <el-button v-if="hasPptContent" type="primary" size="large" @click="viewFullPreview">
                <el-icon><View /></el-icon>
                完整预览
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'CoursewareView' }
</script>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/store/app'
import { ElMessage } from 'element-plus'
import { resolveApiBaseURL } from '@/api/baseUrl'
import {
  VideoPlay, Document, Files, Edit, Setting, Check, Clock,
  Connection, Download, View, Plus, SuccessFilled, Loading,
  VideoCamera, UploadFilled, Folder
} from '@element-plus/icons-vue'
import ComplianceReport from '@/components/ComplianceReport.vue'
import { trackedFetch } from '@/api/dataFlow'

// Palette 图标可能不存在于 element-plus, 使用 Setting 作为后备
const Palette = Setting

const router = useRouter()
const store = useAppStore()

// 表单数据
const form = reactive({
  topic: '',
  subject: '数学',
  target_audience: '七年级',
  duration: 45,
  difficulty: 'medium',
  key_points_text: '',
  theme_color: '蓝色系',
  include_ppt: true,
  include_word: true
})

const subjectOptions = ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '道德与法治', '科学', '信息科技', '艺术', '体育与健康']
const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '高一', '高二', '高三']

// 上传文件状态
const uploadedFiles = ref([])

// 生成状态
const generating = ref(false)
const currentProgressStep = ref(0)
const progressPercent = ref(0)
const currentResult = ref(null)
const slides = ref([])
const currentSlide = ref(null)

// === sessionStorage 持久化 ===
const STORAGE_KEY_RESULT = 'courseware_currentResult'
const STORAGE_KEY_SLIDES = 'courseware_slides'

// 从 sessionStorage 恢复上次的生成结果
function restoreFromStorage() {
  try {
    const savedResult = sessionStorage.getItem(STORAGE_KEY_RESULT)
    const savedSlides = sessionStorage.getItem(STORAGE_KEY_SLIDES)
    if (savedResult && !currentResult.value) {
      currentResult.value = JSON.parse(savedResult)
      console.log('已从sessionStorage恢复生成结果')
    }
    if (savedSlides && slides.value.length === 0) {
      slides.value = JSON.parse(savedSlides)
    }
  } catch (e) {
    console.warn('恢复sessionStorage数据失败:', e)
  }
}

// 保存到 sessionStorage
function saveToStorage() {
  try {
    if (currentResult.value) {
      // 保存时去掉 ppt_content 中过大的数据以控制存储大小
      const toSave = { ...currentResult.value }
      if (toSave.ppt_content && typeof toSave.ppt_content === 'object') {
        // 保留 ppt_content 的元数据但截断过大的详细内容
        const pptCopy = { ...toSave.ppt_content }
        if (JSON.stringify(pptCopy).length > 500000) {
          // 如果超过500KB，只保留metadata和outline
          toSave.ppt_content = {
            metadata: pptCopy.metadata,
            outline: pptCopy.outline
          }
        }
      }
      sessionStorage.setItem(STORAGE_KEY_RESULT, JSON.stringify(toSave))
    }
    if (slides.value.length > 0) {
      sessionStorage.setItem(STORAGE_KEY_SLIDES, JSON.stringify(slides.value))
    }
  } catch (e) {
    console.warn('保存sessionStorage数据失败:', e)
  }
}

function clearStorage() {
  sessionStorage.removeItem(STORAGE_KEY_RESULT)
  sessionStorage.removeItem(STORAGE_KEY_SLIDES)
}

// 监听 currentResult 变化自动保存
watch(currentResult, () => { saveToStorage() }, { deep: true })
watch(slides, () => { saveToStorage() }, { deep: true })

// 生成步骤 - 动态根据选择的内容生成
const generationSteps = ref([
  { name: '智能需求分析', status: '等待中', details: '' },
  { name: '结构化大纲生成', status: '等待中', details: '' },
  { name: '分页面精细化内容生成', status: '等待中', details: '' },
  { name: 'PPT视觉与动画设计', status: '等待中', details: '' },
  { name: 'PPT排版与格式规范', status: '等待中', details: '' },
  { name: '最终PPT生成', status: '等待中', details: '' }
])

// 进度颜色
const progressColors = [
  { color: '#00c8ff', percentage: 20 },
  { color: '#00ff88', percentage: 50 },
  { color: '#7c3aed', percentage: 100 }
]

// 内容检测
const hasPptContent = computed(() => !!currentResult.value?.ppt_content)
const hasDocContent = computed(() => !!currentResult.value?.lesson_plan)

// 格式化进度
function formatProgress(percent) {
  if (generationSteps.value.length === 0) {
    return '准备中'
  }
  
  // 根据进度百分比确定当前步骤
  const totalSteps = generationSteps.value.length
  let currentStepIndex = 0
  
  if (percent >= 100) {
    currentStepIndex = totalSteps - 1
  } else {
    // 计算当前步骤索引
    currentStepIndex = Math.min(
      Math.floor((percent / 90) * (totalSteps - 1)),
      totalSteps - 2
    )
  }
  
  const currentStep = generationSteps.value[currentStepIndex]
  return currentStep ? currentStep.name : '生成中'
}

// 更新生成步骤状态
function updateProgressStep(stepIndex, status, details = '') {
  if (stepIndex < generationSteps.value.length) {
    generationSteps.value[stepIndex].status = status
    generationSteps.value[stepIndex].details = details
  }
  currentProgressStep.value = stepIndex
  // 根据动态步骤数量计算进度百分比
  const totalSteps = generationSteps.value.length
  if (totalSteps > 0) {
    // 最后一步占比较大，确保最终能达到100%
    if (stepIndex === totalSteps - 1) {
      progressPercent.value = 100
    } else {
      // 均匀分配进度，前几步各占相应比例
      progressPercent.value = Math.round((stepIndex / (totalSteps - 1)) * 90)
    }
  }
}

// 处理文件上传成功
function handleUploadSuccess(response) {
  if (response.success) {
    ElMessage.success('文件上传成功')
    uploadedFiles.value.push({
      name: response.filename,
      file_id: response.file_id,
      url: response.filename
    })
  } else {
    ElMessage.error('文件上传失败: ' + response.message)
  }
}

// 处理文件上传失败
function handleUploadError(error) {
  ElMessage.error('文件上传失败: 网络错误')
  console.error('上传失败:', error)
}

// 重置表单
function resetForm() {
  form.topic = ''
  form.subject = '数学'
  form.target_audience = '七年级'
  form.duration = 45
  form.difficulty = 'medium'
  form.key_points_text = ''
  form.theme_color = '蓝色系'
  form.include_ppt = true
  form.include_word = true
  currentResult.value = null
  slides.value = []
  uploadedFiles.value = []
  clearStorage()
}



const difficultyLabels = { easy: '入门', medium: '中等', hard: '进阶' }

function levelForGrade(grade) {
  if (/^[一二三四五六]年级$/.test(grade)) return '小学'
  if (/^[七八九]年级$/.test(grade)) return '初中'
  return '普通高中'
}

async function readJson(response, fallback) {
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || data.message || fallback)
  return data
}

// 只展示后端返回的真实状态；每种产物独立失败，已成功内容不会被丢弃。
async function startGeneration() {
  clearStorage()
  currentResult.value = null
  slides.value = []
  currentSlide.value = null

  if (!form.topic.trim()) return ElMessage.warning('请输入教学主题')
  if (!form.subject) return ElMessage.warning('请选择学科')
  if (!form.target_audience) return ElMessage.warning('请选择年级')
  if (!form.duration) return ElMessage.warning('请选择课时时长')
  if (!form.include_ppt && !form.include_word) return ElMessage.warning('请至少选择一种生成内容')

  const steps = []
  if (form.include_ppt) steps.push({ name: 'PPT课件生成' })
  if (form.include_word) steps.push({ name: 'Word教案生成' })
  steps.push({ name: '处理结束' })
  generationSteps.value = steps.map(step => ({ ...step, status: '等待中', details: '' }))
  currentProgressStep.value = 0
  progressPercent.value = 0
  generating.value = true

  const failures = []
  const completed = []
  const referenceFiles = uploadedFiles.value.map(file => file.file_id).filter(Boolean)
  const difficulty = difficultyLabels[form.difficulty] || '中等'
  currentResult.value = {
    topic: form.topic,
    subject: form.subject,
    grade: form.target_audience,
    audience: form.target_audience,
    duration: form.duration,
    files: {},
    compliance_reports: {}
  }

  let currentStep = 0
  if (form.include_ppt) {
    updateProgressStep(currentStep, '提交中', '正在创建PPT生成任务')
    try {
      const keyPoints = form.key_points_text.split('\n').map(item => item.trim()).filter(Boolean)
      keyPoints.push(`内容难度：${difficulty}`)
      const response = await trackedFetch(`${resolveApiBaseURL()}/ppt/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: form.topic,
          duration: form.duration,
          audience: form.target_audience,
          subject: form.subject,
          theme_color: form.theme_color,
          style_preference: 'professional',
          key_points: keyPoints,
          reference_docs: referenceFiles,
          template: 'standard'
        })
      })
      const task = await readJson(response, 'PPT任务创建失败')
      if (!task.success || !task.task_id) throw new Error(task.message || 'PPT任务创建失败')

      let finished = false
      for (let attempts = 0; attempts < 300; attempts++) {
        const statusResponse = await trackedFetch(`${resolveApiBaseURL()}/ppt/status/${task.task_id}`)
        const status = await readJson(statusResponse, 'PPT状态读取失败')
        const taskProgress = Number(status.progress || 0)
        updateProgressStep(currentStep, `${taskProgress}%`, status.current_step || '正在生成PPT')
        progressPercent.value = Math.round(((currentStep + taskProgress / 100) / steps.length) * 100)
        if (status.status === 'completed' && status.result) {
          const previous = currentResult.value
          currentResult.value = {
            ...previous,
            ...status.result,
            task_id: task.task_id,
            files: { ...previous.files, ...(status.result.files || {}) },
            compliance_reports: {
              ...previous.compliance_reports,
              ...(status.result.compliance ? { ppt: status.result.compliance } : {})
            }
          }
          parseSlides(currentResult.value)
          updateProgressStep(currentStep, '完成', 'PPT文件生成完成')
          completed.push('PPT')
          finished = true
          break
        }
        if (status.status === 'failed' || status.status === 'unknown') {
          throw new Error(status.error || 'PPT任务失败或已过期')
        }
        await sleep(1000)
      }
      if (!finished) throw new Error('PPT生成超时，请稍后重试')
    } catch (error) {
      failures.push(`PPT：${error.message}`)
      updateProgressStep(currentStep, '失败', error.message)
    }
    currentStep++
  }

  if (form.include_word) {
    updateProgressStep(currentStep, '生成中', '正在生成教案内容')
    try {
      const requirements = [form.key_points_text, `内容难度：${difficulty}`].filter(Boolean).join('\n')
      const response = await trackedFetch(`${resolveApiBaseURL()}/lesson-plan/generate-full`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level: levelForGrade(form.target_audience),
          subject: form.subject,
          grade: form.target_audience,
          topic: form.topic,
          duration: form.duration,
          requirements,
          reference_files: referenceFiles
        })
      })
      const lesson = await readJson(response, '教案生成失败')
      if (!lesson.success || !lesson.lesson_plan) throw new Error(lesson.message || '教案生成失败')

      currentResult.value.lesson_plan = lesson.lesson_plan
      if (lesson.compliance) currentResult.value.compliance_reports.lesson_plan = lesson.compliance
      updateProgressStep(currentStep, '导出中', '教案内容已生成，正在导出Word文件')

      const exportResponse = await trackedFetch(`${resolveApiBaseURL()}/lesson-plan/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_plan: lesson.lesson_plan, export_format: 'docx', topic: form.topic })
      })
      const exported = await readJson(exportResponse, 'Word导出失败')
      if (!exported.success || !exported.download_url) throw new Error(exported.message || 'Word导出失败')
      currentResult.value.files.docx = exported.download_url
      updateProgressStep(currentStep, '完成', 'Word教案生成完成')
      completed.push('Word教案')
    } catch (error) {
      failures.push(`Word教案：${error.message}`)
      updateProgressStep(
        currentStep,
        currentResult.value.lesson_plan ? '内容已生成，导出失败' : '失败',
        error.message
      )
    }
    currentStep++
  }

  currentResult.value.generation_errors = failures
  updateProgressStep(
    currentStep,
    failures.length ? (completed.length || currentResult.value.lesson_plan ? '部分完成' : '失败') : '完成',
    failures.length ? failures.join('；') : '所选内容均已生成'
  )
  progressPercent.value = 100
  generating.value = false

  if (failures.length && (completed.length || currentResult.value.lesson_plan)) {
    ElMessage.warning('部分内容已完成，可查看失败项并单独重试')
  } else if (failures.length) {
    currentResult.value = null
    ElMessage.error(failures.join('；'))
  } else {
    ElMessage.success(`${completed.join('、')}生成完成`)
  }
}

// 解析幻灯片
function parseSlides(result) {
  if (!result) return

  const pptContent = result.ppt_content
  if (pptContent) {
    const parsedSlides = []

    // 检查pptContent是否是对象且包含detailed_content
    if (typeof pptContent === 'object' && pptContent.detailed_content) {
      // 从detailed_content中解析幻灯片
      pptContent.detailed_content.forEach((slide) => {
        const title = slide.core_topic || `幻灯片 ${slide.page_num}`
        const type = slide.page_type || 'content'
        parsedSlides.push({
          title,
          type
        })
      })
    } else if (typeof pptContent === 'string' && pptContent.includes('页面标题')) {
      // 回退到旧的字符串解析方式
      const sections = pptContent.split('页面标题')
      sections.slice(1).forEach((section, i) => {
        const lines = section.split('\n')
        const title = lines[0]?.replace(/[：:]/g, '').trim() || '无标题'
        parsedSlides.push({
          title,
          type: i === 0 ? 'cover' : 'content'
        })
      })
    }

    slides.value = parsedSlides
  }
}

// 下载文件
function downloadFile(type) {
  if (!currentResult.value) {
    ElMessage.warning('没有可下载的文件')
    return
  }

  try {
    let downloadUrl = ''
    let hasDownload = false

    if (type === 'pptx') {
      const taskId = currentResult.value.task_id || currentResult.value.taskId
      if (taskId) {
        downloadUrl = `${resolveApiBaseURL()}/ppt/download/${encodeURIComponent(taskId)}`
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的PPT任务')
      }
    } else if (type === 'docx') {
      if (currentResult.value.files?.docx) {
        downloadUrl = currentResult.value.files.docx
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的Word文件')
      }
    } else if (type === 'animation') {
      const taskId = currentResult.value.animation_result?.task_id
      const taskDir = currentResult.value.animation_result?.task_dir
      if (taskId) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/animation/download?task_id=${encodeURIComponent(taskId)}`
        hasDownload = true
      } else if (taskDir) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(taskDir)}`
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的动画文件')
      }
    } else if (type === 'game') {
      const taskId = currentResult.value.game_result?.task_id
      const taskDir = currentResult.value.game_result?.task_dir
      if (taskId) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/game/download?task_id=${encodeURIComponent(taskId)}`
        hasDownload = true
      } else if (taskDir) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(taskDir)}`
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的游戏文件')
      }
    }

    if (hasDownload) {
      console.log('下载URL:', downloadUrl)
      window.open(downloadUrl, '_blank')
      ElMessage.success('文件下载中...')
    }
  } catch (e) {
    console.error('下载失败:', e)
    ElMessage.error('下载失败')
  }
}

// 预览文件
function previewFile(type) {
  if (!currentResult.value) {
    ElMessage.warning('没有可预览的内容')
    return
  }

  if (type === 'pptx') {
    // 从currentResult中获取任务ID
    const taskId = currentResult.value.task_id || currentResult.value.taskId
    if (taskId) {
      viewPPTPreview(taskId)
    } else if (currentResult.value.ppt_content) {
      // 如果有PPT内容，直接预览
      viewFullPreview()
    } else {
      ElMessage.warning('任务ID不存在')
    }
  } else if (type === 'animation') {
    const taskId = currentResult.value.animation_result?.task_id
    const taskDir = currentResult.value.animation_result?.task_dir
    if (taskId) {
      window.open(`${resolveApiBaseURL()}/courseware/animation/download?task_id=${encodeURIComponent(taskId)}`, '_blank')
    } else if (taskDir) {
      window.open(`${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(taskDir)}`, '_blank')
    } else {
      ElMessage.warning('没有可预览的动画文件')
    }
  } else if (type === 'game') {
    const taskId = currentResult.value.game_result?.task_id
    const taskDir = currentResult.value.game_result?.task_dir
    if (taskId) {
      window.open(`${resolveApiBaseURL()}/courseware/game/download?task_id=${encodeURIComponent(taskId)}`, '_blank')
    } else if (taskDir) {
      window.open(`${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(taskDir)}`, '_blank')
    } else {
      ElMessage.warning('没有可预览的游戏文件')
    }
  } else {
    viewFullPreview()
  }
}

// 查看PPT预览
async function viewPPTPreview(taskId) {
  try {
    const previewResponse = await trackedFetch(`${resolveApiBaseURL()}/ppt/preview/${encodeURIComponent(taskId)}`)
    const previewRes = await previewResponse.json()
    
    if (previewRes.success) {
      router.push({
        path: `/preview/${taskId}`,
        query: {
          courseware: JSON.stringify({
            ppt_content: previewRes.ppt_data,
            task_id: currentResult.value?.task_id || taskId,
            topic: currentResult.value?.topic || form.topic || ''
          })
        }
      })
    } else {
      ElMessage.error('预览失败: ' + (previewRes.message || '未知错误'))
    }
  } catch (e) {
    console.error('预览失败:', e)
    ElMessage.error('预览失败')
  }
}

// 查看完整预览
function viewFullPreview() {
  if (!currentResult.value) return

  const taskId = currentResult.value.task_id || currentResult.value.taskId
  if (!taskId) {
    ElMessage.warning('当前内容没有可继续编辑的PPT任务')
    return
  }
  const previewData = { ...currentResult.value }
  delete previewData.task_dir
  delete previewData.pptx_path
  router.push({
    path: `/preview/${taskId}`,
    query: {
      courseware: JSON.stringify(previewData)
    }
  })
}

// 开始新生成
function startNewGeneration() {
  resetForm()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 辅助函数
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// 生命周期
onMounted(() => {
  // 【修复】不要自动恢复旧的生成结果，避免显示历史数据
  // restoreFromStorage() 已移除，改为仅在用户需要时手动恢复
  
  // 从路由查询参数中获取数据
  const query = router.currentRoute.value.query
  if (query.topic) {
    form.topic = query.topic
  }
  if (query.audience) {
    form.target_audience = query.audience
  }
  if (query.subject) form.subject = query.subject
  if (query.difficulty) form.difficulty = query.difficulty
  if (query.key_points) form.key_points_text = query.key_points
  if (query.reference_files) {
    const ids = String(query.reference_files).split(',').filter(Boolean)
    const names = String(query.reference_names || '').split(',')
    uploadedFiles.value = ids.map((file_id, index) => ({
      file_id,
      name: names[index] || file_id,
      url: names[index] || file_id
    }))
  }
  if (query.duration) {
    form.duration = parseInt(query.duration)
  }
  if (query.include_ppt) {
    form.include_ppt = query.include_ppt === 'true'
  }
  if (query.include_word) {
    form.include_word = query.include_word === 'true'
  }
})

onBeforeUnmount(() => {
  saveToStorage()
})
</script>

<style lang="scss" scoped>
.courseware-view {
  min-height: calc(100vh - 112px);
  padding: 24px;
  background: linear-gradient(180deg, rgba(10, 14, 39, 0.9) 0%, rgba(5, 8, 20, 1) 100%);
  overflow-y: auto;
}

/* 确保页面可以正常滚动 */
html, body {
  overflow-y: auto;
  height: 100%;
}

.courseware-container {
  max-width: 1400px;
  margin: 0 auto;
}

// 页面标题
.page-header {
  text-align: center;
  margin-bottom: 32px;

  h1 {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #00c8ff 0%, #7c3aed 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }

  .subtitle {
    font-size: 16px;
    color: rgba(255, 255, 255, 0.6);
  }
}

// 主内容区域
.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  overflow: visible;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

// 表单面板
.form-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  padding-right: 8px;
}

// 模板识别结果
.template-detected {
  margin-top: 12px;
  
  :deep(.el-alert) {
    background: rgba(0, 200, 255, 0.08);
    border-color: rgba(0, 200, 255, 0.2);
    
    .el-alert__title {
      color: rgba(255, 255, 255, 0.9);
    }
    
    .el-alert__description {
      color: rgba(255, 255, 255, 0.6);
    }
  }
}

// 自定义滚动条
.form-panel::-webkit-scrollbar {
  width: 6px;
}

.form-panel::-webkit-scrollbar-track {
  background: rgba(0, 200, 255, 0.1);
  border-radius: 3px;
}

.form-panel::-webkit-scrollbar-thumb {
  background: rgba(0, 200, 255, 0.5);
  border-radius: 3px;
}

.form-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 200, 255, 0.8);
}

.form-card {
  background: rgba(10, 14, 39, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 16px;
  padding: 24px;

  .card-header {
    margin-bottom: 20px;

    h3 {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 18px;
      font-weight: 600;
      color: #fff;
    }
  }

  :deep(.el-form-item) {
    margin-bottom: 16px;
  }

  :deep(.el-form-item__label) {
    color: rgba(255, 255, 255, 0.7);
    font-weight: 500;
  }
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

// 生成选项
.generation-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 200, 255, 0.05);
    border-color: rgba(0, 200, 255, 0.2);
  }

  &.active {
    background: rgba(0, 200, 255, 0.1);
    border-color: rgba(0, 200, 255, 0.4);

    .option-icon {
      background: linear-gradient(135deg, #00c8ff, #0099cc);
      color: #fff;
    }

    .option-check {
      background: #00c8ff;
      color: #fff;
    }
  }

  .option-icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: rgba(255, 255, 255, 0.6);
    transition: all 0.2s;
  }

  .option-info {
    flex: 1;

    .option-title {
      display: block;
      font-size: 15px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 4px;
    }

    .option-desc {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.4);
    }
  }

  .option-check {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: transparent;
    transition: all 0.2s;
  }
}

// 生成按钮
.generate-actions {
  display: flex;
  gap: 16px;
  padding-top: 8px;

  .generate-btn {
    flex: 1;
    height: 56px;
    font-size: 18px;
    background: linear-gradient(135deg, #00c8ff 0%, #7c3aed 100%);
    border: none;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 200, 255, 0.4);
    }
  }
}

// 结果面板
.result-panel {
  background: rgba(10, 14, 39, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 16px;
  padding: 24px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  padding-right: 8px;
}

// 自定义滚动条
.result-panel::-webkit-scrollbar {
  width: 6px;
}

.result-panel::-webkit-scrollbar-track {
  background: rgba(0, 200, 255, 0.1);
  border-radius: 3px;
}

.result-panel::-webkit-scrollbar-thumb {
  background: rgba(0, 200, 255, 0.5);
  border-radius: 3px;
}

.result-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 200, 255, 0.8);
}

// 生成中状态
.generating-status {
  .generating-header {
    margin-bottom: 24px;

    h3 {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 20px;
      color: #00c8ff;
    }
  }
}

// 生成过程可视化窗口
.generation-visualization {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  margin-bottom: 24px;
  overflow: hidden;

  .visualization-header {
    padding: 12px 16px;
    background: rgba(0, 200, 255, 0.1);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);

    h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.7);
    }
  }

  .visualization-body {
    padding: 20px;
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .slide-preview {
    width: 100%;
    max-width: 400px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);

    .slide-content {
      text-align: center;

      h5 {
        font-size: 18px;
        font-weight: 600;
        color: #fff;
        margin-bottom: 12px;
      }

      p {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.7);
        line-height: 1.6;
      }

      .cover-slide {
        h3 {
          font-size: 24px;
          font-weight: 700;
          color: #00c8ff;
          margin-bottom: 16px;
        }

        p {
          font-size: 16px;
          color: rgba(255, 255, 255, 0.6);
          margin-bottom: 8px;
        }
      }
    }
  }

  .preview-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;

    .el-icon {
      font-size: 32px;
      color: #00c8ff;
    }

    p {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.6);
    }
  }
}

.progress-steps {
  margin-bottom: 32px;
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  opacity: 0.4;
  transition: all 0.3s;

  &.active {
    opacity: 1;
  }

  &.current {
    .step-icon {
      background: #00c8ff;
      color: #fff;
      animation: pulse 1.5s infinite;
    }
  }

  .step-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.6);
    transition: all 0.3s;
  }

  .step-info {
    .step-name {
      display: block;
      font-size: 15px;
      color: #fff;
      margin-bottom: 2px;
    }

    .step-status {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.4);
      display: block;
      margin-bottom: 2px;
    }

    .step-details {
      font-size: 11px;
      color: rgba(0, 200, 255, 0.8);
      display: block;
      line-height: 1.4;
    }
  }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0, 200, 255, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(0, 200, 255, 0); }
}

// 空状态
.empty-state {
  text-align: center;
  padding: 60px 20px;

  .empty-icon {
    width: 120px;
    height: 120px;
    margin: 0 auto 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, rgba(0, 200, 255, 0.1), rgba(124, 58, 237, 0.1));
    border-radius: 50%;
    color: #00c8ff;
  }

  h3 {
    font-size: 24px;
    color: #fff;
    margin-bottom: 12px;
  }

  p {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.8;
    margin-bottom: 32px;
  }

  .feature-list {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 16px;
  }

  .feature-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.7);

    .el-icon {
      color: #00c8ff;
    }
  }
}

// 结果内容
.result-content {
  .result-header {
    text-align: center;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);

    h3 {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      font-size: 24px;
      color: #00ff88;
      margin-bottom: 8px;

      .el-icon {
        font-size: 28px;
      }
    }

    p {
      margin-bottom: 16px;
      font-size: 16px;
      color: rgba(255, 255, 255, 0.6);
    }

    .el-button {
      margin-top: 8px;
    }
  }
}

// 文件卡片列表
.result-files {
  display: grid;
  gap: 12px;
  margin-bottom: 24px;
}

// 窄屏：卡片改为可换行布局，避免图标/文字/按钮被挤在一行
@media (max-width: 640px) {
  .file-card {
    flex-wrap: wrap;
    padding: 14px 16px;
    gap: 12px;

    .file-actions {
      width: 100%;
      justify-content: flex-end;
    }
  }
}

.file-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 200, 255, 0.05);
    border-color: rgba(0, 200, 255, 0.2);
    transform: translateY(-1px);
  }

  .file-icon {
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;

    &.pptx {
      background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
      color: #fff;
    }

    &.docx {
      background: linear-gradient(135deg, #00c8ff, #0099cc);
      color: #fff;
    }

    &.animation {
      background: linear-gradient(135deg, #7c3aed, #6d28d9);
      color: #fff;
    }

    &.game {
      background: linear-gradient(135deg, #00ff88, #00cc6a);
      color: #fff;
    }
  }

  .file-info {
    flex: 1;

    .file-name {
      display: block;
      font-size: 16px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 4px;
    }

    .file-size {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.4);
    }
  }

  .file-actions {
    display: flex;
    gap: 8px;
  }
}

// 课程预览
.course-preview {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;

  .preview-header {
    padding: 12px 16px;
    background: rgba(0, 200, 255, 0.1);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);

    h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.7);
    }
  }

  .preview-body {
    padding: 16px;
  }

  .slides-preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .slide-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;

    &.cover {
      background: rgba(0, 200, 255, 0.1);
      border: 1px solid rgba(0, 200, 255, 0.2);
    }

    .slide-num {
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 6px;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.6);
    }

    .slide-title {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.8);
    }
  }

  .slide-more {
    text-align: center;
    padding: 8px;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.4);
  }
}

// 结果操作按钮
.result-actions {
  display: flex;
  gap: 16px;

  button {
    flex: 1;
    height: 48px;
    font-size: 16px;
  }
}
</style>
