<template>
  <div class="animation-view">
    <div class="animation-container">
      <div class="page-header">
        <h1>
          <el-icon :size="28"><VideoCamera /></el-icon>
          教学动画创意中心
        </h1>
        <p class="subtitle">输入教学信息，AI智能生成动画方案、分镜脚本和HTML5预览</p>
      </div>

      <div class="main-content">
        <!-- 左侧：表单 -->
        <div class="form-panel">
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Edit /></el-icon> 动画基本信息</h3>
            </div>

            <!-- 学科选择 -->
            <div class="subject-section">
              <label class="section-label">选择学科</label>
              <div class="subject-tags">
                <button
                  type="button"
                  v-for="subject in subjectOptions"
                  :key="subject.value"
                  :class="['subject-tag', { active: form.subject === subject.value }]"
                  @click="selectSubject(subject)"
                >
                  <span class="tag-icon">{{ subject.icon }}</span>
                  <span class="tag-name">{{ subject.label }}</span>
                </button>
              </div>
            </div>

            <el-form label-position="top" size="large">
              <el-form-item label="教学主题" required>
                <el-input
                  v-model="form.topic"
                  placeholder="输入教学主题，或从下方示例中选择"
                  size="large"
                  @input="onTopicChange"
                />
              </el-form-item>

              <!-- 示例主题 -->
              <div class="examples-section" v-if="currentExamples.length">
                <label class="section-label">推荐主题（点击快速填入）</label>
                <div class="example-tags">
                  <button
                    type="button"
                    v-for="(example, idx) in currentExamples"
                    :key="idx"
                    class="example-tag"
                    @click="fillExample(example)"
                  >
                    {{ example.title }}
                  </button>
                </div>
              </div>

              <div class="form-grid">
                <el-form-item label="目标受众">
                  <el-select v-model="form.audience" size="large">
                    <el-option label="小学生" value="小学生" />
                    <el-option label="初中生" value="初中生" />
                    <el-option label="高中生" value="高中生" />
                    <el-option label="大学生" value="大学生" />
                    <el-option label="研究生" value="研究生" />
                  </el-select>
                </el-form-item>

                <el-form-item label="动画时长（分钟）">
                  <el-input-number v-model="form.duration" :min="1" :max="30" size="large" />
                </el-form-item>
              </div>

              <el-form-item label="教学内容描述">
                <el-input
                  v-model="form.teaching_content"
                  type="textarea"
                  :rows="4"
                  :placeholder="currentSubjectHint"
                />
              </el-form-item>
            </el-form>
          </div>

          <div class="generate-actions">
            <el-button size="large" @click="resetForm">重置</el-button>
            <el-button type="primary" size="large" :loading="generating" @click="generateAnimation">
              <el-icon v-if="!generating"><VideoCamera /></el-icon>
              {{ generating ? '生成中...' : '生成动画方案' }}
            </el-button>
          </div>
        </div>

        <!-- 右侧：结果 -->
        <div class="result-panel">
          <!-- 空状态 -->
          <div v-if="!generating && !result" class="empty-state">
            <div class="empty-icon">🎬</div>
            <h3>动画创意工坊</h3>
            <p>填写左侧表单，AI将为您生成完整的教学动画方案，包含分镜脚本、角色设计和HTML5预览</p>
          </div>

          <!-- 生成中 -->
          <div v-if="generating" class="generating-state">
            <div class="generating-icon">
              <el-icon class="is-loading" :size="48"><Loading /></el-icon>
            </div>
            <h3>正在生成动画方案...</h3>
            <p>AI正在设计动画分镜脚本和角色，请稍候</p>
            <el-progress :percentage="progress" :stroke-width="8" :show-text="true" status="primary" />
          </div>

          <!-- 结果 -->
          <div v-if="!generating && result" class="result-content">
            <div class="result-header">
              <div class="result-title">
                <el-icon :size="24" color="#67c23a"><CircleCheckFilled /></el-icon>
                <h3>{{ result.animation_data?.title || '动画方案生成完成' }}</h3>
              </div>
              <el-tag type="success">生成成功</el-tag>
            </div>

            <!-- 出厂质检报告：后端生成完成时已附带，纯规则离线扫描 -->
            <ComplianceReport v-if="compliance" :report="compliance" label="本次动画" />

            <div class="result-description" v-if="result.animation_data?.description">
              <p>{{ result.animation_data.description }}</p>
            </div>

            <!-- 内嵌HTML5动画预览 -->
            <div class="preview-embed" v-if="result.html_content">
              <div class="preview-embed-header">
                <h4><el-icon><View /></el-icon> 动画预览</h4>
                <div class="preview-controls">
                  <el-button size="small" @click="toggleFullscreen">
                    <el-icon><FullScreen /></el-icon> 全屏
                  </el-button>
                  <el-button size="small" type="primary" @click="previewAnimation">
                    <el-icon><View /></el-icon> 新窗口
                  </el-button>
                </div>
              </div>
              <div class="preview-frame-container" ref="previewContainer">
                <iframe
                  ref="previewFrame"
                  :srcdoc="result.html_content"
                  class="preview-frame"
                  sandbox="allow-scripts allow-same-origin"
                  frameborder="0"
                ></iframe>
              </div>
            </div>

            <!-- 动画信息卡片 -->
            <div class="info-cards">
              <div class="info-card">
                <span class="info-label">生成方式</span>
                <span class="info-value">{{ getGenerationMethodName(result.generation_method) }}</span>
              </div>
              <div class="info-card" v-if="result.subject">
                <span class="info-label">识别学科</span>
                <span class="info-value">{{ getSubjectName(result.subject) }}</span>
              </div>
              <div class="info-card">
                <span class="info-label">场景数量</span>
                <span class="info-value">{{ result.animation_data?.scenes?.length || result.scenes?.length || 0 }} 个</span>
              </div>
              <div class="info-card" v-if="result.knowledge_points?.length">
                <span class="info-label">知识点</span>
                <span class="info-value">{{ result.knowledge_points.length }} 个</span>
              </div>
            </div>

            <!-- 知识点列表（新系统输出） -->
            <div class="knowledge-section" v-if="result.knowledge_points?.length">
              <h4><el-icon><Reading /></el-icon> 提取的知识点</h4>
              <div class="knowledge-list">
                <div
                  v-for="(kp, idx) in result.knowledge_points"
                  :key="idx"
                  class="knowledge-item"
                >
                  <div class="kp-header">
                    <span class="kp-index">{{ idx + 1 }}</span>
                    <span class="kp-name">{{ kp.name }}</span>
                    <el-tag size="small" :type="getDifficultyType(kp.difficulty)">
                      {{ getDifficultyText(kp.difficulty) }}
                    </el-tag>
                  </div>
                  <p class="kp-desc" v-if="kp.description">{{ kp.description }}</p>
                </div>
              </div>
            </div>

            <!-- 分镜脚本列表 -->
            <div class="scenes-section" v-if="result.animation_data?.scenes?.length">
              <h4>分镜脚本</h4>
              <div class="scene-list">
                <div
                  v-for="(scene, idx) in result.animation_data.scenes"
                  :key="idx"
                  class="scene-item"
                >
                  <div class="scene-header">
                    <span class="scene-number">场景 {{ scene.scene_id || idx + 1 }}</span>
                    <span class="scene-title">{{ scene.title }}</span>
                    <el-tag size="small" type="info">{{ scene.duration || '' }}</el-tag>
                  </div>
                  <p class="scene-desc" v-html="renderMath(scene.description)"></p>
                  <p class="scene-script" v-if="scene.script">
                    <strong>台词：</strong><span v-html="renderMath(scene.script)"></span>
                  </p>
                </div>
              </div>
            </div>

            <!-- 角色设计 -->
            <div class="characters-section" v-if="result.animation_data?.characters?.length">
              <h4>角色设计</h4>
              <div class="character-grid">
                <div
                  v-for="(char, idx) in result.animation_data.characters"
                  :key="idx"
                  class="character-card"
                >
                  <div class="char-avatar">👨‍🏫</div>
                  <div class="char-name">{{ char.name }}</div>
                  <div class="char-role">{{ char.role }}</div>
                </div>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="result-actions">
              <el-button type="primary" @click="previewAnimation">
                <el-icon><View /></el-icon> 预览HTML
              </el-button>
              <el-button type="success" @click="downloadAnimation">
                <el-icon><Download /></el-icon> 下载HTML
              </el-button>
              <el-button @click="resetAll">
                <el-icon><RefreshRight /></el-icon> 重新生成
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { renderMathInText } from '@/utils/mathRender'
import ComplianceReport from '@/components/ComplianceReport.vue'
import 'katex/dist/katex.min.css'
import {
  VideoCamera,
  Edit,
  Loading,
  CircleCheckFilled,
  View,
  Download,
  RefreshRight,
  FullScreen,
  Reading
} from '@element-plus/icons-vue'

defineOptions({ name: 'AnimationView' })

const router = useRouter()

const previewContainer = ref(null)
const previewFrame = ref(null)

const form = reactive({
  topic: '',
  subject: 'general',
  audience: '大学生',
  duration: 5,
  teaching_content: ''
})

// 学科选项
const subjectOptions = [
  { value: 'mathematics', label: '数学', icon: '📐', examples: [
    { title: '二次函数图像', content: '二次函数y = ax² + bx + c的图像是一条抛物线。顶点坐标为(-b/2a, (4ac-b²)/4a)。当a > 0时开口向上，当a < 0时开口向下。' },
    { title: '三角函数', content: '正弦函数sin(x)和余弦函数cos(x)是周期为2π的周期函数。三角函数在几何和物理中有着广泛应用。' },
    { title: '勾股定理', content: '在直角三角形中，两条直角边的平方和等于斜边的平方：a² + b² = c²。' },
    { title: '圆的面积', content: '圆的面积公式是S = πr²，其中r是圆的半径。圆周率π约等于3.14159。' },
  ], hint: '例如：描述函数图像、几何定理、代数公式等...' },
  { value: 'physics', label: '物理', icon: '⚡', examples: [
    { title: '抛物运动', content: '抛体运动可以分解为水平方向的匀速直线运动和竖直方向的自由落体运动。运动轨迹是一条抛物线。' },
    { title: '牛顿三定律', content: '牛顿第一定律：物体保持静止或匀速直线运动状态。第二定律：F=ma。第三定律：作用力与反作用力大小相等方向相反。' },
    { title: '机械能守恒', content: '在只有重力或弹力做功的系统中，动能和势能可以相互转化，但机械能的总量保持不变。' },
    { title: '电路欧姆定律', content: '通过导体的电流与导体两端的电压成正比，与导体的电阻成反比：I = U/R。' },
  ], hint: '例如：描述物理现象、运动规律、力学原理等...' },
  { value: 'chemistry', label: '化学', icon: '⚗️', examples: [
    { title: '水分子结构', content: '水分子的化学式是H₂O，由两个氢原子和一个氧原子组成，呈V形结构，键角约104.5度。' },
    { title: '化学反应方程式', content: '化学反应中，反应物转化为生成物，原子种类和数量保持不变。例如：2H₂ + O₂ → 2H₂O。' },
    { title: '元素周期表', content: '元素周期表按原子序数排列，同一周期从左到右金属性递减，非金属性递增。' },
    { title: '酸碱中和反应', content: '酸和碱反应生成盐和水的反应称为中和反应。例如：HCl + NaOH → NaCl + H₂O。' },
  ], hint: '例如：描述分子结构、化学反应、元素性质等...' },
  { value: 'biology', label: '生物', icon: '🧬', examples: [
    { title: '细胞分裂过程', content: '有丝分裂分为间期、前期、中期、后期、末期五个阶段。间期进行DNA复制，分裂期将复制的染色体平均分配到两个子细胞中。' },
    { title: 'DNA双螺旋结构', content: 'DNA由两条反向平行的核苷酸链组成双螺旋结构，碱基配对遵循A-T、C-G原则。' },
    { title: '光合作用', content: '光合作用是绿色植物利用光能将二氧化碳和水转化为有机物并释放氧气的过程：6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂。' },
    { title: '细胞结构', content: '动物细胞包含细胞膜、细胞质、细胞核、线粒体等结构。植物细胞还具有细胞壁和叶绿体。' },
  ], hint: '例如：描述细胞结构、生理过程、遗传规律等...' },
  { value: 'geography', label: '地理', icon: '🌍', examples: [
    { title: '地球自转', content: '地球绕自转轴自西向东旋转，周期约24小时。自转产生昼夜交替现象。' },
    { title: '板块运动', content: '地球岩石圈分为若干板块，板块之间相互运动，形成山脉、海沟等地形。' },
    { title: '气候带分布', content: '根据纬度和海陆分布，地球分为热带、温带、寒带等气候带。' },
    { title: '水循环', content: '水在大气、陆地和海洋之间循环流动，包括蒸发、降水、径流等过程。' },
  ], hint: '例如：描述地理现象、气候特征、地形地貌等...' },
  { value: 'general', label: '综合', icon: '📊', examples: [
    { title: '项目管理流程', content: '项目管理包括启动、规划、执行、监控和收尾五个阶段。每个阶段都有特定的目标和交付物。' },
    { title: '思维导图制作', content: '思维导图是一种图形化的思维工具，以中心主题为核心，向外发散出相关的子主题和关键词。' },
    { title: '时间管理技巧', content: '有效的时间管理包括制定计划、优先级排序、避免拖延等策略。' },
    { title: '学习方法', content: '高效学习方法包括主动学习、间隔重复、思维导图、费曼技巧等。' },
  ], hint: '描述您想展示的内容和知识点...' },
]

const currentExamples = computed(() => {
  const subject = subjectOptions.find(s => s.value === form.subject)
  return subject ? subject.examples : []
})

const currentSubjectHint = computed(() => {
  const subject = subjectOptions.find(s => s.value === form.subject)
  return subject ? subject.hint : '描述您想展示的内容和知识点...'
})

function selectSubject(subject) {
  form.subject = subject.value
}

function fillExample(example) {
  form.topic = example.title
  form.teaching_content = example.content
}

function onTopicChange() {
  // 根据主题自动推测学科
  const keywords = {
    'mathematics': ['函数', '方程', '几何', '代数', '三角', '公式', '定理'],
    'physics': ['物理', '运动', '力', '能量', '电路', '速度', '加速度'],
    'chemistry': ['化学', '分子', '原子', '反应', '元素', '化合'],
    'biology': ['生物', '细胞', 'DNA', '分裂', '光合', '遗传'],
    'geography': ['地理', '地球', '气候', '地形', '板块'],
  }
  
  const topic = form.topic.toLowerCase()
  for (const [subject, kws] of Object.entries(keywords)) {
    if (kws.some(kw => topic.includes(kw))) {
      form.subject = subject
      return
    }
  }
}

const generating = ref(false)
const result = ref(null)
const progress = ref(0)
// 出厂质检报告（后端生成时附带，独立于产物存储，避免污染后端返回结构）
const compliance = ref(null)

// ====== sessionStorage 持久化 ======
const STORAGE_KEY = 'animation_result'
const STORAGE_KEY_COMPLIANCE = 'animation_compliance'

function restoreFromStorage() {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved && !result.value) {
      result.value = JSON.parse(saved)
    }
    const savedCompliance = sessionStorage.getItem(STORAGE_KEY_COMPLIANCE)
    if (savedCompliance && !compliance.value) {
      compliance.value = JSON.parse(savedCompliance)
    }
  } catch (e) {
    console.error('恢复动画结果失败:', e)
  }
}

function saveToStorage() {
  try {
    if (result.value) {
      const toSave = { ...result.value }
      if (toSave.html_content && toSave.html_content.length > 500 * 1024) {
        toSave.html_content = ''
      }
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
    }
    if (compliance.value) {
      sessionStorage.setItem(STORAGE_KEY_COMPLIANCE, JSON.stringify(compliance.value))
    }
  } catch (e) {
    console.error('保存动画结果失败:', e)
  }
}

watch([result, compliance], () => { saveToStorage() }, { deep: true })

// ====== 数学渲染辅助 ======
function renderMath(text) {
  if (!text) return ''
  return renderMathInText(text)
}

onMounted(async () => {
  restoreFromStorage()

  const query = router.currentRoute.value.query
  if (query.topic) form.topic = query.topic
  if (query.audience) form.audience = query.audience
  if (query.duration) form.duration = parseInt(query.duration)
})

onBeforeUnmount(() => {
  saveToStorage()
})

async function generateAnimation() {
  if (!form.topic.trim()) {
    ElMessage.warning('请输入教学主题')
    return
  }

  generating.value = true
  result.value = null
  progress.value = 0

  const progressTimer = setInterval(() => {
    if (progress.value < 90) {
      progress.value += Math.random() * 8 + 2
    }
  }, 500)

  try {
    const response = await fetch(`${resolveApiBaseURL()}/courseware/animation/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: form.topic,
        audience: form.audience,
        teaching_content: form.teaching_content || form.topic,
        duration: form.duration
      })
    })

    const data = await response.json()
    if (data.success) {
      progress.value = 100
      result.value = data.animation
      compliance.value = data.compliance || null
      ElMessage.success('动画方案生成成功！')
    } else {
      ElMessage.error(data.message || '生成失败')
    }
  } catch (e) {
    console.error('动画生成失败:', e)
    ElMessage.error('动画生成失败，请检查网络连接')
  } finally {
    clearInterval(progressTimer)
    generating.value = false
  }
}

function previewAnimation() {
  if (result.value?.html_content) {
    const blob = new Blob([result.value.html_content], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    return
  }
  if (!result.value?.task_dir) {
    ElMessage.warning('没有可预览的动画文件')
    return
  }
  const url = `${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(result.value.task_dir)}&topic=${encodeURIComponent(result.value.topic || form.topic)}`
  window.open(url, '_blank')
}

function downloadAnimation() {
  if (result.value?.html_content) {
    const blob = new Blob([result.value.html_content], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${form.topic || 'animation'}_动画.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('文件下载中...')
    return
  }
  if (!result.value?.task_dir) {
    ElMessage.warning('没有可下载的动画文件')
    return
  }
  const url = `${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(result.value.task_dir)}&topic=${encodeURIComponent(result.value.topic || form.topic)}`
  window.open(url, '_blank')
  ElMessage.success('文件下载中...')
}

function resetForm() {
  form.topic = ''
  form.audience = '大学生'
  form.duration = 5
  form.teaching_content = ''
}

function toggleFullscreen() {
  const container = previewContainer.value
  if (!container) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    container.requestFullscreen?.() || container.webkitRequestFullscreen?.()
  }
}

function resetAll() {
  resetForm()
  result.value = null
  progress.value = 0
  sessionStorage.removeItem(STORAGE_KEY)
}

// ====== 新系统辅助函数 ======
function getGenerationMethodName(method) {
  const names = {
    'subject_specific': '学科特定组件',
    'llm_html5': 'AI智能生成',
    'canvas_demo': 'Canvas演示',
    'storyboard_fallback': '分镜预览'
  }
  return names[method] || '教学演示'
}

function getSubjectName(subject) {
  const names = {
    'mathematics': '📐 数学',
    'physics': '⚡ 物理',
    'chemistry': '⚗️ 化学',
    'biology': '🧬 生物',
    'geography': '🌍 地理',
    'history': '📜 历史',
    'chinese': '📖 语文',
    'english': '🔤 英语',
    'general': '📊 通用'
  }
  return names[subject] || subject
}

function getDifficultyType(difficulty) {
  const types = {
    1: 'success',
    2: 'warning',
    3: 'danger'
  }
  return types[difficulty] || 'info'
}

function getDifficultyText(difficulty) {
  const texts = {
    1: '基础',
    2: '进阶',
    3: '高级'
  }
  return texts[difficulty] || '未知'
}
</script>

<style scoped lang="scss">
.animation-view {
  min-height: 100vh;
  padding: 20px;
}

.animation-container {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;

  h1 {
    font-size: 28px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: linear-gradient(135deg, #f6d365, #fda085);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }

  .subtitle {
    color: rgba(255, 255, 255, 0.6);
    margin-top: 8px;
    font-size: 14px;
  }
}

.main-content {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 24px;
  align-items: start;
}

.form-panel {
  position: sticky;
  top: 20px;
}

.form-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 24px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);

  .card-header {
    margin-bottom: 20px;

    h3 {
      font-size: 16px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }
}

.subject-section, .examples-section {
  margin-bottom: 20px;

  .section-label {
    display: block;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.6);
    margin-bottom: 10px;
    font-weight: 500;
  }
}

.subject-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.subject-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);

  .tag-icon {
    font-size: 16px;
  }

  &:hover {
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.3);
  }

  &.active {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(167, 139, 250, 0.2));
    border-color: rgba(56, 189, 248, 0.5);
    color: #fff;
  }
}

.example-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.example-tag {
  padding: 6px 12px;
  background: rgba(167, 139, 250, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.2);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);

  &:hover {
    background: rgba(167, 139, 250, 0.25);
    border-color: rgba(167, 139, 250, 0.4);
  }
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.generate-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;

  .el-button {
    flex: 1;
    height: 48px;
    font-size: 15px;
    border-radius: 12px;
  }

  .el-button--primary {
    background: linear-gradient(135deg, #f6d365, #fda085);
    border: none;
    color: #1a1a2e;
    font-weight: 600;

    &:hover {
      opacity: 0.9;
    }
  }
}

.result-panel {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 16px;
  padding: 30px;
  min-height: 500px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;

  .empty-icon {
    font-size: 64px;
    margin-bottom: 20px;
  }

  h3 {
    color: #fff;
    font-size: 20px;
    margin-bottom: 10px;
  }

  p {
    color: rgba(255, 255, 255, 0.5);
    max-width: 400px;
    line-height: 1.6;
  }
}

.generating-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;

  .generating-icon {
    margin-bottom: 20px;
    color: #f6d365;
  }

  h3 {
    color: #fff;
    margin-bottom: 8px;
  }

  p {
    color: rgba(255, 255, 255, 0.5);
    margin-bottom: 20px;
  }

  .el-progress {
    width: 300px;
  }
}

.result-content {
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .result-title {
      display: flex;
      align-items: center;
      gap: 10px;

      h3 {
        color: #fff;
        font-size: 18px;
      }
    }

    // 窄屏：标题与状态标签换行，避免挤在一行
    @media (max-width: 640px) {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }
  }

  .result-description {
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 20px;
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    line-height: 1.6;
  }

  .preview-embed {
    margin-bottom: 24px;
    .preview-embed-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      h4 {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 16px;
        color: #fff;
      }
      .preview-controls {
        display: flex;
        gap: 8px;
      }
    }
    .preview-frame-container {
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid rgba(0, 200, 255, 0.2);
      background: #000;
      &:fullscreen {
        .preview-frame { height: 100vh; }
      }
    }
    .preview-frame {
      width: 100%;
      height: 500px;
      border: none;
      display: block;
    }
  }
}

.info-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;

  .info-card {
    background: rgba(255, 255, 255, 0.05);
    padding: 14px;
    border-radius: 10px;
    text-align: center;

    .info-label {
      display: block;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.5);
      margin-bottom: 6px;
    }

    .info-value {
      display: block;
      font-size: 16px;
      color: #fff;
      font-weight: 600;
    }
  }
}

.scenes-section, .characters-section {
  margin-bottom: 24px;

  h4 {
    color: #fff;
    font-size: 16px;
    margin-bottom: 12px;
    padding-left: 10px;
    border-left: 3px solid #f6d365;
  }
}

.scene-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.scene-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);

  .scene-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;

    .scene-number {
      color: #f6d365;
      font-weight: 600;
      font-size: 13px;
    }

    .scene-title {
      color: #fff;
      font-weight: 500;
    }
  }

  .scene-desc {
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 6px;
  }

  .scene-script {
    color: rgba(255, 255, 255, 0.5);
    font-size: 12px;
    background: rgba(0, 0, 0, 0.2);
    padding: 8px 12px;
    border-radius: 8px;
    line-height: 1.5;

    strong {
      color: rgba(255, 255, 255, 0.7);
    }
  }
}

.character-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.character-card {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 12px;
  text-align: center;

  .char-avatar {
    font-size: 36px;
    margin-bottom: 8px;
  }

  .char-name {
    color: #fff;
    font-weight: 600;
    font-size: 14px;
  }

  .char-role {
    color: rgba(255, 255, 255, 0.5);
    font-size: 12px;
    margin-top: 4px;
  }
}

.result-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.knowledge-section {
  margin-bottom: 24px;

  h4 {
    color: #fff;
    font-size: 16px;
    margin-bottom: 12px;
    padding-left: 10px;
    border-left: 3px solid #38bdf8;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.knowledge-item {
  background: rgba(56, 189, 248, 0.08);
  padding: 14px;
  border-radius: 10px;
  border: 1px solid rgba(56, 189, 248, 0.15);
  transition: all 0.2s ease;

  &:hover {
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.25);
  }

  .kp-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;

    .kp-index {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: linear-gradient(135deg, #38bdf8, #0ea5e9);
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .kp-name {
      flex: 1;
      color: #e2e8f0;
      font-weight: 500;
      font-size: 14px;
    }
  }

  .kp-desc {
    color: rgba(255, 255, 255, 0.5);
    font-size: 12px;
    line-height: 1.5;
    margin: 0;
    padding-left: 34px;
  }
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .form-panel {
    position: static;
  }

  .info-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
