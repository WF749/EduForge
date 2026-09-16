<template>
  <div class="ctx-bar">
    <div class="ctx-row ctx-row-main">
      <el-select
        v-model="switchTo"
        class="ctx-switch"
        size="large"
        filterable
        placeholder="最近课程"
        @change="onSwitch"
      >
        <el-option
          v-for="t in store.recentTasks"
          :key="t.id"
          :label="t.topic || '（未命名课程）'"
          :value="t.id"
        >
          <span class="sw-topic">{{ t.topic || '（未命名课程）' }}</span>
          <span class="sw-meta">{{ t.subject }} · {{ t.grade }} · {{ t.artifactCount }}/4</span>
        </el-option>
      </el-select>

      <el-input
        v-model="store.topic"
        class="ctx-topic"
        size="large"
        placeholder="这节课的教学主题，例如：一次函数的图像与性质"
        :prefix-icon="EditPen"
      />

      <el-select v-model="store.subject" size="large" filterable allow-create class="ctx-field">
        <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
      </el-select>

      <el-select v-model="store.grade" size="large" class="ctx-field">
        <el-option v-for="g in GRADES" :key="g" :label="g" :value="g" />
      </el-select>

      <div class="ctx-duration">
        <span class="ctx-label">课时</span>
        <el-input-number v-model="store.duration" :min="15" :max="180" :step="5" size="large" controls-position="right" />
        <span class="ctx-unit">分钟</span>
      </div>

      <el-select v-model="store.difficulty" size="large" class="ctx-diff">
        <el-option v-for="d in DIFFICULTIES" :key="d.value" :label="d.label" :value="d.value" />
      </el-select>

      <el-button size="large" :icon="RefreshLeft" @click="confirmReset">换一节课</el-button>
      <el-button
        v-if="store.taskId"
        size="large"
        :icon="FolderChecked"
        title="归档后从最近课程列表移除，产物链接仍可下载"
        @click="confirmArchive"
      >归档本课</el-button>
    </div>

    <div class="ctx-row ctx-row-sub">
      <el-input
        v-model="store.keyPoints"
        type="textarea"
        :rows="1"
        autosize
        placeholder="补充要求 / 教学要点（可空）。会随这节课一起传给教案、PPT、动画、游戏四类生成"
      />

      <el-upload
        class="ctx-upload"
        :action="uploadAction"
        :multiple="true"
        :limit="5"
        :show-file-list="false"
        accept=".pdf,.doc,.docx,.pptx,.txt"
        :on-success="onUploaded"
        :on-error="onUploadError"
      >
        <el-button size="default" :icon="UploadFilled">参考资料</el-button>
      </el-upload>
    </div>

    <div v-if="store.referenceFiles.length" class="ctx-refs">
      <el-tag
        v-for="f in store.referenceFiles"
        :key="f.file_id"
        closable
        size="small"
        type="info"
        @close="store.removeReference(f.file_id)"
      >
        <el-icon><Document /></el-icon>
        {{ f.name }}
      </el-tag>
      <span class="ctx-refs-hint">已选 {{ store.referenceFiles.length }} 份，生成时会被读取正文</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, RefreshLeft, UploadFilled, Document, FolderChecked } from '@element-plus/icons-vue'
import { useLessonStore, SUBJECTS, GRADES, DIFFICULTIES } from '@/store/lesson'
import { resolveApiBaseURL } from '@/api/baseUrl'

const store = useLessonStore()
const uploadAction = computed(() => `${resolveApiBaseURL()}/upload/file`)

function onUploaded(response) {
  if (!response?.success) {
    ElMessage.error('上传失败：' + (response?.message || '未知错误'))
    return
  }
  store.addReference({ file_id: response.file_id, name: response.filename || response.file_id })
  ElMessage.success('已加入本节课的参考资料')
}

function onUploadError() {
  ElMessage.error('上传失败：网络错误')
}

// 切换器只作"动作入口"：选完立刻清空，避免它显示成一个常驻的下拉框，
// 让人误以为当前课程是"下拉里选中的那一项"。当前课始终由顶部主题输入框表示。
const switchTo = ref('')

async function onSwitch(id) {
  switchTo.value = ''
  if (!id || id === store.taskId) return
  const ok = await store.switchTask(id)
  if (ok) ElMessage.success('已切换到该课程')
  else ElMessage.error('切换失败：读不到这节课的记录')
}

async function confirmArchive() {
  try {
    await ElMessageBox.confirm(
      '归档后这节课会从「最近课程」移除，已生成的文件仍可在「历史作品」下载。归档后会清空工作台，方便开始下一节。',
      '归档当前课程？',
      { type: 'warning', confirmButtonText: '归档并新建', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  const ok = await store.setArchived(true)
  if (ok) ElMessage.success('已归档，工作台已清空')
  else ElMessage.error('归档失败，请稍后重试')
}

onMounted(() => { store.loadRecent() })

async function confirmReset() {
  const hasWork = store.doneCount > 0
  if (hasWork) {
    try {
      await ElMessageBox.confirm(
        '换一节课会清空当前主题、参考资料和四类产物的记录（已下载过的文件不受影响）。',
        '确认换一节课？',
        { type: 'warning', confirmButtonText: '换一节课', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  store.resetLesson()
}
</script>

<style lang="scss" scoped>
.ctx-bar {
  background: rgba(10, 14, 39, 0.82);
  border: 1px solid rgba(0, 200, 255, 0.18);
  border-radius: 16px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ctx-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ctx-row-main {
  .ctx-topic { flex: 1 1 320px; min-width: 240px; }
  .ctx-field { width: 130px; }
  .ctx-diff { width: 130px; }
  .ctx-switch { width: 150px; }
}

.sw-meta {
  float: right;
  margin-left: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.ctx-duration {
  display: flex;
  align-items: center;
  gap: 6px;

  .ctx-label, .ctx-unit {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.55);
    white-space: nowrap;
  }
}

.ctx-row-sub {
  :deep(.el-textarea) { flex: 1 1 360px; min-width: 240px; }
}

.ctx-upload {
  flex: 0 0 auto;
}

.ctx-refs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;

  .ctx-refs-hint {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.35);
  }
}

@media (max-width: 720px) {
  .ctx-row-main {
    .ctx-topic, .ctx-field, .ctx-diff { flex: 1 1 100%; width: 100%; }
  }
}
</style>
