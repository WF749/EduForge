<template>
  <div class="wb-page">
    <PageHeader
      title="知识库"
      description="内置教学法与学科资料，加上你自己上传的课件。生成时可以选择用哪一部分。"
    >
      <template #actions>
        <!-- 不占一级导航的次级入口：查着资料顺手想出一份成品时从这里进 -->
        <el-dropdown trigger="click" @command="onQuickMake">
          <el-button :icon="MagicStick">
            快速制作
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="lesson-plan">教案</el-dropdown-item>
              <el-dropdown-item command="courseware">课件（六阶段）</el-dropdown-item>
              <el-dropdown-item command="ppt">PPT 课件</el-dropdown-item>
              <el-dropdown-item command="animation">动画演示</el-dropdown-item>
              <el-dropdown-item command="game">互动游戏</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button :icon="Refresh" :loading="loadingStatus" @click="loadStatus">刷新状态</el-button>
      </template>
    </PageHeader>

    <!-- 状态条：降级必须说清，否则教师会以为系统坏了 -->
    <div class="wb-card wb-card-pad status">
      <div class="status__item">
        <span class="wb-muted">索引状态</span>
        <StatusTag :status="statusOk ? 'done' : 'degraded'" :label="statusOk ? '正常' : '需要重建'" />
      </div>
      <div class="status__item">
        <span class="wb-muted">文档片段</span>
        <b>{{ status.chunks ?? status.count ?? '—' }}</b>
      </div>
      <div v-for="(v, k) in statusFlags" :key="k" class="status__item">
        <span class="wb-muted">{{ k }}</span>
        <b>{{ v === true ? '可用' : v === false ? '不可用' : v }}</b>
      </div>
      <p v-if="statusError" class="status__error">{{ statusError }}</p>
    </div>

    <el-tabs v-model="tab">
      <!-- 检索测试 -->
      <el-tab-pane label="检索测试" name="search">
        <div class="wb-card wb-card-pad wb-stack">
          <p class="wb-card-hint">
            生成时用的就是这条检索。查不到说明知识库里没有相关内容 ——
            系统会明确说"没有"，而不是让模型编一段。
          </p>
          <el-input
            v-model="query"
            type="textarea"
            :rows="2"
            placeholder="输入一个教学问题，例如：初中物理浮力常见的学生误区有哪些"
          />
          <div class="wb-row">
            <el-button type="primary" :loading="searching" :disabled="!query.trim()" @click="onSearch">
              检索
            </el-button>
            <el-checkbox v-model="rerank">启用重排序（更准，稍慢）</el-checkbox>
            <el-input-number v-model="topK" :min="1" :max="20" size="small" aria-label="返回条数" />
          </div>

          <StateBlock :error="searchError" :retryable="false">
            <div v-if="searchResult" class="wb-stack-sm">
              <div v-if="searchResult.refused" class="note note--warn">
                知识库判定：没有找到相关内容。生成时不会把任何片段塞进上下文。
              </div>
              <EmptyState
                v-else-if="!hits.length"
                title="没有命中"
                description="换个说法试试，或者到「我的资料」里上传相关文档。"
                icon="Search"
              />
              <ul v-else class="hits">
                <li v-for="(h, i) in hits" :key="i" class="hit">
                  <div class="hit__head">
                    <b>{{ h.source || '资料' }}</b>
                    <span v-if="h.heading_path" class="wb-muted">{{ h.heading_path }}</span>
                    <span v-if="h.score != null" class="hit__score">{{ Number(h.score).toFixed(3) }}</span>
                  </div>
                  <p class="hit__text">{{ h.content || h.text || '' }}</p>
                </li>
              </ul>
            </div>
          </StateBlock>
        </div>
      </el-tab-pane>

      <!-- 我的资料 -->
      <el-tab-pane label="我的资料" name="files">
        <div class="wb-card wb-card-pad wb-stack">
          <div class="wb-row">
            <el-upload
              :show-file-list="false"
              :http-request="onUpload"
              accept=".pdf,.doc,.docx,.txt,.md,.pptx"
            >
              <el-button type="primary" :icon="Upload">上传资料</el-button>
            </el-upload>
            <el-checkbox v-model="addToKnowledge">上传后直接入库</el-checkbox>
            <span class="wb-muted" style="font-size: var(--fs-xs)">
              支持 PDF / Word / PPT / 文本；扫描版 PDF 提取不出文字，会当场提示。
            </span>
          </div>

          <StateBlock
            :loading="loadingFiles"
            hint="正在读取资料列表…"
            :error="fileError"
            :empty="!files.length"
            empty-title="还没有上传资料"
            empty-description="上传课件、教材或习题，生成时会把它们作为依据之一。"
            @retry="loadFiles"
          >
            <ul class="files">
              <li v-for="file in files" :key="file.file_id" class="file">
                <span class="file__name wb-truncate">{{ file.filename }}</span>
                <span class="file__size">{{ formatSize(file.size) }}</span>
                <span class="file__ops">
                  <el-button size="small" text @click="onProcess(file)">检查可否提取</el-button>
                  <el-button size="small" text @click="onAddToKnowledge(file)">入库</el-button>
                </span>
              </li>
            </ul>
          </StateBlock>
        </div>

        <!-- 索引里的文档 -->
        <div class="wb-card wb-card-pad wb-stack lp">
          <div class="wb-row wb-row-between">
            <b>已入库的文档</b>
            <el-button size="small" :icon="Refresh" :loading="loadingDocs" @click="loadDocs">
              刷新
            </el-button>
          </div>
          <StateBlock
            :loading="loadingDocs"
            hint="正在读取已入库文档…"
            :error="docError"
            :empty="!docs.length"
            empty-title="还没有文档"
            empty-description="上传资料并选择入库，或者直接重建内置索引。"
            @retry="loadDocs"
          >
            <ul class="files">
              <li v-for="d in docs" :key="d.document_id || d.id" class="file">
                <span class="file__name wb-truncate">{{ d.document_id || d.id || d.name }}</span>
                <span class="file__size">{{ d.chunks ?? d.count ?? '' }}</span>
                <span class="file__ops">
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click="onDeleteDoc(d)"
                  >
                    删除
                  </el-button>
                </span>
              </li>
            </ul>
          </StateBlock>
        </div>
      </el-tab-pane>

      <!-- 索引与维护 -->
      <el-tab-pane label="索引与维护" name="index">
        <div class="wb-card wb-card-pad wb-stack">
          <div>
            <b>重建内置知识库索引</b>
            <p class="wb-card-hint">
              只重建仓库里 <code>knowledge_base/</code> 下的内置文档，
              <b>不会影响你上传的资料</b>。内置文档有增删或改动时用一次。
            </p>
          </div>
          <el-button :loading="reindexing" @click="onReindex">开始重建</el-button>
          <pre v-if="reindexResult" class="dump">{{ reindexResult }}</pre>
        </div>

        <div class="wb-card wb-card-pad wb-stack lp">
          <div>
            <b class="danger-text">清空轻量知识库</b>
            <p class="wb-card-hint">
              只清 <code>/knowledge/*</code> 这一套早期分块存储，
              <b>不会影响</b>内置索引与上面那份文档列表。清之前先确认你不再需要它们。
            </p>
          </div>
          <div class="wb-row">
            <span class="wb-muted">当前片段数：{{ lightweightCount }}</span>
            <el-button type="danger" plain :loading="clearing" @click="onClear">
              清空轻量知识库
            </el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, MagicStick, Refresh, Search, Upload } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  fetchRagStatus, searchKnowledge, listRagDocuments, deleteRagDocument, reindexSeed
} from '@/api/rag'
import { listUploadedFiles, uploadFile, processUpload, addFileToKnowledge } from '@/api/upload'
import { fetchKnowledgeStats, clearKnowledge } from '@/api/knowledge'
import { confirmDanger, notifyError, notifySuccess } from '@/utils/notify'

/**
 * 知识库管理。
 *
 * 两套存储并存（内置 RAG 索引 + 早期轻量分块），界面上必须分开：
 * 混在一起会让教师以为"删了没生效"或者"清一次全没了"。
 */
const router = useRouter()
const tab = ref('search')

/** 次级入口：跳到 /generate/*，路由与后端接口都保留，只是不再占一级导航 */
function onQuickMake(type) {
  router.push(`/generate/${type}`)
}

const status = ref({})
const loadingStatus = ref(false)
const statusError = ref('')

const query = ref('')
const topK = ref(5)
const rerank = ref(true)
const searching = ref(false)
const searchError = ref('')
const searchResult = ref(null)

const files = ref([])
const loadingFiles = ref(false)
const fileError = ref('')
const addToKnowledge = ref(true)

const docs = ref([])
const loadingDocs = ref(false)
const docError = ref('')

const reindexing = ref(false)
const reindexResult = ref('')
const clearing = ref(false)
const lightweightCount = ref(0)

const statusOk = computed(() => !statusError.value && Object.keys(status.value).length > 0)

const LABELS = {
  vector_ready: '向量检索',
  bm25_ready: '关键词检索',
  rerank_ready: '重排序',
  has_index: '已有索引'
}

/** 状态里那些布尔字段（各通道是否可用）挑出来展示 */
const statusFlags = computed(() => {
  const out = {}
  for (const [k, v] of Object.entries(status.value)) {
    if (typeof v === 'boolean') out[LABELS[k] || k] = v
  }
  return out
})

const hits = computed(() => {
  const list = searchResult.value?.hits
  return Array.isArray(list) ? list : []
})

async function loadStatus() {
  loadingStatus.value = true
  statusError.value = ''
  try {
    status.value = await fetchRagStatus()
  } catch (e) {
    statusError.value = e?.message || '状态读取失败'
  } finally {
    loadingStatus.value = false
  }
}

async function onSearch() {
  if (!query.value.trim() || searching.value) return
  searching.value = true
  searchError.value = ''
  searchResult.value = null
  try {
    searchResult.value = await searchKnowledge({
      query: query.value.trim(),
      topK: topK.value,
      rerank: rerank.value
    })
  } catch (e) {
    searchError.value = e?.message || '检索失败'
  } finally {
    searching.value = false
  }
}

async function loadFiles() {
  loadingFiles.value = true
  fileError.value = ''
  try { files.value = await listUploadedFiles() } catch (e) { fileError.value = e?.message || '列表读取失败' } finally { loadingFiles.value = false }
}

async function loadDocs() {
  loadingDocs.value = true
  docError.value = ''
  try {
    const d = await listRagDocuments()
    docs.value = Array.isArray(d.documents) ? d.documents : []
  } catch (e) {
    docError.value = e?.message || '文档列表读取失败'
  } finally {
    loadingDocs.value = false
  }
}

async function loadStats() {
  try {
    const s = await fetchKnowledgeStats()
    lightweightCount.value = s?.chunks ?? s?.count ?? s?.total ?? 0
  } catch { lightweightCount.value = 0 }
}

async function onUpload({ file }) {
  try {
    await uploadFile(file, { addToKnowledge: addToKnowledge.value })
    notifySuccess('上传成功')
    await loadFiles()
    await loadStatus()
  } catch (e) {
    // 扫描版 PDF 提取不出文本 —— 后端会明确说明，这里原样转达
    notifyError(e?.message || '上传失败')
  }
}

async function onProcess(file) {
  try {
    const r = await processUpload(file.file_id)
    notifySuccess(r?.text_length ? `可以提取正文，约 ${r.text_length} 字` : '这份资料提取不出文本')
  } catch (e) {
    notifyError(e?.message || '解析失败')
  }
}

async function onAddToKnowledge(file) {
  try {
    await addFileToKnowledge(file.file_id)
    notifySuccess('已入库')
    await loadDocs()
    await loadStatus()
  } catch (e) {
    notifyError(e?.message || '入库失败')
  }
}

async function onDeleteDoc(d) {
  const id = d.document_id || d.id
  const ok = await confirmDanger({
    title: '从索引里移除这篇文档？',
    consequence: '它的所有片段都会被删除，之后的检索不会再命中它。<br>原始上传文件仍在「我的资料」里，可以重新入库。',
    confirmText: '确认移除'
  })
  if (!ok) return
  try {
    await deleteRagDocument(id)
    notifySuccess('已移除')
    await loadDocs()
  } catch (e) {
    notifyError(e?.message || '删除失败')
  }
}

async function onReindex() {
  if (reindexing.value) return
  reindexing.value = true
  reindexResult.value = ''
  try {
    const r = await reindexSeed()
    reindexResult.value = JSON.stringify(r, null, 2)
    notifySuccess(`重建完成：${r.documents ?? 0} 篇 / ${r.chunks ?? 0} 片段`)
    await loadStatus()
  } catch (e) {
    notifyError(e?.message || '重建失败')
  } finally {
    reindexing.value = false
  }
}

async function onClear() {
  const ok = await confirmDanger({
    title: '清空轻量知识库？',
    consequence: `将删除 ${lightweightCount.value} 个片段。<br>内置知识库索引与已上传的资料不受影响。`,
    confirmText: '确认清空'
  })
  if (!ok) return
  clearing.value = true
  try {
    await clearKnowledge()
    notifySuccess('已清空')
    await loadStats()
  } catch (e) {
    notifyError(e?.message || '清空失败')
  } finally {
    clearing.value = false
  }
}

function formatSize(n) {
  const v = Number(n || 0)
  if (v < 1024) return `${v} B`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`
  return `${(v / 1024 / 1024).toFixed(1)} MB`
}

onMounted(() => {
  loadStatus()
  loadFiles()
  loadDocs()
  loadStats()
})
</script>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: var(--sp-5);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}

.status__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--fs-sm);
}

.status__error {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--wb-risk-text);
}

.hits { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }

.hit {
  border-left: 2px solid var(--brand-border);
  padding-left: var(--sp-3);
}

.hit__head { display: flex; align-items: baseline; gap: var(--sp-2); flex-wrap: wrap; font-size: var(--fs-sm); }
.hit__score { font-family: var(--font-mono); font-size: 11px; color: var(--wb-text-3); }
.hit__text { margin: 4px 0 0; font-size: var(--fs-sm); color: var(--wb-text-2); line-height: 1.7; }

.files { list-style: none; margin: 0; padding: 0; }

.file {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 84px auto;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px 0;
  border-top: 1px solid var(--wb-border);
  font-size: var(--fs-sm);
}

.file__size { font-size: var(--fs-xs); color: var(--wb-text-3); }
.file__ops { display: flex; justify-content: flex-end; }

.note {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
}

.note--warn { background: var(--wb-warn-bg); color: var(--wb-warn-text); }

.lp { margin-top: var(--sp-4); }

.dump {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  background: var(--wb-code-bg);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  color: var(--wb-text-2);
}

.danger-text { color: var(--wb-risk-text); }

code {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  background: var(--wb-code-bg);
  padding: 1px 4px;
  border-radius: 4px;
}
</style>
