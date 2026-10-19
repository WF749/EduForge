<template>
  <div class="wb-page">
    <PageHeader
      title="资源库"
      description="所有生成过的课件、教案、动画与游戏都在这里。备课记录删了，文件也还在。"
      :badge="`${groups.length} 组`"
    >
      <template #actions>
        <!-- 不占一级导航的次级入口：想单独调参数出一份新东西时从这里进 -->
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
      </template>
    </PageHeader>

    <div class="wb-card wb-card-pad toolbar">
      <el-input v-model="keyword" placeholder="搜索文件名或所属备课" clearable style="max-width: 280px" aria-label="搜索资源">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="typeFilter" style="width: 140px" aria-label="类型筛选">
        <el-option label="全部类型" value="" />
        <el-option label="课件" value="课件" />
        <el-option label="教案" value="教案" />
        <el-option label="动画" value="动画" />
        <el-option label="游戏" value="游戏" />
      </el-select>
      <el-select v-model="sortBy" style="width: 140px" aria-label="排序方式">
        <el-option label="最近的在前" value="recent" />
        <el-option label="按名称" value="name" />
      </el-select>
      <el-button :icon="Refresh" @click="load" aria-label="刷新">刷新</el-button>
      <span class="wb-muted wb-grow">共 {{ groups.length }} 组 / {{ fileCount }} 个文件</span>
    </div>

    <StateBlock
      :loading="loading"
      hint="正在读取资源列表…"
      :error="error"
      :empty="!groups.length"
      empty-title="还没有生成过任何东西"
      empty-description="去工作台备一节课，或者到「生成中心」直接生成一份教案 / PPT / 动画 / 游戏。"
      @retry="load"
    >
      <template #emptyAction>
        <el-button type="primary" @click="$router.push('/generate/lesson-plan')">去生成</el-button>
      </template>

      <div class="wb-stack">
        <article v-for="g in paged" :key="g.dir + g.label" class="group">
          <header class="group__head">
            <div class="group__title">
              <StatusTag :status="g.label === '教案' ? 'pass' : 'active'" :label="g.label" />
              <b class="group__dir">{{ g.dir }}</b>
              <span v-if="g.lesson" class="group__lesson">属于「{{ g.lesson.topic }}」</span>
              <span v-else class="wb-muted">未归档到备课</span>
            </div>
            <el-button
              v-if="g.delete_url"
              size="small"
              text
              type="danger"
              @click="onDelete(g)"
            >
              删除整组
            </el-button>
          </header>

          <ul class="files">
            <li v-for="file in g.files" :key="file.name" class="file">
              <span class="file__ext">{{ (file.type || '').toUpperCase() }}</span>
              <span class="file__name wb-truncate">{{ file.name }}</span>
              <span class="file__size">{{ formatSize(file.size) }}</span>
              <span class="file__ops">
                <el-button
                  v-if="file.preview_url"
                  size="small"
                  text
                  @click="onPreview(file)"
                >
                  预览
                </el-button>
                <el-button size="small" text @click="onDownload(file)">下载</el-button>
              </span>
            </li>
          </ul>
        </article>
      </div>

      <div v-if="groups.length > pageSize" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="groups.length"
          layout="prev, pager, next"
          background
        />
      </div>
    </StateBlock>

    <!-- 教案文件（平铺在教案目录里的那批） -->
    <section class="wb-card wb-card-pad lp">
      <div class="wb-row wb-row-between">
        <div>
          <b>导出的教案文件</b>
          <p class="wb-card-hint">教案是平铺文件，不按目录分组；这里按文件名倒序列出。</p>
        </div>
        <el-button size="small" :icon="Refresh" :loading="loadingPlans" @click="loadPlans">
          刷新
        </el-button>
      </div>

      <StateBlock
        :loading="loadingPlans"
        :error="planError"
        :empty="!planFiles.length"
        empty-title="还没有导出过教案"
        empty-description="在生成中心生成教案后点「导出 Word」，文件会出现在这里。"
        :retryable="false"
      >
        <ul class="files">
          <li v-for="file in planFiles" :key="file.name" class="file">
            <span class="file__ext">{{ extOf(file.name) }}</span>
            <span class="file__name wb-truncate">{{ file.name }}</span>
            <span class="file__size">{{ formatSize(file.size) }}</span>
            <span class="file__ops">
              <el-button size="small" text @click="openUrl(lessonPlanDownloadUrl(file.name))">
                下载
              </el-button>
            </span>
          </li>
        </ul>
      </StateBlock>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, MagicStick, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { listGeneratedFiles, deleteGeneratedDir, coursewareDownloadUrl } from '@/api/courseware'
import { listLessonPlanFiles, lessonPlanDownloadUrl } from '@/api/lessonPlan'
import { trackedFetch } from '@/api/dataFlow'
import { confirmDanger, notifyError, notifySuccess } from '@/utils/notify'

/**
 * 历史作品。
 *
 * 归属信息来自后端反查表（生成目录名 → 课程）。读不到时按"未归档"显示，
 * 不影响列表 —— 历史作品没有归属也能用，不该因为台账坏了就整个打不开。
 */
const router = useRouter()

const groups = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const typeFilter = ref('')
const sortBy = ref('recent')
const page = ref(1)
const pageSize = 8

const planFiles = ref([])
const loadingPlans = ref(false)
const planError = ref('')

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  let out = groups.value
  if (typeFilter.value) out = out.filter(g => g.label === typeFilter.value)
  if (k) {
    out = out.filter(g =>
      `${g.dir} ${g.lesson?.topic || ''} ${(g.files || []).map(f => f.name).join(' ')}`
        .toLowerCase().includes(k))
  }
  const sorted = [...out]
  if (sortBy.value === 'name') sorted.sort((a, b) => String(a.dir).localeCompare(String(b.dir)))
  else sorted.sort((a, b) => String(b.dir).localeCompare(String(a.dir)))
  return sorted
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

const fileCount = computed(() =>
  filtered.value.reduce((n, g) => n + (g.files?.length || 0), 0))

async function load() {
  loading.value = true
  error.value = ''
  try {
    groups.value = await listGeneratedFiles()
  } catch (e) {
    error.value = e?.message || '文件列表加载失败'
  } finally {
    loading.value = false
  }
}

async function loadPlans() {
  loadingPlans.value = true
  planError.value = ''
  try {
    const list = await listLessonPlanFiles()
    planFiles.value = [...list].sort((a, b) => (b.mtime || 0) - (a.mtime || 0))
  } catch (e) {
    planError.value = e?.message || '教案文件列表加载失败'
  } finally {
    loadingPlans.value = false
  }
}

/** 次级入口：跳到 /generate/*，路由与后端接口都保留，只是不再占一级导航 */
function onQuickMake(type) {
  router.push(`/generate/${type}`)
}

function formatSize(n) {
  const v = Number(n || 0)
  if (v < 1024) return `${v} B`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`
  return `${(v / 1024 / 1024).toFixed(1)} MB`
}

function extOf(name) {
  return String(name).split('.').pop()?.toUpperCase() || ''
}

function openUrl(url) {
  if (url) window.open(url, '_blank', 'noopener')
}

function onDownload(file) {
  openUrl(file.download_url || coursewareDownloadUrl({ fileType: file.type, taskDir: '' }))
}

/** 预览 HTML：下载接口带 attachment，必须转成 Blob 才能看 */
async function onPreview(file) {
  const url = file.preview_url || file.download_url
  if (!url) return
  try {
    const res = await trackedFetch(url)
    if (!res.ok) throw new Error(`预览失败（HTTP ${res.status}）`)
    const blob = await res.blob()
    const objUrl = URL.createObjectURL(new Blob([blob], { type: 'text/html;charset=utf-8' }))
    window.open(objUrl, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(objUrl), 60000)
  } catch (e) {
    notifyError(e?.message || '预览失败')
  }
}

async function onDelete(g) {
  const ok = await confirmDanger({
    title: `删除「${g.dir}」整组？`,
    consequence: `这一组共 ${g.files?.length || 0} 个文件会被永久删除，回收站也找不回来。<br>备课记录不受影响，只是指向的文件没了。`,
    confirmText: '确认删除'
  })
  if (!ok) return
  try {
    await deleteGeneratedDir(g.delete_url)
    notifySuccess('已删除')
    await load()
  } catch (e) {
    notifyError(e?.message || '删除失败')
  }
}

watch([keyword, typeFilter, sortBy], () => { page.value = 1 })

onMounted(() => {
  load()
  loadPlans()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}

.group {
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-md);
  background: var(--wb-surface);
  padding: var(--sp-3);
}

.group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-bottom: var(--sp-2);
}

.group__title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
  flex-wrap: wrap;
}

.group__dir {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
}

.group__lesson { font-size: var(--fs-xs); color: var(--brand-text); }

.files { list-style: none; margin: 0; padding: 0; }

.file {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 84px auto;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px 0;
  border-top: 1px solid var(--wb-border);
  font-size: var(--fs-sm);
}

.file__ext {
  font-size: 10px;
  font-weight: 600;
  text-align: center;
  padding: 2px 0;
  border-radius: 4px;
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
}

.file__size { font-size: var(--fs-xs); color: var(--wb-text-3); }
.file__ops { display: flex; gap: 0; justify-content: flex-end; }

.pager { display: flex; justify-content: center; margin-top: var(--sp-4); }

.lp { margin-top: var(--sp-5); }

@media (max-width: 768px) {
  .file { grid-template-columns: 44px minmax(0, 1fr) auto; }
  .file__size { display: none; }
}
</style>
