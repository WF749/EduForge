<template>
  <div class="knowledge-view">
    <div class="knowledge-container">
      <!-- Page Header -->
      <div class="page-header">
        <div class="header-info">
          <h1>本地知识库管理</h1>
          <p class="subtitle">构建和管理您的专业知识库，用于RAG检索增强</p>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon documents">
            <el-icon :size="28"><Document /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.total_documents || 0 }}</span>
            <span class="stat-label">文档数量</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon chunks">
            <el-icon :size="28"><Grid /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.total_chunks || 0 }}</span>
            <span class="stat-label">知识块</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon status" :class="{ active: stats.status === 'ready' }">
            <el-icon :size="28"><Connection /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.status || '未知' }}</span>
            <span class="stat-label">服务状态</span>
          </div>
        </div>
      </div>

      <!-- Main Content Grid -->
      <div class="content-grid">
        <!-- Upload Section -->
        <div class="upload-section">
          <div class="section-card">
            <div class="card-header">
              <h3>
                <el-icon :size="20"><Upload /></el-icon>
                上传知识文件
              </h3>
            </div>

            <el-upload
              ref="uploadRef"
              drag
              :auto-upload="false"
              :multiple="true"
              accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md"
              :on-change="handleFileChange"
              :file-list="fileList"
              class="upload-area"
            >
              <div class="upload-content">
                <div class="upload-icon">
                  <el-icon :size="48"><UploadFilled /></el-icon>
                </div>
                <div class="upload-text">拖拽文件到此处或点击上传</div>
                <div class="upload-formats">
                  <span class="format-tag">PDF</span>
                  <span class="format-tag">Word</span>
                  <span class="format-tag">PPT</span>
                  <span class="format-tag">TXT</span>
                  <span class="format-tag">Markdown</span>
                </div>
                <div class="upload-hint">
                  支持多份参考资料，系统会自动解析并添加到知识库
                </div>
              </div>
            </el-upload>

            <div class="upload-actions">
              <el-button @click="fileList = []" :disabled="fileList.length === 0 || uploading">
                清空列表
              </el-button>
              <el-button
                type="primary"
                :loading="uploading"
                @click="uploadFiles"
                :disabled="fileList.length === 0"
              >
                <el-icon><Upload /></el-icon>
                解析并添加到知识库
              </el-button>
            </div>

            <!-- 上传进度条 -->
            <div class="upload-progress" v-if="uploading || uploadProgress > 0">
              <el-progress
                :percentage="uploadProgress"
                :stroke-width="10"
                :color="uploadProgress >= 100 ? '#43e97b' : '#00c8ff'"
                :format="() => `${uploadProgress}%`"
              />
              <div class="progress-status" v-if="uploadStatus">
                <el-icon v-if="uploading" class="rotating"><Loading /></el-icon>
                <el-icon v-else-if="uploadProgress >= 100" style="color: #43e97b"><SuccessFilled /></el-icon>
                <span>{{ uploadStatus }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Documents List Section -->
        <div class="documents-section">
          <div class="section-card">
            <div class="card-header">
              <h3>
                <el-icon :size="20"><Collection /></el-icon>
                知识库文档
              </h3>
              <el-button
                text
                type="danger"
                @click="clearKnowledgeBase"
                :disabled="documents.length === 0"
              >
                <el-icon><Delete /></el-icon>
                清空知识库
              </el-button>
            </div>

            <div class="documents-list" v-if="documents.length > 0">
              <div
                v-for="doc in documents"
                :key="doc.id"
                class="document-item"
              >
                <div class="doc-icon">
                  <el-icon :size="20"><Document /></el-icon>
                </div>
                <div class="doc-info">
                  <span class="doc-name">{{ doc.metadata?.filename || doc.name || doc.id }}</span>
                  <div class="doc-meta">
                    <span class="meta-item">
                      <el-icon :size="12"><Grid /></el-icon>
                      {{ doc.count || 0 }} 个知识块
                    </span>
                    <span class="meta-item" v-if="doc.metadata?.file_type">
                      <el-icon :size="12"><Files /></el-icon>
                      {{ doc.metadata.file_type }}
                    </span>
                  </div>
                </div>
                <el-button
                  :icon="Delete"
                  text
                  type="danger"
                  class="delete-btn"
                  @click="deleteDocument(doc.id)"
                />
              </div>
            </div>

            <div v-else-if="loadingDocs" class="empty-state">
              <el-icon :size="40" class="rotating"><Loading /></el-icon>
              <p>加载文档列表中...</p>
            </div>

            <div v-else class="empty-state">
              <div class="empty-icon">
                <el-icon :size="56"><Folder /></el-icon>
              </div>
              <p>知识库为空</p>
              <span>请上传文档以构建您的知识库</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Query Section -->
      <div class="query-section">
        <div class="section-card">
          <div class="card-header">
            <h3>
              <el-icon :size="20"><Search /></el-icon>
              检索测试
            </h3>
          </div>

          <p class="section-desc">测试知识库的检索效果，验证知识融合是否正确</p>

          <div class="query-tips">
            <p><strong>使用方法：</strong>在下方输入框中输入您想查询的问题或关键词，点击检索按钮。系统会从已上传的知识库文档中查找最相关的内容片段并按相关度排序返回。</p>
            <p>提示：查询内容越具体，检索结果越精准。例如输入"勾股定理的证明方法"比"数学"效果更好。</p>
          </div>

          <div class="query-input">
            <el-input
              v-model="queryText"
              placeholder="输入查询内容，例如：Python变量定义"
              size="large"
            >
              <template #append>
                <el-button
                  :icon="Search"
                  @click="executeQuery"
                  :loading="querying"
                  :disabled="!queryText.trim()"
                >
                  检索
                </el-button>
              </template>
            </el-input>
          </div>

          <!-- Query Results -->
          <div class="query-results" v-if="queryResults.length > 0">
            <h4>检索结果 <span class="result-count">共 {{ queryResults.length }} 条</span></h4>
            <div
              v-for="(result, index) in queryResults"
              :key="index"
              class="result-item"
              :class="{ 'low-relevance': result.score < 0.5 }"
            >
              <div class="result-header">
                <span class="result-index">{{ index + 1 }}</span>
                <el-tag v-if="result.score >= 0.8" type="success" size="small">高匹配</el-tag>
                <el-tag v-else-if="result.score >= 0.5" type="warning" size="small">中匹配</el-tag>
                <el-tag v-else type="info" size="small">低匹配</el-tag>
                <el-progress
                  :percentage="Math.round(result.score * 100)"
                  :stroke-width="4"
                  :color="getScoreColor(result.score)"
                  class="result-score"
                />
                <span class="score-value">{{ Math.round(result.score * 100) }}%</span>
              </div>
              <div class="result-content">{{ result.content }}</div>
              <div class="result-meta">
                <el-icon :size="12"><Document /></el-icon>
                来源: {{ result.source || result.metadata?.filename || result.metadata?.source || '未知' }}
              </div>
            </div>
          </div>

          <!-- Empty state -->
          <div class="query-empty" v-else-if="queryResults.length === 0 && queryText.trim() && !querying">
            <p>未找到相关内容。请尝试：</p>
            <ul>
              <li>使用不同的关键词重新检索</li>
              <li>确认知识库中已上传包含相关内容的文档</li>
              <li>使用更具体或更简洁的查询语句</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Education Examples Section -->
      <div class="examples-section">
        <div class="section-card">
          <div class="card-header">
            <h3>
              <el-icon :size="20"><Star /></el-icon>
              教育知识示例
            </h3>
          </div>

          <p class="section-desc">预设的教育领域知识库内容示例</p>

          <div class="examples-grid">
            <div
              v-for="example in educationExamples"
              :key="example.title"
              class="example-item"
              @click="queryText = example.query; executeQuery()"
            >
              <div class="example-icon" :style="{ background: example.gradient }">
                <el-icon :size="20"><component :is="example.icon" /></el-icon>
              </div>
              <div class="example-content">
                <span class="example-title">{{ example.title }}</span>
                <span class="example-query">{{ example.query }}</span>
              </div>
              <el-icon :size="16" class="example-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useAppStore } from '@/store/app'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document, UploadFilled, Upload, Delete, Grid,
  Connection, Folder, Search, Collection, Star,
  Files, ArrowRight, VideoPlay, Connection as ConnIcon,
  Loading, SuccessFilled
} from '@element-plus/icons-vue'

const store = useAppStore()

// State
const fileList = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')
const documents = ref([])
const stats = ref({})
const queryText = ref('')
const queryResults = ref([])
const querying = ref(false)
const loadingDocs = ref(false)

const KB_UI_KEY = 'a04_knowledge_ui_v1'

function restoreKnowledgeCache() {
  try {
    const raw = sessionStorage.getItem(KB_UI_KEY)
    if (!raw) return
    const d = JSON.parse(raw)
    if (d.stats && typeof d.stats === 'object') stats.value = d.stats
    if (Array.isArray(d.documents)) documents.value = d.documents
    if (typeof d.queryText === 'string') queryText.value = d.queryText
    if (Array.isArray(d.queryResults)) queryResults.value = d.queryResults
  } catch { /* ignore */ }
}

function saveKnowledgeCache() {
  try {
    sessionStorage.setItem(KB_UI_KEY, JSON.stringify({
      stats: stats.value,
      documents: documents.value,
      queryText: queryText.value,
      queryResults: queryResults.value
    }))
  } catch { /* ignore */ }
}

watch([stats, documents, queryText, queryResults], saveKnowledgeCache, { deep: true })

// Education Examples
const educationExamples = [
  {
    title: 'Python编程基础',
    query: 'Python中的变量和数据类型有哪些？',
    icon: VideoPlay,
    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  },
  {
    title: '计算机网络',
    query: 'TCP/IP协议栈的层次结构是什么？',
    icon: Connection,
    gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
  },
  {
    title: '数据结构',
    query: '二叉树的遍历方法有哪些？',
    icon: Files,
    gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)'
  },
  {
    title: '机器学习',
    query: '监督学习和无监督学习的区别？',
    icon: Star,
    gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)'
  }
]

// Load data
async function loadData() {
  loadingDocs.value = true
  try {
    const [statsData, docsData] = await Promise.all([
      store.fetchKnowledgeStats(),
      store.fetchKnowledgeDocuments(100)
    ])
    if (statsData) {
      stats.value = statsData
    }
    documents.value = docsData || []
  } catch (e) {
    console.error('加载知识库数据失败:', e)
    ElMessage.error('加载知识库数据失败，请检查后端服务是否启动')
  } finally {
    loadingDocs.value = false
  }
}

// Handle file change
function handleFileChange(file, files) {
  fileList.value = files
}

// Upload files
async function uploadFiles() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  uploadStatus.value = ''
  let successCount = 0
  const totalFiles = fileList.value.length

  try {
    for (let i = 0; i < totalFiles; i++) {
      const file = fileList.value[i]
      const fileName = file.name || file.raw?.name || '未知文件'
      
      // 阶段1: 上传中 (每个文件占总进度的一部分)
      const fileBaseProgress = Math.round((i / totalFiles) * 100)
      const fileStepProgress = Math.round(100 / totalFiles)
      
      uploadProgress.value = fileBaseProgress
      uploadStatus.value = `正在上传并解析 (${i + 1}/${totalFiles}): ${fileName}`
      
      // 模拟上传阶段进度
      const progressTimer = setInterval(() => {
        if (uploadProgress.value < fileBaseProgress + fileStepProgress * 0.9) {
          uploadProgress.value += 1
        }
      }, 300)

      try {
        const uploadRes = await store.uploadFile(file.raw, 'knowledge_base', true)
        clearInterval(progressTimer)
        
        if (uploadRes.success === false) {
          ElMessage.error(`文件 ${fileName} 处理失败: ${uploadRes.message || '未知错误'}`)
          uploadProgress.value = fileBaseProgress + fileStepProgress
          continue
        }
        successCount++
        uploadProgress.value = fileBaseProgress + fileStepProgress
        uploadStatus.value = `已完成 (${successCount}/${totalFiles}): ${fileName}`
      } catch (fileErr) {
        clearInterval(progressTimer)
        const msg = fileErr.response?.data?.detail || fileErr.response?.data?.message || fileErr.message || '未知错误'
        ElMessage.error(`文件 ${fileName} 上传失败: ${msg}`)
        uploadProgress.value = fileBaseProgress + fileStepProgress
      }
    }

    uploadProgress.value = 100
    if (successCount > 0) {
      uploadStatus.value = `全部完成！成功添加 ${successCount}/${totalFiles} 个文件`
      ElMessage.success(`成功添加 ${successCount} 个文件到知识库`)
    } else {
      uploadStatus.value = '所有文件处理失败，请检查文件格式'
    }
    fileList.value = []
    await loadData()
  } catch (e) {
    const msg = e.response?.data?.detail || e.response?.data?.message || e.message || '未知错误'
    ElMessage.error('上传失败: ' + msg)
    uploadStatus.value = '上传出错: ' + msg
  } finally {
    uploading.value = false
    // 3秒后清除进度条
    setTimeout(() => {
      if (!uploading.value) {
        uploadProgress.value = 0
        uploadStatus.value = ''
      }
    }, 3000)
  }
}

// Delete document
async function deleteDocument(docId) {
  try {
    await ElMessageBox.confirm('确定要删除这个文档吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await store.api.delete(`/knowledge/document/${encodeURIComponent(docId)}`)
    if (res.data?.success) {
      ElMessage.success('删除成功')
    } else {
      ElMessage.error('删除失败: ' + (res.data?.message || '未知错误'))
    }
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.message || e.message || ''))
    }
  }
}

// Clear knowledge base
async function clearKnowledgeBase() {
  try {
    await ElMessageBox.confirm(
      '确定要清空整个知识库吗？此操作不可恢复！',
      '危险操作',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'error'
      }
    )

    await store.api.delete('/knowledge/clear')
    ElMessage.success('知识库已清空')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// Execute query
async function executeQuery() {
  if (!queryText.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }

  querying.value = true

  try {
    const res = await store.queryKnowledge(queryText.value)
    queryResults.value = res.results || []
  } catch (e) {
    ElMessage.error('检索失败')
  } finally {
    querying.value = false
  }
}

// Get score color
function getScoreColor(score) {
  if (score > 0.8) return '#00ff88'
  if (score > 0.6) return '#00c8ff'
  if (score > 0.4) return '#ffcc00'
  return '#ff6b6b'
}

onMounted(() => {
  restoreKnowledgeCache()
  loadData()
})

onBeforeUnmount(() => {
  saveKnowledgeCache()
})
</script>

<style lang="scss" scoped>
.knowledge-view {
  height: calc(100vh - 112px);
  overflow-y: auto;
  padding: 24px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 200, 255, 0.3);
    border-radius: 3px;
  }
}

.knowledge-container {
  max-width: 1200px;
  margin: 0 auto;
}

// Page Header
.page-header {
  margin-bottom: 28px;

  .header-info {
    h1 {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      color: transparent;
    }

    .subtitle {
      font-size: 14px;
      color: var(--text-secondary);
    }
  }
}

// Stats Grid
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 24px;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.1);
  border-radius: 16px;
  transition: all 0.3s ease;

  &:hover {
    border-color: rgba(0, 200, 255, 0.3);
    transform: translateY(-2px);
  }

  .stat-icon {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;

    &.documents {
      background: linear-gradient(135deg, #667eea, #764ba2);
    }

    &.chunks {
      background: linear-gradient(135deg, #4facfe, #00f2fe);
    }

    &.status {
      background: linear-gradient(135deg, #f093fb, #f5576c);

      &.active {
        background: linear-gradient(135deg, #43e97b, #38f9d7);
        animation: status-glow 2s ease-in-out infinite;
      }
    }
  }

  @keyframes status-glow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(67, 233, 123, 0.4); }
    50% { box-shadow: 0 0 20px 4px rgba(67, 233, 123, 0.2); }
  }

  .stat-content {
    display: flex;
    flex-direction: column;

    .stat-value {
      font-size: 28px;
      font-weight: 800;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      color: transparent;
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-muted);
    }
  }
}

// Content Grid
.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.section-card {
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s ease;

  &:hover {
    border-color: rgba(0, 200, 255, 0.2);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }
}

// Upload Section
.upload-section {
  .upload-area {
    width: 100%;

    :deep(.el-upload-dragger) {
      width: 100%;
      height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(10, 14, 39, 0.4);
      border: 2px dashed rgba(0, 200, 255, 0.2);
      border-radius: 12px;

      &:hover {
        border-color: var(--primary);
      }
    }
  }

  .upload-content {
    text-align: center;

    .upload-icon {
      color: var(--primary);
      margin-bottom: 12px;
      opacity: 0.7;
    }

    .upload-text {
      font-size: 15px;
      margin-bottom: 12px;
    }

    .upload-formats {
      display: flex;
      gap: 8px;
      justify-content: center;
      margin-bottom: 8px;

      .format-tag {
        padding: 3px 10px;
        font-size: 11px;
        background: rgba(0, 200, 255, 0.1);
        border: 1px solid rgba(0, 200, 255, 0.2);
        border-radius: 6px;
        color: var(--primary);
      }
    }

    .upload-hint {
      font-size: 12px;
      color: var(--text-muted);
    }
  }

  .upload-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 16px;
  }

  .upload-progress {
    margin-top: 16px;
    padding: 12px 16px;
    background: rgba(10, 14, 39, 0.4);
    border-radius: 10px;
    border: 1px solid rgba(0, 200, 255, 0.15);

    :deep(.el-progress-bar__outer) {
      background: rgba(0, 200, 255, 0.1);
    }

    .progress-status {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      font-size: 13px;
      color: var(--text-secondary);
    }
  }
}

.rotating {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

// Documents Section
.documents-section {
  .documents-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 280px;
    overflow-y: auto;
  }

  .document-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(10, 14, 39, 0.4);
    border-radius: 10px;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(0, 200, 255, 0.05);

      .delete-btn {
        opacity: 1;
      }
    }

    .doc-icon {
      width: 40px;
      height: 40px;
      background: rgba(0, 200, 255, 0.1);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--primary);
    }

    .doc-info {
      flex: 1;
      min-width: 0;

      .doc-name {
        display: block;
        font-size: 14px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-bottom: 4px;
      }

      .doc-meta {
        display: flex;
        gap: 12px;

        .meta-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 12px;
          color: var(--text-muted);
        }
      }
    }

    .delete-btn {
      opacity: 0;
      transition: opacity 0.2s;
    }
  }

  .empty-state {
    text-align: center;
    padding: 40px 20px;

    .empty-icon {
      color: var(--text-muted);
      opacity: 0.3;
      margin-bottom: 12px;
    }

    p {
      font-size: 15px;
      color: var(--text-secondary);
      margin-bottom: 4px;
    }

    span {
      font-size: 13px;
      color: var(--text-muted);
    }
  }
}

// Query Section
.query-section {
  margin-bottom: 24px;

  .section-desc {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 16px;
  }

  .query-tips {
    background: rgba(0, 200, 255, 0.05);
    border: 1px solid rgba(0, 200, 255, 0.15);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
    p {
      font-size: 13px;
      line-height: 1.6;
      color: var(--text-muted);
      margin: 0 0 6px;
      &:last-child { margin-bottom: 0; }
      strong { color: var(--text-secondary); }
    }
  }

  .query-empty {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    p { font-size: 14px; margin-bottom: 12px; }
    ul {
      list-style: none;
      padding: 0;
      li {
        font-size: 13px;
        padding: 4px 0;
        &::before { content: '•  '; color: var(--primary); }
      }
    }
  }

  .query-input {
    margin-bottom: 20px;

    :deep(.el-input__wrapper) {
      background: rgba(10, 14, 39, 0.6);
      border-radius: 10px 0 0 10px;
    }
  }

  .query-results {
    h4 {
      font-size: 14px;
      color: var(--text-secondary);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;

      .result-count {
        font-size: 12px;
        color: var(--text-muted);
        font-weight: normal;
      }
    }
  }

  .result-item {
    padding: 16px;
    background: rgba(10, 14, 39, 0.4);
    border-radius: 12px;
    margin-bottom: 12px;

    &.low-relevance {
      opacity: 0.6;
      border-left: 3px solid rgba(255, 107, 107, 0.4);
    }

    .result-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;

      .result-index {
        width: 20px;
        height: 20px;
        background: rgba(0, 200, 255, 0.2);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 600;
        color: var(--primary);
      }

      .result-score {
        flex: 1;
      }

      .score-value {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        min-width: 40px;
        text-align: right;
      }
    }

    .result-content {
      font-size: 14px;
      line-height: 1.7;
      margin-bottom: 8px;
      max-height: 80px;
      overflow: hidden;
    }

    .result-meta {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      color: var(--text-muted);
    }
  }
}

// Examples Section
.examples-section {
  .examples-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;

    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
  }

  .example-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    background: rgba(10, 14, 39, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(0, 200, 255, 0.05);
      border-color: rgba(0, 200, 255, 0.2);
      transform: translateX(4px);

      .example-arrow {
        opacity: 1;
        transform: translateX(0);
      }
    }

    .example-icon {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      flex-shrink: 0;
    }

    .example-content {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;

      .example-title {
        font-size: 14px;
        font-weight: 600;
      }

      .example-query {
        font-size: 12px;
        color: var(--text-muted);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .example-arrow {
      color: var(--primary);
      opacity: 0;
      transform: translateX(-8px);
      transition: all 0.2s ease;
    }
  }
}
</style>
