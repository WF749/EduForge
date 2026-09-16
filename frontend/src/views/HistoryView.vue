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

      <!-- 文件列表：按"属于哪一节课"归组 -->
      <div v-else class="lesson-groups">
        <section v-for="bucket in groupedByLesson" :key="bucket.key" class="lesson-bucket glass-card">
          <header class="lb-head">
            <div class="lb-title">
              <el-icon :size="18"><Collection /></el-icon>
              <span v-if="bucket.lesson" class="lb-name">{{ bucket.lesson.topic || '（未命名课程）' }}</span>
              <span v-else class="lb-name muted">未归档到课程</span>
              <el-tag size="small" type="info" effect="plain">{{ bucket.groups.length }} 项</el-tag>
            </div>
            <el-button
              v-if="bucket.lesson"
              size="small"
              type="primary"
              text
              @click="openLesson(bucket.lesson.id)"
            >在工作台打开</el-button>
          </header>

          <div class="files-grid">
            <div v-for="group in bucket.groups" :key="`${group.label}:${group.dir}`" class="file-card">
              <div class="card-header">
                <div class="card-title-row">
                  <el-tag :type="getTagType(group.label || '课件')" size="small">{{ group.label || '课件' }}</el-tag>
                  <span class="card-name">{{ formatDirName(group.dir) }}</span>
                </div>
                <el-button v-if="group.delete_url" type="danger" text size="small" @click="deleteGroup(group)" :icon="Delete">删除</el-button>
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
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Delete, Document, View, Download, Loading, Collection } from '@element-plus/icons-vue'

const router = useRouter()

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

/**
 * 按"属于哪一节课"归组。
 *
 * lesson 由后端用台账反查得到（产物目录名/文件名 → 课程）。没有归属的
 * （比如老页面生成的、或台账被清过）放进"未归档到课程"，不要悄悄丢掉。
 */
const groupedByLesson = computed(() => {
  const buckets = new Map()
  for (const group of filteredFiles.value) {
    const lesson = group.lesson && group.lesson.id ? group.lesson : null
    const key = lesson ? lesson.id : '__none__'
    if (!buckets.has(key)) buckets.set(key, { key, lesson, groups: [] })
    buckets.get(key).groups.push(group)
  }
  // 有归属的排在前面，没归属的沉到最后
  return [...buckets.values()].sort((a, b) => {
    if (!a.lesson && b.lesson) return 1
    if (a.lesson && !b.lesson) return -1
    return 0
  })
})

/** 跳回工作台并打开这节课（工作台会按 taskId 从台账恢复） */
function openLesson(lessonId) {
  router.push({ path: '/', query: { lesson: lessonId } })
}

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
    const resp = await trackedFetch(resolveApiBaseURL() + '/courseware/files')
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
  if (!file.download_url) return ElMessage.warning('该文件没有可用的下载地址')
  window.open(file.download_url, '_blank')
}

function previewFile(group, file) {
  if (!file.preview_url) return ElMessage.warning('该文件不支持在线预览')
  window.open(file.preview_url, '_blank')
}

async function deleteGroup(group) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${formatDirName(group.dir)}" 及其所有文件吗？此操作不可撤销。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const resp = await trackedFetch(group.delete_url, {
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

.lesson-groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.lesson-bucket {
  padding: 18px 20px 20px;
}

.lb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  margin-bottom: 14px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.12);

  .lb-title {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .lb-name {
    font-size: 16px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lb-name.muted {
    color: rgba(255, 255, 255, 0.4);
    font-weight: 400;
  }
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
