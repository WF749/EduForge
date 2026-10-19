<template>
  <article class="art" :aria-label="`${meta.name}产物卡片`">
    <header class="art__head">
      <div class="art__title">
        <span class="art__icon" aria-hidden="true">
          <el-icon :size="16"><component :is="meta.icon" /></el-icon>
        </span>
        <b>{{ meta.name }}</b>
        <StatusTag :status="art.status" />
      </div>
      <span v-if="art.summary" class="art__summary">{{ art.summary }}</span>
    </header>

    <!-- 进度：PPT 有真实进度与步骤名，其余只有"生成中" -->
    <div v-if="art.status === 'running'" class="art__progress">
      <el-progress
        v-if="kind === 'ppt'"
        :percentage="progress"
        :stroke-width="6"
        :show-text="false"
      />
      <el-progress v-else :percentage="100" :stroke-width="6" :show-text="false" indeterminate />
      <span class="art__step">{{ stepHint || '正在生成…' }}</span>
    </div>

    <!-- 失败：错误原文照显示，不替后端圆场 -->
    <p v-else-if="art.status === 'failed'" class="art__error" role="alert">{{ art.error }}</p>

    <!-- 离线可用性提醒：动画/游戏拷到没网的教室打不开就晚了 -->
    <p v-if="offlineWarn" class="art__warn">
      <el-icon><WarningFilled /></el-icon>
      {{ offlineWarn }}
    </p>

    <ComplianceCard v-if="art.compliance" :report="art.compliance" compact />

    <footer class="art__foot">
      <el-button
        v-if="art.status !== 'done'"
        type="primary"
        size="small"
        :loading="art.status === 'running'"
        :disabled="!canGenerate"
        @click="$emit('generate', kind)"
      >
        {{ art.status === 'failed' ? '重新生成' : '生成' }}
      </el-button>

      <template v-if="art.status === 'done'">
        <el-button size="small" :loading="downloading" @click="onDownload">
          <el-icon><Download /></el-icon>
          下载
        </el-button>
        <el-button v-if="canPreview" size="small" :loading="previewing" @click="onPreview">
          <el-icon><View /></el-icon>
          预览
        </el-button>
        <el-button size="small" text @click="$emit('generate', kind)">
          <el-icon><RefreshRight /></el-icon>
          重新生成
        </el-button>
      </template>

    </footer>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Download, RefreshRight, View, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ARTIFACTS, useLessonStore } from '@/store/lesson'
import { trackedFetch } from '@/api/dataFlow'
import StatusTag from '@/components/common/StatusTag.vue'
import ComplianceCard from '@/components/workbench/ComplianceCard.vue'

/**
 * 单个产物卡片。
 *
 * 两个历史坑在这里被钉住：
 *  1. **预览不能用 window.open**。下载接口带 `Content-Disposition: attachment`，
 *     直接开只会下载一个文件，教师点"预览"却得到下载，会以为功能坏了。
 *     所以预览一律先取成 Blob 再开本地 URL。
 *  2. **失败文案原样显示**。早年把错误吞成"生成失败，请重试"，
 *     教师无从判断是模型挂了还是自己没填全。
 */
const props = defineProps({
  kind: { type: String, required: true },
  progress: { type: Number, default: 0 },
  stepHint: { type: String, default: '' }
})

defineEmits(['generate'])

const store = useLessonStore()
const downloading = ref(false)
const previewing = ref(false)

const meta = computed(() => ARTIFACTS.find(a => a.id === props.kind) || ARTIFACTS[0])
const art = computed(() => store.artifacts[props.kind] || {})
const canGenerate = computed(() => !!store.topic.trim())

// HTML 类产物（动画 / 游戏）才谈得上"预览"；PPT/教案只能下载或跳转预览页
const canPreview = computed(() => ['animation', 'game'].includes(props.kind) && !!art.value.downloadUrl)

const offlineWarn = computed(() => {
  const off = art.value.offline
  if (!off || off.ok !== false) return ''
  const n = Array.isArray(off.findings) ? off.findings.length : 0
  return n ? `离线检查：有 ${n} 处外部依赖，拷到没网的教室可能打不开` : ''
})

/** 所有下载都走 fetch → Blob：既能带上数据流向观测，也能在失败时给出可读提示 */
async function fetchBlob(url) {
  const res = await trackedFetch(url)
  if (!res.ok) throw new Error(`下载失败（HTTP ${res.status}）`)
  return await res.blob()
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `${store.topic || '产物'}.${meta.value.ext}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 立刻回收会让部分浏览器来不及触发下载
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

async function onDownload() {
  if (downloading.value) return
  downloading.value = true
  try {
    const blob = await fetchBlob(art.value.downloadUrl)
    saveBlob(blob)
  } catch (e) {
    ElMessage.error(e?.message || '下载失败')
  } finally {
    downloading.value = false
  }
}

async function onPreview() {
  if (previewing.value) return
  previewing.value = true
  try {
    const blob = await fetchBlob(art.value.previewUrl || art.value.downloadUrl)
    const url = URL.createObjectURL(new Blob([blob], { type: 'text/html;charset=utf-8' }))
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (e) {
    ElMessage.error(e?.message || '预览失败')
  } finally {
    previewing.value = false
  }
}
</script>

<style scoped>
.art {
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-md);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.art__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.art__title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-base);
}

.art__icon {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--wb-surface-2);
  color: var(--wb-text-2);
}

.art__summary {
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
}

.art__progress { display: flex; flex-direction: column; gap: 4px; }

.art__step {
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
}

.art__error {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--wb-risk-text);
  background: var(--danger-bg);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  line-height: 1.6;
}

.art__warn {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-xs);
  color: var(--wb-warn-text);
  background: var(--wb-warn-bg);
  border-radius: var(--radius-sm);
  padding: 6px var(--sp-2);
}

.art__foot {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-top: auto;
}

</style>
