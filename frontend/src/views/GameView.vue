<template>
  <div class="game-view">
    <div class="game-container">
      <div class="page-header">
        <h1>
          <el-icon :size="28"><TrophyBase /></el-icon>
          互动游戏生成中心
        </h1>
        <p class="subtitle">输入教学信息，AI自动生成HTML5互动教学游戏，支持在线试玩和下载</p>
      </div>

      <div class="main-content">
        <!-- 左侧：表单 -->
        <div class="form-panel">
          <div class="form-card">
            <div class="card-header">
              <h3><el-icon><Edit /></el-icon> 游戏基本信息</h3>
            </div>

            <el-form label-position="top" size="large">
              <el-form-item label="教学主题" required>
                <el-input
                  v-model="form.topic"
                  placeholder="例如：英语单词记忆、数学运算练习"
                  size="large"
                />
              </el-form-item>

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

                <el-form-item label="游戏类型">
                  <el-select v-model="form.game_type" size="large" placeholder="选择游戏类型">
                    <el-option
                      v-for="t in gameTypes"
                      :key="t.id"
                      :label="t.name"
                      :value="t.id"
                    />
                  </el-select>
                </el-form-item>
              </div>

              <el-form-item label="教学内容描述">
                <el-input
                  v-model="form.teaching_content"
                  type="textarea"
                  :rows="4"
                  placeholder="描述游戏需要覆盖的知识点和学习目标..."
                />
              </el-form-item>
            </el-form>
          </div>

          <div class="generate-actions">
            <el-button size="large" @click="resetForm">重置</el-button>
            <el-button type="primary" size="large" :loading="generating" @click="generateGame">
              <el-icon v-if="!generating"><TrophyBase /></el-icon>
              {{ generating ? '生成中...' : '生成互动游戏' }}
            </el-button>
          </div>
        </div>

        <!-- 右侧：结果 -->
        <div class="result-panel">
          <!-- 空状态 -->
          <div v-if="!generating && !result" class="empty-state">
            <div class="empty-icon">🎮</div>
            <h3>互动游戏工坊</h3>
            <p>填写左侧表单，AI将为您生成可直接在浏览器中试玩的HTML5教学互动游戏</p>
          </div>

          <!-- 生成中 -->
          <div v-if="generating" class="generating-state">
            <div class="generating-icon">
              <el-icon class="is-loading" :size="48"><Loading /></el-icon>
            </div>
            <h3>正在生成互动游戏...</h3>
            <p>AI正在设计游戏关卡和题目，请稍候</p>
            <el-progress :percentage="progress" :stroke-width="8" :show-text="true" status="primary" />
          </div>

          <!-- 结果 -->
          <div v-if="!generating && result" class="result-content">
            <div class="result-header">
              <div class="result-title">
                <el-icon :size="24" color="#67c23a"><CircleCheckFilled /></el-icon>
                <h3>{{ result.game_data?.title || '互动游戏生成完成' }}</h3>
              </div>
              <el-tag type="success">生成成功</el-tag>
            </div>

            <!-- 出厂质检报告：后端生成完成时已附带，纯规则离线扫描 -->
            <ComplianceReport v-if="compliance" :report="compliance" label="本次游戏" />

            <div class="result-description" v-if="result.game_data?.description">
              <p v-html="renderMath(result.game_data.description)"></p>
            </div>

            <!-- 内嵌HTML5游戏预览 -->
            <div class="preview-embed" v-if="result.html_content">
              <div class="preview-embed-header">
                <h4><el-icon><View /></el-icon> 游戏预览</h4>
                <div class="preview-controls">
                  <el-button size="small" @click="toggleFullscreen">
                    <el-icon><FullScreen /></el-icon> 全屏
                  </el-button>
                  <el-button size="small" type="primary" @click="previewGame">
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

            <!-- 游戏信息卡片 -->
            <div class="info-cards">
              <div class="info-card">
                <span class="info-label">游戏类型</span>
                <span class="info-value">{{ result.game_data?.game_type || form.game_type }}</span>
              </div>
              <div class="info-card">
                <span class="info-label">题目数量</span>
                <span class="info-value">{{ result.game_data?.questions?.length || result.game_data?.levels?.length || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-label">难度等级</span>
                <span class="info-value">{{ result.game_data?.difficulty || '适中' }}</span>
              </div>
              <div class="info-card">
                <span class="info-label">预计时间</span>
                <span class="info-value">{{ result.game_data?.estimated_time || '5-10分钟' }}</span>
              </div>
            </div>

            <!-- 游戏规则 -->
            <div class="rules-section" v-if="result.game_data?.rules">
              <h4>游戏规则</h4>
              <div class="rules-content">
                <template v-if="Array.isArray(result.game_data.rules)">
                  <p v-for="(rule, idx) in result.game_data.rules" :key="idx" v-html="renderMath((idx + 1) + '. ' + rule)"></p>
                </template>
                <p v-else v-html="renderMath(result.game_data.rules)"></p>
              </div>
            </div>

            <!-- 题目预览 -->
            <div class="questions-section" v-if="result.game_data?.questions?.length">
              <h4>题目预览</h4>
              <div class="question-list">
                <div
                  v-for="(q, idx) in result.game_data.questions.slice(0, 5)"
                  :key="idx"
                  class="question-item"
                >
                  <span class="q-number">Q{{ idx + 1 }}</span>
                  <span class="q-text" v-html="renderMath(q.question || q.title || String(q))"></span>
                </div>
                <p v-if="result.game_data.questions.length > 5" class="more-hint">
                  ... 共 {{ result.game_data.questions.length }} 道题目
                </p>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="result-actions">
              <el-button type="warning" @click="playGame">
                <el-icon><VideoPlay /></el-icon> 在线试玩
              </el-button>
              <el-button type="success" @click="downloadGame">
                <el-icon><Download /></el-icon> 下载游戏
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
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { renderMathInText } from '@/utils/mathRender'
import ComplianceReport from '@/components/ComplianceReport.vue'
import 'katex/dist/katex.min.css'
import {
  TrophyBase,
  Edit,
  Loading,
  CircleCheckFilled,
  VideoPlay,
  Download,
  RefreshRight,
  View,
  FullScreen
} from '@element-plus/icons-vue'

defineOptions({ name: 'GameView' })

const STORAGE_KEY = 'game_result'

const router = useRouter()
const previewContainer = ref(null)
const previewFrame = ref(null)

const form = reactive({
  topic: '',
  audience: '大学生',
  game_type: 'quiz',
  teaching_content: ''
})

const generating = ref(false)
const result = ref(null)
const progress = ref(0)
// 出厂质检报告（后端生成时附带）
const compliance = ref(null)
const gameTypes = ref([
  { id: '选择题', name: '选择题', description: '多项选择答题' },
  { id: '填空题', name: '填空题', description: '填空练习' },
  { id: '点击配对', name: '点击配对', description: '知识点连线匹配' },
  { id: '拖拽排序', name: '拖拽排序', description: '流程/步骤排序' },
  { id: '记忆翻牌', name: '记忆翻牌', description: '卡片记忆配对' }
])

function renderMath(text) {
  if (!text) return ''
  return renderMathInText(String(text))
}

/* ---- sessionStorage 持久化 ---- */
function restoreFromStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      if (saved.form) Object.assign(form, saved.form)
      if (saved.result) result.value = saved.result
      if (saved.compliance) compliance.value = saved.compliance
    }
  } catch { /* ignore */ }
}

function saveToStorage() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      form: { ...form },
      result: result.value,
      compliance: compliance.value
    }))
  } catch { /* ignore */ }
}

watch([() => ({ ...form }), result, compliance], saveToStorage, { deep: true })

onMounted(async () => {
  restoreFromStorage()

  // 从路由查询参数预填表单
  const query = router.currentRoute.value.query
  if (query.topic) form.topic = query.topic
  if (query.audience) form.audience = query.audience
  if (query.duration) form.duration = parseInt(query.duration)

  try {
    const res = await fetch(`${resolveApiBaseURL()}/courseware/game/types`)
    const data = await res.json()
    if (data.success && data.types) {
      gameTypes.value = data.types
    }
  } catch (e) {
    console.log('使用默认游戏类型列表')
  }
})

onBeforeUnmount(() => {
  saveToStorage()
})

async function generateGame() {
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
    const response = await fetch(`${resolveApiBaseURL()}/courseware/game/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: form.topic,
        audience: form.audience,
        teaching_content: form.teaching_content || form.topic,
        game_type: form.game_type
      })
    })

    const data = await response.json()
    if (data.success) {
      progress.value = 100
      result.value = data.game
      compliance.value = data.compliance || null
      ElMessage.success('互动游戏生成成功！')
    } else {
      ElMessage.error(data.message || '生成失败')
    }
  } catch (e) {
    console.error('游戏生成失败:', e)
    ElMessage.error('游戏生成失败，请检查网络连接')
  } finally {
    clearInterval(progressTimer)
    generating.value = false
  }
}

function playGame() {
  if (result.value?.html_content) {
    const blob = new Blob([result.value.html_content], { type: 'text/html; charset=utf-8' })
    window.open(URL.createObjectURL(blob), '_blank')
    return
  }
  if (!result.value?.task_dir) {
    ElMessage.warning('没有可试玩的游戏文件')
    return
  }
  const url = `${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(result.value.task_dir)}&topic=${encodeURIComponent(result.value.topic || form.topic)}`
  window.open(url, '_blank')
}

function downloadGame() {
  if (result.value?.html_content) {
    const blob = new Blob([result.value.html_content], { type: 'text/html; charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${form.topic || 'game'}_${form.game_type || 'game'}.html`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('文件下载中...')
    return
  }
  if (!result.value?.task_dir) {
    ElMessage.warning('没有可下载的游戏文件')
    return
  }
  const url = `${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(result.value.task_dir)}&topic=${encodeURIComponent(result.value.topic || form.topic)}`
  window.open(url, '_blank')
  ElMessage.success('文件下载中...')
}

function previewGame() {
  if (result.value?.html_content) {
    const blob = new Blob([result.value.html_content], { type: 'text/html; charset=utf-8' })
    window.open(URL.createObjectURL(blob), '_blank')
    return
  }
  if (!result.value?.task_dir) {
    ElMessage.warning('没有可预览的游戏文件')
    return
  }
  const url = `${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(result.value.task_dir)}&topic=${encodeURIComponent(result.value.topic || form.topic)}`
  window.open(url, '_blank')
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

function resetForm() {
  form.topic = ''
  form.audience = '大学生'
  form.game_type = 'quiz'
  form.teaching_content = ''
}

function resetAll() {
  resetForm()
  result.value = null
  progress.value = 0
  sessionStorage.removeItem(STORAGE_KEY)
}
</script>

<style scoped lang="scss">
.game-view {
  min-height: 100vh;
  padding: 20px;
}

.game-container {
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
    background: linear-gradient(135deg, #a18cd1, #fbc2eb);
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
    background: linear-gradient(135deg, #a18cd1, #fbc2eb);
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
    color: #a18cd1;
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
      height: 550px;
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

.rules-section, .questions-section {
  margin-bottom: 24px;

  h4 {
    color: #fff;
    font-size: 16px;
    margin-bottom: 12px;
    padding-left: 10px;
    border-left: 3px solid #a18cd1;
  }
}

.rules-content {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 12px;

  p {
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
    line-height: 1.8;
  }
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.question-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: rgba(255, 255, 255, 0.05);
  padding: 12px 16px;
  border-radius: 10px;

  .q-number {
    background: linear-gradient(135deg, #a18cd1, #fbc2eb);
    color: #1a1a2e;
    font-weight: 700;
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }

  .q-text {
    color: rgba(255, 255, 255, 0.8);
    font-size: 13px;
    line-height: 1.5;
  }
}

.more-hint {
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  text-align: center;
  padding: 8px;
}

.result-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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
