<template>
  <div class="artifact-card" :class="[`grad-${meta.grad}`, `is-${artifact.status}`]">
    <div class="ac-icon">
      <el-icon :size="26"><component :is="meta.icon" /></el-icon>
    </div>

    <div class="ac-main">
      <div class="ac-title-row">
        <span class="ac-name">{{ meta.name }}</span>
        <el-tag v-if="artifact.status === 'done'" type="success" size="small" effect="dark">已完成</el-tag>
        <el-tag v-else-if="artifact.status === 'running'" type="primary" size="small" effect="dark">生成中</el-tag>
        <el-tag v-else-if="artifact.status === 'failed'" type="danger" size="small" effect="dark">失败</el-tag>
        <el-tag v-else type="info" size="small" effect="plain">未生成</el-tag>
        <span v-if="artifact.summary" class="ac-summary">{{ artifact.summary }}</span>
      </div>

      <div class="ac-meta">
        <span v-if="artifact.at && artifact.status !== 'idle'">
          {{ new Date(artifact.at).toLocaleString('zh-CN', { hour12: false }) }}
        </span>
        <span v-else>填写课程信息后即可生成</span>
      </div>

      <el-alert
        v-if="artifact.error"
        class="ac-error"
        type="error"
        :closable="false"
        show-icon
        :title="artifact.error"
      />

      <!-- 出厂质检：只报告不阻断，四类产物一视同仁 -->
      <ComplianceReport
        v-if="artifact.compliance"
        :report="artifact.compliance"
        :label="meta.name"
      />

      <!-- 离线可用性：现在不说，等拷到教室电脑才发现打不开就晚了 -->
      <el-alert
        v-if="needsNetwork"
        class="ac-offline"
        type="warning"
        :closable="false"
        show-icon
        :title="artifact.offline.message"
      >
        <ul class="ac-offline-refs">
          <li v-for="r in artifact.offline.refs.slice(0, 3)" :key="r.url">
            {{ r.kind }} · {{ r.url }}
          </li>
        </ul>
      </el-alert>
    </div>

    <div class="ac-actions">
      <el-button
        v-if="artifact.status === 'done' && artifact.downloadUrl"
        type="primary"
        size="small"
        :icon="Download"
        @click="openUrl(artifact.downloadUrl)"
      >下载</el-button>

      <el-button
        v-if="artifact.status === 'done' && artifact.previewUrl"
        size="small"
        :icon="View"
        :loading="previewing"
        @click="openPreview"
      >预览</el-button>

      <el-button
        v-if="artifact.status === 'done' && artifact.previewRoute"
        size="small"
        :icon="EditPen"
        @click="router.push(artifact.previewRoute)"
      >打开编辑</el-button>

      <el-button
        size="small"
        :icon="RefreshRight"
        :loading="artifact.status === 'running'"
        :disabled="!canGenerate"
        @click="emit('generate')"
      >{{ artifact.status === 'done' ? '重新生成' : '生成' }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download, View, RefreshRight, EditPen } from '@element-plus/icons-vue'
import { trackedFetch } from '@/api/dataFlow'
import ComplianceReport from '@/components/ComplianceReport.vue'
import { ARTIFACTS } from '@/store/lesson'

const props = defineProps({
  typeId: { type: String, required: true },
  artifact: { type: Object, required: true },
  canGenerate: { type: Boolean, default: true }
})
const emit = defineEmits(['generate'])

const router = useRouter()
const previewing = ref(false)

const meta = computed(
  () => ARTIFACTS.find(a => a.id === props.typeId) || { name: props.typeId, icon: 'Document', grad: 'files' }
)

// 只在"确实扫出外链"时才提示。没扫过（checked=false）时不吭声 ——
// 一个说不清的检查结果比没有更吵，而且会让人以为产物有问题。
const needsNetwork = computed(
  () => Boolean(props.artifact.offline?.checked && props.artifact.offline.offline_ready === false)
)

function openUrl(url) {
  if (!url) {
    ElMessage.warning('该文件暂时没有可用地址，请重新生成')
    return
  }
  window.open(url, '_blank')
}

/**
 * 预览 HTML 产物（动画 / 游戏）。
 *
 * 不能直接用 window.open 打开下载地址：后端的 download 接口带
 * `Content-Disposition: attachment`，新标签只会触发下载，看起来像"点了预览没反应"。
 * 所以这里先把内容取回来，用 Blob URL 打开，才是真正的预览。
 */
async function openPreview() {
  const url = props.artifact.previewUrl
  if (!url) {
    ElMessage.warning('该产物暂时没有可用地址，请重新生成')
    return
  }
  previewing.value = true
  try {
    const res = await trackedFetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const html = await res.text()
    const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
    window.open(blobUrl, '_blank')
    // 留给浏览器加载完再回收，立刻 revoke 会白屏
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
  } catch (e) {
    ElMessage.error('预览失败：' + (e?.message || '无法读取文件'))
  } finally {
    previewing.value = false
  }
}
</script>

<style lang="scss" scoped>
.artifact-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 18px;
  background: rgba(10, 14, 39, 0.72);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 14px;
  transition: all 0.25s ease;

  &:hover {
    border-color: rgba(0, 200, 255, 0.4);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
  }

  &.is-failed { border-color: rgba(255, 107, 107, 0.45); }
  &.is-running { border-color: rgba(0, 200, 255, 0.5); }
}

.ac-icon {
  flex: 0 0 48px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #fff;

  .grad-files & { background: linear-gradient(135deg, #00c8ff, #0099cc); }
  .grad-ppt & { background: linear-gradient(135deg, #ff6b6b, #ee5a5a); }
  .grad-anim & { background: linear-gradient(135deg, #7c3aed, #6d28d9); }
  .grad-game & { background: linear-gradient(135deg, #00ff88, #00cc6a); color: #06281a; }
}

.ac-main {
  flex: 1;
  min-width: 0;
}

.ac-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;

  .ac-name {
    font-size: 16px;
    font-weight: 600;
    color: #fff;
  }

  .ac-summary {
    font-size: 12px;
    color: rgba(0, 200, 255, 0.85);
  }
}

.ac-meta {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.ac-error {
  margin-top: 10px;
}

.ac-offline {
  margin-top: 10px;
}

.ac-offline-refs {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-all;
}

.ac-actions {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 240px;
}

@media (max-width: 860px) {
  .artifact-card { flex-wrap: wrap; }
  .ac-actions { max-width: none; width: 100%; justify-content: flex-end; }
}
</style>
