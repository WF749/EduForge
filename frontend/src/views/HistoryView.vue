<template>
  <div class="history-view">
    <div class="history-container">
      <div class="page-header">
        <h2 class="page-title title-gradient">历史记录</h2>
        <p class="page-subtitle">查看、下载和管理所有生成过的课件、教案、动画和游戏文件</p>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar glass-card">
        <el-select v-model="filterType" placeholder="全部类型" clearable size="large" style="width: 140px">
          <el-option label="全部" value="" />
          <el-option label="课件" value="课件" />
          <el-option label="游戏" value="游戏" />
          <el-option label="动画" value="动画" />
          <el-option label="教案" value="教案" />
        </el-select>
        <el-input v-model="searchText" placeholder="搜索文件名..." clearable size="large" style="flex:1; max-width:300px" :prefix-icon="Search" />
        <el-button type="primary" :icon="Refresh" @click="loadFiles" :loading="loading" size="large">刷新</el-button>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading-state glass-card">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <!-- 空状态 -->
      <div v-else-if="filteredFiles.length === 0" class="empty-state glass-card">
        <el-icon :size="48"><Document /></el-icon>
        <p>暂无生成记录</p>
        <el-button type="primary" @click="$router.push('/courseware')">去生成课件</el-button>
      </div>

      <!-- 文件列表 -->
      <div v-else class="files-grid">
        <div v-for="group in filteredFiles" :key="group.path" class="file-card glass-card">
          <div class="card-header">
            <div class="card-title-row">
              <el-tag :type="getTagType(group.label || '课件')" size="small">{{ group.label || '课件' }}</el-tag>
              <span class="card-name">{{ formatDirName(group.dir) }}</span>
            </div>
            <el-button type="danger" text size="small" @click="deleteGroup(group)" :icon="Delete">删除</el-button>
          </div>

          <div class="card-files">
            <div v-for="file in group.files" :key="file.name" class="file-item">
              <el-icon :size="16"><component :is="getFileIcon(file.type)" /></el-icon>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatSize(file.size) }}</span>
              <div class="file-actions">
                <el-button v-if="file.type === 'html'" text size="small" type="primary" @click="previewFile(group, file)">
                  <el-icon><View /></el-icon>
                </el-button>
                <el-button text size="small" type="success" @click="downloadFile(group, file)">
                  <el-icon><Download /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Delete, Document, View, Download, Loading } from '@element-plus/icons-vue'

const loading = ref(false)
const fileGroups = ref([])
const filterType = ref('')
const searchText = ref('')

const filteredFiles = computed(() => {
  const q = (searchText.value || '').toLowerCase()
  return fileGroups.value.filter(g => {
    if (filterType.value && g.label !== filterType.value) return false
    if (q) {
      const inDir = g.dir.toLowerCase().includes(q)
      const inFile = (g.files || []).some(f => f.name.toLowerCase().includes(q))
      if (!inDir && !inFile) return false
    }
    return true
  })
})

function getTagType(label) {
  if (label === '课件') return 'primary'
  if (label === '游戏') return 'success'
  if (label === '动画') return 'warning'
  if (label === '教案') return 'danger'
  return 'info'
}

function getFileIcon(type) {
  if (type === 'pptx') return Document
  if (type === 'docx') return Document
  if (type === 'html') return View
  return Document
}

function formatDirName(dir) {
  // 截取时间戳前的主题名, e.g. "Python_20240101_abc123" -> "Python"
  const parts = dir.split('_')
  if (parts.length >= 3) {
    return parts.slice(0, -2).join('_')
  }
  return dir
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function loadFiles() {
  loading.value = true
  try {
    const resp = await fetch(resolveApiBaseURL() + '/courseware/files')
    const data = await resp.json()
    if (data.success) {
      fileGroups.value = data.files || []
    }
  } catch (e) {
    ElMessage.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

function downloadFile(group, file) {
  const url = resolveApiBaseURL() + `/courseware/download/` + file.type +
    '?task_dir=' + encodeURIComponent(group.path) +
    '&topic=' + encodeURIComponent(formatDirName(group.dir))
  window.open(url, '_blank')
}

function previewFile(group, file) {
  const filePath = `${group.path}/${file.name}`.replace(/\/+/g, '/').replace(/^\//, '')
  const api = resolveApiBaseURL()
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const base = api.startsWith('http') ? api.replace(/\/?api\/?$/, '') : origin
  const url = `${base.replace(/\/$/, '')}/${filePath}`.replace(/([^:]\/)\/+/g, '$1')
  window.open(url, '_blank')
}

async function deleteGroup(group) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${formatDirName(group.dir)}" 及其所有文件吗？此操作不可撤销。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const resp = await fetch(resolveApiBaseURL() + '/courseware/files/' + encodeURIComponent(group.dir), {
      method: 'DELETE'
    })
    const data = await resp.json()
    if (data.success) {
      ElMessage.success('删除成功')
      loadFiles()
    } else {
      ElMessage.error(data.detail || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadFiles()
})
</script>

<style lang="scss" scoped>
.history-view {
  padding: 24px;
  min-height: 100vh;
}

.history-container {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
  .page-title {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .page-subtitle {
    color: var(--text-muted);
    font-size: 14px;
  }
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  margin-bottom: 20px;
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 20px;
  color: var(--text-muted);
  font-size: 16px;
}

.files-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.file-card {
  padding: 20px;
  border-radius: 12px;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 200, 255, 0.1);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;

    .card-title-row {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .card-name {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }

  .card-files {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .file-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(0, 200, 255, 0.03);
    border: 1px solid rgba(0, 200, 255, 0.06);

    .file-name {
      flex: 1;
      font-size: 13px;
      color: var(--text-secondary);
    }
    .file-size {
      font-size: 12px;
      color: var(--text-muted);
      margin-right: 8px;
    }
    .file-actions {
      display: flex;
      gap: 2px;
    }
  }
}
</style>
