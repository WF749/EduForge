<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="95vw"
    :close-on-click-modal="false"
    :close-on-press-escape="canClose"
    :show-close="canClose"
    class="generation-visual-modal"
    :class="{ 'fullscreen-mode': isFullscreen }"
  >
    <div class="visual-workspace" v-if="taskId">
      <!-- 左侧进度区 -->
      <div class="progress-panel">
        <!-- 头部信息 -->
        <div class="panel-header">
          <h3>
            <el-icon><VideoPlay /></el-icon>
            生成进度
          </h3>
          <el-tag :type="statusTagType" size="small">
            {{ statusText }}
          </el-tag>
        </div>

        <!-- 阶段进度 -->
        <div class="stage-progress">
          <div 
            v-for="(stage, index) in stages" 
            :key="stage.id"
            class="stage-item"
            :class="{ 
              'completed': isStageCompleted(stage.id),
              'active': currentStage === stage.id,
              'pending': isStagePending(stage.id)
            }"
          >
            <div class="stage-indicator">
              <div class="stage-icon">
                <el-icon v-if="isStageCompleted(stage.id)"><Check /></el-icon>
                <el-icon v-else-if="currentStage === stage.id" class="is-loading"><Loading /></el-icon>
                <span v-else>{{ index + 1 }}</span>
              </div>
              <div class="stage-line" v-if="index < stages.length - 1"></div>
            </div>
            <div class="stage-content">
              <div class="stage-name">{{ stage.name }}</div>
              <div class="stage-message" v-if="currentStage === stage.id">
                {{ currentMessage }}
              </div>
            </div>
          </div>
        </div>

        <!-- 总体进度条 -->
        <div class="overall-progress">
          <div class="progress-label">
            <span>总体进度</span>
            <span>{{ progress }}%</span>
          </div>
          <el-progress 
            :percentage="progress" 
            :stroke-width="10"
            :color="progressColor"
            :show-text="false"
          />
        </div>

        <!-- 已生成页面列表 -->
        <div class="pages-list" v-if="pages.length > 0">
          <div class="list-header">
            <span>已生成页面</span>
            <span class="count">{{ pages.length }} 页</span>
          </div>
          <div class="thumbnail-scroll">
            <div 
              v-for="(page, index) in pages" 
              :key="index"
              class="page-thumb"
              :class="{ 'active': currentPreviewPage === index + 1 }"
              @click="currentPreviewPage = index + 1"
            >
              <span class="thumb-num">{{ index + 1 }}</span>
              <span class="thumb-title">{{ getPageTitle(page) }}</span>
            </div>
          </div>
        </div>

        <!-- 错误信息 -->
        <div class="error-panel" v-if="errorMsg">
          <div class="error-icon">
            <el-icon><Warning /></el-icon>
          </div>
          <div class="error-content">
            <div class="error-title">生成出错</div>
            <div class="error-message">{{ errorMsg }}</div>
          </div>
          <el-button type="danger" size="small" @click="handleRetry">
            重试
          </el-button>
        </div>
      </div>

      <!-- 右侧预览区 -->
      <div class="preview-panel">
        <!-- PPT预览 -->
        <PPTPreview
          v-if="contentType === 'ppt'"
          :pages="pages"
          :current-page="currentPreviewPage"
          :fullscreen="isPreviewFullscreen"
          @update:currentPage="currentPreviewPage = $event"
          @update:fullscreen="isPreviewFullscreen = $event"
        />

        <!-- 其他内容类型预览（可扩展） -->
        <div v-else class="generic-preview">
          <div class="preview-placeholder">
            <el-icon :size="64"><Document /></el-icon>
            <p>{{ contentType }} 预览</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 无任务状态 -->
    <div class="empty-state" v-else>
      <el-icon class="is-loading" :size="48"><Loading /></el-icon>
      <p>正在初始化...</p>
    </div>

    <!-- 底部操作栏 -->
    <template #footer>
      <div class="dialog-footer">
        <div class="footer-left">
          <el-button 
            v-if="status === 'running'" 
            type="warning" 
            @click="handlePause"
          >
            <el-icon><VideoPause /></el-icon>
            暂停
          </el-button>
          <el-button 
            v-if="status === 'paused'" 
            type="primary" 
            @click="handleResume"
          >
            <el-icon><VideoPlay /></el-icon>
            继续
          </el-button>
        </div>
        
        <div class="footer-right">
          <el-button @click="handleMinimize">
            <el-icon><SemiSelect /></el-icon>
            最小化
          </el-button>
          <el-button 
            v-if="status !== 'running' && status !== 'paused'" 
            type="primary" 
            @click="handleDownload"
            :disabled="!downloadReady"
          >
            <el-icon><Download /></el-icon>
            下载文件
          </el-button>
          <el-button 
            v-if="status !== 'running' && status !== 'paused'" 
            type="success"
            @click="handleClose"
          >
            完成
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  VideoPlay, VideoPause, Loading, Check, Warning, 
  Document, Download, SemiSelect 
} from '@element-plus/icons-vue'
import PPTPreview from './PPTPreview.vue'
import { useSSE, StageNames, MessageType } from '../hooks/useSSE'
import { resolveApiBaseURL } from '@/api/baseUrl'

const props = defineProps({
  // 是否显示
  modelValue: {
    type: Boolean,
    default: false
  },
  // 任务ID
  taskId: {
    type: String,
    default: ''
  },
  // 内容类型
  contentType: {
    type: String,
    default: 'ppt' // ppt | lesson_plan | animation | game
  },
  // 任务参数
  params: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'update:modelValue', 
  'completed', 
  'error', 
  'close',
  'minimize'
])

// ============ 状态 ============
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const isFullscreen = ref(false)
const isPreviewFullscreen = ref(false)

// 生成状态
const status = ref('pending') // pending | running | paused | completed | failed
const progress = ref(0)
const currentStage = ref('init')
const currentMessage = ref('准备开始...')
const errorMsg = ref('')
const downloadReady = ref(false)

// 预览相关
const pages = ref([])
const currentPreviewPage = ref(1)
const resultData = ref(null)

// SSE连接
let sse = null

// ============ 阶段定义 ============
const stages = [
  { id: 'init', name: '初始化' },
  { id: 'requirements_parsing', name: '需求解析' },
  { id: 'outline_generation', name: '大纲生成' },
  { id: 'content_generation', name: '内容生成' },
  { id: 'style_rendering', name: '样式渲染' },
  { id: 'file_generation', name: '文件生成' },
  { id: 'validation', name: '校验' },
  { id: 'completed', name: '完成' }
]

// ============ 计算属性 ============
const dialogTitle = computed(() => {
  const titles = {
    ppt: 'PPT课件生成',
    lesson_plan: 'Word教案生成',
    animation: '动画演示生成',
    game: '互动游戏生成'
  }
  return titles[props.contentType] || '内容生成'
})

const statusText = computed(() => {
  const texts = {
    pending: '等待中',
    running: '生成中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status.value] || '未知'
})

const statusTagType = computed(() => {
  const types = {
    pending: 'info',
    running: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return types[status.value] || 'info'
})

const progressColor = computed(() => {
  if (status.value === 'failed') return '#f56c6c'
  if (status.value === 'completed') return '#67c23a'
  return '#409eff'
})

const canClose = computed(() => {
  return status.value === 'pending' || 
         status.value === 'completed' || 
         status.value === 'failed'
})

// ============ 方法 ============

// 初始化SSE连接
function initSSE() {
  if (!props.taskId) return

  sse = useSSE()

  // 监听SSE消息
  watch(sse.lastMessage, (msg) => {
    if (!msg) return

    switch (msg.type) {
      case MessageType.PROGRESS:
        progress.value = msg.progress || 0
        currentStage.value = msg.stage || 'init'
        currentMessage.value = msg.message || ''
        if (msg.message) {
          currentMessage.value = msg.message
        }
        break

      case MessageType.PREVIEW_UPDATE:
        const pageIndex = msg.page_index
        const pageData = msg.page_data
        if (pageIndex && pageData) {
          while (pages.value.length < pageIndex) {
            pages.value.push(null)
          }
          pages.value[pageIndex - 1] = pageData
          currentPreviewPage.value = pageIndex
        }
        break

      case MessageType.STAGE_START:
        currentStage.value = msg.stage
        break

      case MessageType.COMPLETED:
        status.value = 'completed'
        progress.value = 100
        currentStage.value = 'completed'
        currentMessage.value = '生成完成！'
        downloadReady.value = true
        resultData.value = msg.result
        ElMessage.success('生成完成！')
        emit('completed', msg.result)
        break

      case MessageType.ERROR:
        status.value = 'failed'
        errorMsg.value = msg.error || '生成失败'
        ElMessage.error(msg.error || '生成失败')
        emit('error', { error: msg.error, details: msg.error_details })
        break

      case 'heartbeat':
        // 心跳，保持连接
        break
    }
  }, { immediate: true })

  // 监听状态变化
  watch(sse.status, (newStatus) => {
    if (newStatus === 'connected') {
      status.value = 'running'
    } else if (newStatus === 'error') {
      if (!errorMsg.value) {
        errorMsg.value = sse.error.value || '连接失败'
      }
    }
  })

  // 连接SSE
  const apiBase = getApiBaseUrl()
  sse.connect(`${apiBase}/courseware/sse/${props.taskId}`)
}

function getApiBaseUrl() {
  return resolveApiBaseURL()
}

// 阶段状态判断
function isStageCompleted(stageId) {
  const stageOrder = stages.map(s => s.id)
  const currentIdx = stageOrder.indexOf(currentStage.value)
  const checkIdx = stageOrder.indexOf(stageId)
  return checkIdx < currentIdx || currentStage.value === 'completed'
}

function isStagePending(stageId) {
  const stageOrder = stages.map(s => s.id)
  const currentIdx = stageOrder.indexOf(currentStage.value)
  const checkIdx = stageOrder.indexOf(stageId)
  return checkIdx > currentIdx && currentStage.value !== 'completed'
}

// 获取页面标题
function getPageTitle(page) {
  if (!page) return '加载中'
  return page.core_topic?.slice(0, 8) || page.page_type || '页面'
}

// 操作处理
function handlePause() {
  // TODO: 调用后端暂停接口
  ElMessage.info('暂停生成')
}

function handleResume() {
  // TODO: 调用后端恢复接口
  ElMessage.info('继续生成')
}

function handleRetry() {
  errorMsg.value = ''
  status.value = 'pending'
  progress.value = 0
  pages.value = []
  // TODO: 重新发起生成请求
  ElMessage.info('正在重新生成...')
}

function handleDownload() {
  if (!resultData.value) return
  
  const filePath = resultData.value.pptx_path || resultData.value.file_path
  if (filePath) {
    // 构建下载链接
    const apiBase = getApiBaseUrl()
    const filename = filePath.split('/').pop() || filePath.split('\\').pop()
    const downloadUrl = `${apiBase}/courseware/download/pptx?task_dir=${encodeURIComponent(resultData.value.task_dir)}`
    
    // 创建下载
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = filename
    a.click()
    
    ElMessage.success('开始下载')
  }
}

function handleMinimize() {
  emit('minimize')
  visible.value = false
}

function handleClose() {
  if (sse) {
    sse.disconnect()
  }
  emit('close')
  visible.value = false
}

// ============ 生命周期 ============

onMounted(() => {
  if (props.taskId) {
    initSSE()
  }
})

onUnmounted(() => {
  if (sse) {
    sse.disconnect()
  }
})

// 监听任务ID变化
watch(() => props.taskId, (newId) => {
  if (newId && visible.value) {
    initSSE()
  }
})

// 监听显示状态
watch(() => props.modelValue, (newVal) => {
  if (newVal && props.taskId && !sse) {
    initSSE()
  }
})
</script>

<style scoped>
/* 模态框样式 */
.generation-visual-modal {
  --el-dialog-padding-primary: 0;
}

.generation-visual-modal :deep(.el-dialog__header) {
  padding: 16px 20px;
  margin: 0;
  background: rgba(26, 31, 78, 0.95);
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
}

.generation-visual-modal :deep(.el-dialog__title) {
  color: white;
  font-size: 18px;
}

.generation-visual-modal :deep(.el-dialog__body) {
  padding: 0;
  height: calc(90vh - 140px);
}

/* 工作区布局 */
.visual-workspace {
  display: flex;
  height: 100%;
  background: #0f1225;
}

/* 左侧进度区 */
.progress-panel {
  width: 320px;
  min-width: 320px;
  background: rgba(26, 31, 78, 0.98);
  border-right: 1px solid rgba(0, 200, 255, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
}

.panel-header h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  color: white;
  font-size: 16px;
  margin: 0;
}

/* 阶段进度 */
.stage-progress {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.stage-item {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.stage-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stage-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #7f8c8d;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  z-index: 1;
}

.stage-item.completed .stage-icon {
  background: #67c23a;
  color: white;
}

.stage-item.active .stage-icon {
  background: #409eff;
  color: white;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.5); }
  50% { box-shadow: 0 0 0 8px rgba(64, 158, 255, 0); }
}

.stage-line {
  width: 2px;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
  margin: 4px 0;
}

.stage-item.completed .stage-line {
  background: #67c23a;
}

.stage-content {
  flex: 1;
  padding-top: 4px;
}

.stage-name {
  color: #b0b8c4;
  font-size: 14px;
}

.stage-item.completed .stage-name {
  color: #67c23a;
}

.stage-item.active .stage-name {
  color: #409eff;
  font-weight: bold;
}

.stage-message {
  color: #7f8c8d;
  font-size: 12px;
  margin-top: 4px;
}

/* 总体进度条 */
.overall-progress {
  padding: 16px 20px;
  border-top: 1px solid rgba(0, 200, 255, 0.1);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  color: #b0b8c4;
  font-size: 12px;
  margin-bottom: 8px;
}

/* 已生成页面列表 */
.pages-list {
  border-top: 1px solid rgba(0, 200, 255, 0.1);
  padding: 12px 16px;
  max-height: 200px;
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  color: #b0b8c4;
  font-size: 12px;
  margin-bottom: 8px;
}

.list-header .count {
  color: #409eff;
}

.thumbnail-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.page-thumb {
  flex-shrink: 0;
  width: 80px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.page-thumb:hover {
  background: rgba(255, 255, 255, 0.1);
}

.page-thumb.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.1);
}

.thumb-num {
  display: block;
  color: #7f8c8d;
  font-size: 10px;
}

.thumb-title {
  display: block;
  color: #b0b8c4;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 错误面板 */
.error-panel {
  margin: 16px;
  padding: 16px;
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.error-icon {
  color: #f56c6c;
  font-size: 20px;
}

.error-content {
  flex: 1;
}

.error-title {
  color: #f56c6c;
  font-weight: bold;
  margin-bottom: 4px;
}

.error-message {
  color: #b0b8c4;
  font-size: 12px;
}

/* 右侧预览区 */
.preview-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.generic-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-placeholder {
  text-align: center;
  color: #7f8c8d;
}

.preview-placeholder p {
  margin-top: 16px;
}

/* 空状态 */
.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #7f8c8d;
  gap: 16px;
}

/* 底部操作栏 */
.dialog-footer {
  display: flex;
  justify-content: space-between;
  padding: 12px 20px;
  background: rgba(26, 31, 78, 0.95);
  border-top: 1px solid rgba(0, 200, 255, 0.2);
}

.footer-left,
.footer-right {
  display: flex;
  gap: 12px;
}

/* 全屏模式 */
.fullscreen-mode :deep(.el-dialog__body) {
  height: calc(100vh - 100px);
}
</style>
