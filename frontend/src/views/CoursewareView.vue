<template>
  <div class="courseware-view">
    <div class="courseware-container">
      <!-- 页面标题 -->
      <div class="page-header">
        <h1>
          <el-icon :size="28"><VideoPlay /></el-icon>
          课件智能生成中心
        </h1>
        <p class="subtitle">输入课程信息，AI一键生成PPT课件、Word教案、动画创意、互动游戏</p>
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
                <el-form-item label="目标受众">
                  <el-select v-model="form.target_audience" size="large">
                    <el-option label="小学生" value="小学生" />
                    <el-option label="初中生" value="初中生" />
                    <el-option label="高中生" value="高中生" />
                    <el-option label="大一新生" value="大一新生" />
                    <el-option label="大二学生" value="大二学生" />
                    <el-option label="专业学生" value="专业学生" />
                    <el-option label="研究生" value="研究生" />
                    <el-option label="在职人员" value="在职人员" />
                    <el-option label="公众" value="公众" />
                  </el-select>
                </el-form-item>

                <el-form-item label="课时时长">
                  <el-input-number v-model="form.duration" :min="15" :max="180" :step="15" size="large" />
                </el-form-item>
              </div>
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
              <el-form-item label="参考文档 / 模板上传（可选）">
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
                      支持 PDF、Word、PPTX、TXT 格式，上传PPTX/DOCX可智能识别模板类型
                    </div>
                  </template>
                </el-upload>
                <!-- 模板识别结果 -->
                <div v-if="detectedTemplate" class="template-detected">
                  <el-alert
                    :title="detectedTemplate.title"
                    :description="detectedTemplate.details"
                    :type="detectedTemplate.alertType"
                    show-icon
                    :closable="false"
                  />
                  <el-button
                    v-if="detectedTemplate.suggested_template"
                    type="primary"
                    size="small"
                    plain
                    style="margin-top: 8px;"
                    @click="applyDetectedTemplate"
                  >
                    应用识别的模板类型
                  </el-button>
                </div>
              </el-form-item>

              <div class="form-grid">
                <el-form-item label="难度等级">
                  <el-select v-model="form.difficulty" size="large">
                    <el-option label="入门级" value="easy" />
                    <el-option label="中等难度" value="medium" />
                    <el-option label="进阶深入" value="hard" />
                  </el-select>
                </el-form-item>

                <el-form-item label="风格偏好">
                  <el-select v-model="form.style" size="large">
                    <el-option label="专业严谨" value="professional" />
                    <el-option label="轻松活泼" value="casual" />
                    <el-option label="简洁清晰" value="minimal" />
                    <el-option label="科技感" value="tech" />
                    <el-option label="商务正式" value="business" />
                    <el-option label="创意艺术" value="creative" />
                    <el-option label="学术研究" value="academic" />
                    <el-option label="教育培训" value="educational" />
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
                <el-form-item label="主题色">
                  <el-select v-model="form.theme_color" size="large">
                    <el-option label="蓝色系" value="蓝色系" />
                    <el-option label="绿色系" value="绿色系" />
                    <el-option label="红色系" value="红色系" />
                    <el-option label="紫色系" value="紫色系" />
                    <el-option label="橙色系" value="橙色系" />
                  </el-select>
                </el-form-item>

                <el-form-item label="PPT模板">
                  <el-select v-model="form.ppt_template" size="large">
                    <el-option label="标准教学" value="standard" />
                    <el-option label="互动教学" value="interactive" />
                    <el-option label="实验教学" value="experimental" />
                    <el-option label="学术讲座" value="lecture" />
                    <el-option label="商务演示" value="business" />
                    <el-option label="科技前沿" value="tech" />
                    <el-option label="艺术设计" value="art" />
                    <el-option label="教育培训" value="education" />
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
                <h4><el-icon><VideoCamera /></el-icon> PPT制作过程</h4>
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
                  <p>正在准备幻灯片...</p>
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
              <div class="feature-item">
                <el-icon><VideoCamera /></el-icon>
                <span>动画创意</span>
              </div>
              <div class="feature-item">
                <el-icon><Connection /></el-icon>
                <span>互动游戏</span>
              </div>
            </div>
          </div>

          <!-- 生成结果展示 -->
          <div v-else class="result-content">
            <div class="result-header">
              <h3>
                <el-icon><SuccessFilled /></el-icon>
                生成完成！
              </h3>
              <p>{{ currentResult.topic || '课件' }}</p>
              <el-button size="small" @click="openFileLocation">
                <el-icon><Folder /></el-icon> 打开文件所在目录
              </el-button>
            </div>

            <!-- 出厂质检报告：后端生成完成时已附带，纯规则离线扫描 -->
            <ComplianceReport
              v-if="currentResult.compliance"
              :report="currentResult.compliance"
              label="本次课件"
            />

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
                  <el-button type="primary" size="small" @click="downloadFile('pptx')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
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
                  <el-button type="primary" size="small" @click="downloadFile('docx')">
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  <el-button size="small" @click="previewFile('docx')">
                    <el-icon><View /></el-icon> 预览
                  </el-button>
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
              <el-button type="primary" size="large" @click="viewFullPreview">
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

// Palette 图标可能不存在于 element-plus, 使用 Setting 作为后备
const Palette = Setting

const router = useRouter()
const store = useAppStore()

// 表单数据
const form = reactive({
  topic: '',
  target_audience: '大一新生',
  duration: 45,
  difficulty: 'medium',
  style: 'professional',
  key_points_text: '',
  theme_color: '蓝色系',
  ppt_template: 'standard',
  include_ppt: true,
  include_word: true
})

// 上传文件状态
const uploadedFiles = ref([])

// 模板识别状态
const detectedTemplate = ref(null)

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
      url: response.filename
    })
    
    // 处理模板智能识别结果
    if (response.template_info) {
      const info = response.template_info
      const templateTypeMap = {
        'ppt_template': { title: 'PPT课件模板', alertType: 'success' },
        'lesson_plan_template': { title: '教案模板', alertType: 'info' },
        'document_template': { title: '文档模板', alertType: 'warning' },
      }
      const typeConfig = templateTypeMap[info.template_type] || { title: '未知模板', alertType: 'warning' }
      
      detectedTemplate.value = {
        title: `智能识别: ${typeConfig.title} (置信度 ${info.confidence}%)`,
        details: info.details || '',
        alertType: typeConfig.alertType,
        template_type: info.template_type,
        suggested_template: info.suggested_template || 'standard',
        file_format: info.file_format || '',
      }
      
      ElMessage.info(`已智能识别为${typeConfig.title}，可点击应用模板类型`)
    }
  } else {
    ElMessage.error('文件上传失败: ' + response.message)
  }
}

// 应用识别的模板类型
function applyDetectedTemplate() {
  if (!detectedTemplate.value) return
  const suggested = detectedTemplate.value.suggested_template
  const templateNameMap = {
    'standard': '标准教学',
    'interactive': '互动教学',
    'experimental': '实验教学',
    'lecture': '学术讲座',
  }
  form.ppt_template = suggested
  ElMessage.success(`已应用模板: ${templateNameMap[suggested] || suggested}`)
}

// 处理文件上传失败
function handleUploadError(error) {
  ElMessage.error('文件上传失败: 网络错误')
  console.error('上传失败:', error)
}

// 重置表单
function resetForm() {
  form.topic = ''
  form.target_audience = '大一新生'
  form.duration = 45
  form.difficulty = 'medium'
  form.style = 'professional'
  form.key_points_text = ''
  form.theme_color = '蓝色系'
  form.ppt_template = 'standard'
  form.include_ppt = true
  form.include_word = true
  currentResult.value = null
  slides.value = []
  uploadedFiles.value = []
  detectedTemplate.value = null
  clearStorage()
}



// 开始生成 - 根据选择的内容动态生成
async function startGeneration() {
  console.log('开始生成课件...')

  // 【修复】开始生成前先清理历史缓存，避免显示旧结果
  clearStorage()
  currentResult.value = null
  slides.value = []
  currentSlide.value = null

  // 表单校验
  if (!form.topic.trim()) {
    ElMessage.warning('请输入教学主题')
    return
  }
  
  if (!form.target_audience) {
    ElMessage.warning('请选择目标受众')
    return
  }
  
  if (!form.duration) {
    ElMessage.warning('请选择课时时长')
    return
  }

  // 确定需要生成的内容
  const selectedContent = []
  if (form.include_ppt) selectedContent.push('ppt')
  if (form.include_word) selectedContent.push('word')

  if (selectedContent.length === 0) {
    ElMessage.warning('请至少选择一种生成内容')
    return
  }

  console.log('生成内容:', selectedContent)

  // 构建动态生成步骤
  const steps = [
    { name: '智能需求分析', key: 'requirements' },
    { name: '结构化大纲生成', key: 'outline' },
    { name: '分页面精细化内容生成', key: 'content' }
  ]
  
  // 根据选择的内容添加相应步骤
  if (form.include_ppt) {
    steps.push({ name: 'PPT视觉与动画设计', key: 'ppt_style' })
    steps.push({ name: 'PPT排版与格式规范', key: 'ppt_layout' })
    steps.push({ name: '最终PPT生成', key: 'final_ppt' })
  }
  if (form.include_word) {
    steps.push({ name: 'Word教案生成', key: 'word_generation' })
  }
  steps.push({ name: '生成完成', key: 'complete' })
  
  // 重置状态
  generating.value = true
  currentProgressStep.value = 0
  progressPercent.value = 0
  generationSteps.value = steps.map(step => ({ name: step.name, status: '等待中' }))

  try {
    // 获取上传的参考文档和教学内容描述
    const teachingContent = form.key_points_text || ''
    const referenceDocs = uploadedFiles.value.map(file => file.name)
    
    let currentStep = 0
    
    // 步骤1: 智能需求分析
    updateProgressStep(currentStep, '分析中...', '正在分析教学主题、目标受众和教学内容需求')
    // 模拟需求分析
    await sleep(1000)
    updateProgressStep(currentStep++, '完成', '需求分析完成，识别出核心教学内容')
    await sleep(300)

    // 步骤2: 结构化大纲生成
    updateProgressStep(currentStep, '生成中...', '正在生成结构化大纲，规划内容结构')
    // 模拟大纲生成
    await sleep(1000)
    updateProgressStep(currentStep++, '完成', '大纲生成完成，包含完整的内容结构') 
    await sleep(300)

    // 步骤3: 分页面精细化内容生成
    updateProgressStep(currentStep, '生成中...', '正在为每个页面生成详细内容')
    
    // 模拟内容生成过程
    const sampleSlides = [
      { title: '封面页', content: form.topic, type: 'cover' },
      { title: '目录', content: '1. 课程介绍\n2. 核心内容\n3. 互动练习\n4. 总结与展望', type: 'table_of_contents' },
      { title: '课程介绍', content: '欢迎来到本课程，本课程将为您介绍' + form.topic + '的核心内容。', type: 'content' },
      { title: '核心内容', content: '本课程的核心内容包括：\n' + (form.key_points_text || '课程核心内容'), type: 'content' },
      { title: '互动练习', content: '让我们通过一些互动练习来巩固所学知识。', type: 'exercise' },
      { title: '总结与展望', content: '通过本课程的学习，您已经掌握了' + form.topic + '的基础知识。', type: 'summary' }
    ]
    
    // 逐个生成内容并显示
    for (let i = 0; i < sampleSlides.length; i++) {
      currentSlide.value = sampleSlides[i]
      await sleep(800)
    }
    
    updateProgressStep(currentStep++, '完成', '精细化内容生成完成') 
    await sleep(300)

    // 步骤4: PPT视觉与动画设计（如果选择了PPT）
    if (form.include_ppt) {
      updateProgressStep(currentStep, '生成中...', '正在生成PPT视觉风格和动画效果设计')
      // 模拟视觉风格生成
      await sleep(1000)
      updateProgressStep(currentStep++, '完成', `视觉风格设计完成，应用 ${form.theme_color} 主题色和 ${form.style} 风格`)
      await sleep(300)

      // 步骤5: PPT排版与格式规范
      updateProgressStep(currentStep, '生成中...', '正在进行PPT排版和格式规范处理')
      await sleep(500)
      updateProgressStep(currentStep++, '完成', 'PPT排版和格式规范处理完成')
      await sleep(300)

      // 步骤6: 最终PPT生成
      updateProgressStep(currentStep, '生成中...', '正在生成最终PPT文件，包含所有内容和设计')
      
      // 构建生成参数
      const pptConfig = {
        topic: form.topic,
        duration: form.duration,
        audience: form.target_audience,
        subject: 'general',
        theme_color: form.theme_color,
        style_preference: form.style,
        key_points: form.key_points_text.split('\n').filter(item => item.trim()),
        reference_docs: referenceDocs,
        template: form.ppt_template
      }

      // 调用后端API生成PPT
      const response = await fetch(`${resolveApiBaseURL()}/ppt/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(pptConfig)
      })
      
      const result = await response.json()
      console.log('PPT生成结果:', result)

      if (!result.success) {
        throw new Error(result.message || 'PPT生成失败')
      }

      // 轮询生成进度
      const taskId = result.task_id
      let attempts = 0
      const maxAttempts = 300 // 5分钟
      
      while (attempts < maxAttempts) {
        const statusResponse = await fetch(`${resolveApiBaseURL()}/ppt/status/${taskId}`)
        const statusRes = await statusResponse.json()
        
        if (statusRes.success) {
          const progress = statusRes.progress || 0
          const status = statusRes.status || 'pending'
          const currentStepName = statusRes.current_step || ''
          
          // 精确计算进度：将后端的0-100进度映射到当前步骤占总步骤的范围内
          const basePercent = Math.round((currentStep / steps.length) * 90)
          const stepRange = Math.round((1 / steps.length) * 90)
          progressPercent.value = Math.min(90, basePercent + Math.round((progress / 100) * stepRange))
          
          // 显示生成进度
          if (status === 'generating' && progress > 0) {
            console.log(`PPT生成中... ${progress}% - ${currentStepName}`)
            updateProgressStep(currentStep, `${progress}%`, currentStepName || '正在生成PPT...')
          }
          
          if (status === 'completed') {
            console.log('PPT生成完成！')
            
            // 设置结果
            currentResult.value = statusRes.result
            currentResult.value.task_id = taskId // 保存任务ID
            
            // 解析幻灯片
            parseSlides(currentResult.value)

            updateProgressStep(currentStep++, '完成', 'PPT文件生成完成')
            ElMessage.success('PPT生成完成！')
            
            // 清空当前幻灯片
            currentSlide.value = null
            break
          } else if (status === 'failed') {
            throw new Error(statusRes.error || 'PPT生成失败')
          } else if (status === 'unknown') {
            throw new Error('任务已过期或服务已重启，请重新生成')
          }
        }
        
        attempts++
        await sleep(1000) // 1秒轮询一次
      }
    
      if (attempts >= maxAttempts) {
        throw new Error('PPT生成超时，请稍后重试')
      }
    }

    // 生成Word教案（如果选择了）
    if (form.include_word) {
      updateProgressStep(currentStep, '生成中...', '正在生成Word教案')
      
      // 构建教案生成参数 - 根据目标受众动态适配学段
      const audienceToLevel = {
        '小学生': { level: '小学', grade: '小学' },
        '初中生': { level: '初中', grade: '初中' },
        '高中生': { level: '普通高中', grade: '高中' },
        '大一新生': { level: '普通高等院校', grade: '大一' },
        '大二学生': { level: '普通高等院校', grade: '大二' },
        '专业学生': { level: '普通高等院校', grade: '专业课程' },
        '研究生': { level: '普通高等院校', grade: '研究生' },
        '在职人员': { level: '职业高中/中等职业学校', grade: '在职培训' },
        '公众': { level: '普通高等院校', grade: '公开课' },
      }
      const levelInfo = audienceToLevel[form.target_audience] || { level: '普通高等院校', grade: '大一' }
      const lessonPlanConfig = {
        level: levelInfo.level,
        subject: form.topic,
        grade: levelInfo.grade,
        topic: form.topic,
        duration: form.duration,
        requirements: form.key_points_text
      }
      
      // 调用后端API生成教案
      const lessonPlanResponse = await fetch(`${resolveApiBaseURL()}/lesson-plan/generate-full`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(lessonPlanConfig)
      })
      
      const lessonPlanResult = await lessonPlanResponse.json()
      console.log('教案生成结果:', lessonPlanResult)
      
      if (lessonPlanResult.success) {
          // 导出教案为Word格式
          const exportResponse = await fetch(`${resolveApiBaseURL()}/lesson-plan/export`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              lesson_plan: lessonPlanResult.lesson_plan,
              export_format: 'docx',
              topic: form.topic  // 【修复】传递原始主题，确保文件名正确
            })
          })
        
        const exportResult = await exportResponse.json()
        console.log('教案导出结果:', exportResult)
        
        if (exportResult.success) {
          // 更新currentResult中的教案信息
          if (!currentResult.value) {
            currentResult.value = {}
          }
          currentResult.value.lesson_plan = lessonPlanResult.lesson_plan
          // 保存出厂质检报告（后端生成时已附带）
          if (lessonPlanResult.compliance) {
            currentResult.value.compliance = lessonPlanResult.compliance
          }
          currentResult.value.files = currentResult.value.files || {}
          currentResult.value.files.docx = exportResult.file_path
          
          updateProgressStep(currentStep++, '完成', 'Word教案生成完成')
          ElMessage.success('Word教案生成完成！')
        } else {
          console.error('教案导出失败:', exportResult.message)
          updateProgressStep(currentStep++, '失败', '教案导出失败')
        }
      } else {
        console.error('教案生成失败:', lessonPlanResult.message)
        updateProgressStep(currentStep++, '失败', '教案生成失败')
      }
    }

    // 最终步骤：生成完成
    updateProgressStep(currentStep, '完成', '所有内容生成完成')
    progressPercent.value = 100
    ElMessage.success('所有内容生成完成！')
  } catch (e) {
    console.error('生成失败:', e)
    ElMessage.error('生成失败: ' + (e.message || '请检查网络连接'))
    // 更新状态为失败
    if (currentProgressStep.value < generationSteps.value.length) {
      updateProgressStep(currentProgressStep.value, '失败', '生成过程中出现错误')
    }
  } finally {
    generating.value = false
  }
}

// 运行Python脚本
async function runPythonScript(script, args) {
  // 模拟Python脚本运行
  console.log('运行Python脚本:', script, '参数:', args)
  
  // 模拟脚本运行时间
  await sleep(3000)
  
  // 模拟脚本返回结果
  const topic = JSON.parse(args).topic
  const pptxPath = `generated_courseware/${encodeURIComponent(topic)}/PPT课件.pptx`
  
  return {
    success: true,
    message: 'PPT生成成功',
    pptx_path: pptxPath
  }
}

// 轮询生成进度
async function pollGenerationStatus(taskId) {
  let attempts = 0
  const maxAttempts = 300 // 5分钟
  let lastProgress = 0
  
  while (attempts < maxAttempts) {
    const statusResponse = await fetch(`${resolveApiBaseURL()}/ppt/status/${taskId}`)
    const statusRes = await statusResponse.json()
    
    if (statusRes.success) {
      const progress = statusRes.progress || 0
      const status = statusRes.status || 'pending'
      
      // 更新进度
      progressPercent.value = progress
      
      // 显示生成进度
      if (status === 'generating' && progress > lastProgress) {
        ElMessage.info(`PPT生成中... ${progress}%`)
        lastProgress = progress
      }
      
      if (status === 'completed') {
        ElMessage.success('PPT生成完成！')
        break
      } else if (status === 'failed') {
        throw new Error(statusRes.error || '生成失败')
      }
    }
    
    attempts++
    await sleep(1000) // 1秒轮询一次
  }
  
  if (attempts >= maxAttempts) {
    throw new Error('生成超时，请稍后重试')
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
    } else {
      // 回退到默认幻灯片
      parsedSlides.push({ title: result.topic || '课件', type: 'cover' })
      parsedSlides.push({ title: '课程内容', type: 'content' })
      parsedSlides.push({ title: '互动练习', type: 'exercise' })
      parsedSlides.push({ title: '课程总结', type: 'summary' })
    }

    slides.value = parsedSlides
  }
}

// 打开文件所在目录
function openFileLocation() {
  if (!currentResult.value) {
    ElMessage.warning('没有文件路径信息')
    return
  }
  
  // 构建文件路径
  let fullPath = ''
  if (currentResult.value.task_dir) {
    fullPath = currentResult.value.task_dir
  } else if (currentResult.value.files?.pptx) {
    fullPath = currentResult.value.files.pptx.replace(/\\[^\\]+$/, '')
  } else if (currentResult.value.files?.docx) {
    fullPath = currentResult.value.files.docx.replace(/\\[^\\]+$/, '')
  } else if (currentResult.value.animation_result?.task_dir) {
    fullPath = currentResult.value.animation_result.task_dir
  } else if (currentResult.value.game_result?.task_dir) {
    fullPath = currentResult.value.game_result.task_dir
  }
  
  if (!fullPath) {
    ElMessage.warning('没有文件路径信息')
    return
  }
  
  // 显示文件路径信息
  ElMessage.info(`生成的文件保存在: ${fullPath}`)
  
  // 确保路径格式正确
  let formattedPath = fullPath
  if (process.platform === 'win32') {
    // 对于Windows系统，确保路径格式正确
    formattedPath = fullPath.replace(/\//g, '\\')
  } else {
    // 对于其他系统，使用正斜杠
    formattedPath = fullPath.replace(/\\/g, '/')
  }
  
  // 在新窗口中打开文件路径
  try {
    window.open(`file:///${formattedPath.replace(/\\/g, '/')}`, '_blank')
  } catch (e) {
    console.error('打开文件路径失败:', e)
    ElMessage.error('打开文件路径失败，请手动前往该路径')
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
      // 优先使用task_dir（文件系统可靠），回退到task_id
      const taskDir = currentResult.value.task_dir
      const topic = currentResult.value.topic || form.topic
      if (taskDir) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/download/pptx?task_dir=${encodeURIComponent(taskDir)}&topic=${encodeURIComponent(topic)}`
        hasDownload = true
      } else {
        const taskId = currentResult.value.task_id || currentResult.value.taskId
        if (taskId) {
          downloadUrl = `${resolveApiBaseURL()}/ppt/download/${taskId}`
          hasDownload = true
        } else {
          ElMessage.warning('没有可下载的PPT文件')
        }
      }
    } else if (type === 'docx') {
      if (currentResult.value.files?.docx) {
        // 使用后端API下载Word文件
        const taskDir = currentResult.value.files.docx.replace(/\\[^\\]+$/, '')
        downloadUrl = `${resolveApiBaseURL()}/courseware/download/docx?task_dir=${encodeURIComponent(taskDir)}`
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的Word文件')
      }
    } else if (type === 'animation') {
      const taskDir = currentResult.value.animation_result?.task_dir
      if (taskDir) {
        downloadUrl = `${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(taskDir)}`
        hasDownload = true
      } else {
        ElMessage.warning('没有可下载的动画文件')
      }
    } else if (type === 'game') {
      const taskDir = currentResult.value.game_result?.task_dir
      if (taskDir) {
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
    const taskDir = currentResult.value.animation_result?.task_dir
    if (taskDir) {
      window.open(`${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(taskDir)}`, '_blank')
    } else {
      ElMessage.warning('没有可预览的动画文件')
    }
  } else if (type === 'game') {
    const taskDir = currentResult.value.game_result?.task_dir
    if (taskDir) {
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
    // 添加 task_dir 和 topic 参数以支持文件系统回退
    const taskDir = encodeURIComponent(currentResult.value?.task_dir || '')
    const topic = encodeURIComponent(currentResult.value?.topic || form.topic || '')
    const previewResponse = await fetch(`${resolveApiBaseURL()}/ppt/preview/${taskId}?task_dir=${taskDir}&topic=${topic}`)
    const previewRes = await previewResponse.json()
    
    if (previewRes.success) {
      const previewId = 'task_' + Date.now()
      router.push({
        path: `/preview/${previewId}`,
        query: {
          courseware: JSON.stringify({
            ppt_content: previewRes.ppt_data,
            task_id: currentResult.value?.task_id || taskId,
            task_dir: currentResult.value?.task_dir || '',
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

  const taskId = 'task_' + Date.now()
  router.push({
    path: `/preview/${taskId}`,
    query: {
      courseware: JSON.stringify(currentResult.value)
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
