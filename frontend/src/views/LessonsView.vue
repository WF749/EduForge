<template>
  <div class="wb-page">
    <PageHeader
      title="我的备课"
      description="每一次备课都会记下主题、学情参数和它对应的四类产物。换电脑、清缓存之后，记录还在。"
      :badge="`${tasks.length} 节`"
    >
      <template #actions>
        <el-button type="primary" :icon="Plus" @click="onCreate">新建备课</el-button>
      </template>
    </PageHeader>

    <!-- 搜索 / 筛选 / 排序 -->
    <div class="wb-card wb-card-pad toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索主题、学科或年级"
        clearable
        style="max-width: 280px"
        aria-label="搜索备课"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-select v-model="archived" style="width: 140px" aria-label="归档筛选">
        <el-option label="全部备课" :value="null" />
        <el-option label="进行中" :value="false" />
        <el-option label="已归档" :value="true" />
      </el-select>

      <el-select v-model="sortBy" style="width: 140px" aria-label="排序方式">
        <el-option label="最近更新" value="updated" />
        <el-option label="主题名称" value="topic" />
        <el-option label="完成最多" value="artifacts" />
      </el-select>

      <span class="wb-muted wb-grow">共 {{ filtered.length }} 节备课</span>
    </div>

    <StateBlock
      :loading="loading"
      hint="正在读取备课记录…"
      :error="error"
      :empty="!filtered.length"
      :empty-title="keyword ? '没有匹配的备课' : '还没有备课'"
      :empty-description="keyword ? '换个关键词试试，或者清空搜索看全部。' : '从一句话开始：新建备课，填上主题就能备课。'"
      @retry="load"
    >
      <template #emptyAction>
        <el-button type="primary" @click="onCreate">新建备课</el-button>
      </template>

      <div class="grid">
        <article v-for="t in paged" :key="t.id" class="lesson">
          <header class="lesson__head">
            <b class="lesson__topic">{{ t.topic || '未命名备课' }}</b>
            <StatusTag v-if="t.archived" status="archived" />
          </header>
          <p class="lesson__meta">
            {{ t.subject || '未设学科' }} · {{ t.grade || '未设年级' }} · {{ t.duration || 45 }} 分钟
          </p>
          <p class="lesson__time">更新于 {{ formatTime(t.updatedAt) }}</p>

          <div class="lesson__progress" :aria-label="`已完成 ${t.artifactCount} 项产物`">
            <span
              v-for="i in 4"
              :key="i"
              class="lesson__dot"
              :class="{ 'is-done': i <= t.artifactCount }"
            />
            <span class="wb-muted">已完成 {{ t.artifactCount }}/4</span>
          </div>

          <footer class="lesson__foot">
            <el-button size="small" type="primary" @click="onOpen(t)">进入备课</el-button>
            <el-button size="small" text @click="onArchive(t)">
              {{ t.archived ? '取消归档' : '归档' }}
            </el-button>
            <el-button size="small" text type="danger" @click="onDelete(t)">删除</el-button>
          </footer>
        </article>
      </div>

      <div v-if="filtered.length > pageSize" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="filtered.length"
          layout="prev, pager, next"
          background
        />
      </div>
    </StateBlock>

    <!-- 新建备课 -->
    <el-dialog v-model="dialog" title="新建备课" width="440px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="教学主题" required>
          <el-input
            v-model="form.topic"
            placeholder="例如：浮力"
            maxlength="60"
            :class="{ 'is-invalid': submitted && !form.topic.trim() }"
          />
          <p v-if="submitted && !form.topic.trim()" class="field-error">请填写教学主题</p>
        </el-form-item>
        <div class="wb-row">
          <el-form-item label="学科" class="wb-grow">
            <el-select v-model="form.subject">
              <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="年级" class="wb-grow">
            <el-select v-model="form.grade">
              <el-option v-for="g in GRADES" :key="g" :label="g" :value="g" />
            </el-select>
          </el-form-item>
          <el-form-item label="时长（分钟）" class="wb-grow">
            <el-input-number v-model="form.duration" :min="15" :max="180" :step="5" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <!-- 提交中禁用 + 请求锁，防止连点建出两节一模一样的课 -->
        <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { SUBJECTS, GRADES, useLessonStore } from '@/store/lesson'
import { fetchTasks, upsertTask, archiveTask, deleteTask } from '@/api/lessonTasks'
import { confirmDanger, notifyError, notifySuccess } from '@/utils/notify'

/**
 * 备课台账（用户可见名称：我的备课）。
 *
 * 搜索 / 筛选 / 排序 / 分页都在前端做：后端 `/lesson-tasks` 只给最近 50 条
 * （这是个本地备课工具，不是档案系统），再翻页没有意义，所以一次取全、本地切。
 */
const router = useRouter()
const store = useLessonStore()

const tasks = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const archived = ref(false)
const sortBy = ref('updated')
const page = ref(1)
const pageSize = 12

const dialog = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const form = ref({ topic: '', subject: '数学', grade: '七年级', duration: 45 })

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  let out = tasks.value.filter(t => {
    if (archived.value === null) return true
    return !!t.archived === archived.value
  })
  if (k) {
    out = out.filter(t =>
      [t.topic, t.subject, t.grade].join(' ').toLowerCase().includes(k))
  }
  const sorted = [...out]
  if (sortBy.value === 'topic') {
    sorted.sort((a, b) => String(a.topic || '').localeCompare(String(b.topic || ''), 'zh'))
  } else if (sortBy.value === 'artifacts') {
    sorted.sort((a, b) => (b.artifactCount || 0) - (a.artifactCount || 0))
  } else {
    sorted.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
  }
  return sorted
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    // 一次取满配额（后端上限 50），分页在本地做
    tasks.value = await fetchTasks(50, archived.value)
  } catch (e) {
    error.value = e?.message || '备课列表加载失败'
  } finally {
    loading.value = false
  }
}

function formatTime(ms) {
  if (!ms) return '—'
  const d = new Date(ms)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function onCreate() {
  form.value = { topic: '', subject: '数学', grade: '七年级', duration: 45 }
  submitted.value = false
  dialog.value = true
}

async function submit() {
  submitted.value = true
  if (!form.value.topic.trim()) return
  if (submitting.value) return
  submitting.value = true
  try {
    const task = await upsertTask({ ...form.value })
    notifySuccess('备课已创建')
    dialog.value = false
    await load()
    onOpen(task)
  } catch (e) {
    notifyError(e?.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

async function onOpen(t) {
  await store.switchTask(t.id)
  router.push('/')
}

async function onArchive(t) {
  try {
    await archiveTask(t.id, !t.archived)
    notifySuccess(t.archived ? '已取消归档' : '已归档')
    await load()
  } catch (e) {
    notifyError(e?.message || '操作失败')
  }
}

async function onDelete(t) {
  const ok = await confirmDanger({
    title: `删除「${t.topic || '未命名备课'}」？`,
    consequence: '台账记录会被删除，这节课的版本历史也会一起清掉。<br>已经导出过的文件不受影响，仍可在「资源库」里下载。',
    confirmText: '确认删除'
  })
  if (!ok) return
  try {
    await deleteTask(t.id)
    notifySuccess('已删除')
    await load()
  } catch (e) {
    notifyError(e?.message || '删除失败')
  }
}

// 筛选条件变了要回到第一页，否则会停在一个已经不存在的页码上
watch([keyword, archived, sortBy], () => { page.value = 1 })

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: var(--sp-3);
}

.lesson {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-4);
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-md);
  background: var(--wb-surface);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--dur-fast) var(--ease);
}

.lesson:hover { box-shadow: var(--shadow-md); }

.lesson__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}

.lesson__topic {
  font-size: var(--fs-md);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lesson__meta { margin: 0; font-size: var(--fs-sm); color: var(--wb-text-2); }
.lesson__time { margin: 0; font-size: var(--fs-xs); color: var(--wb-text-3); }

.lesson__progress {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
}

.lesson__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--wb-surface-3);
}

.lesson__dot.is-done { background: var(--success); }

.lesson__foot {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  margin-top: auto;
  flex-wrap: wrap;
}

.pager {
  display: flex;
  justify-content: center;
  margin-top: var(--sp-4);
}

.field-error {
  margin: 4px 0 0;
  font-size: var(--fs-xs);
  color: var(--wb-risk-text);
}

.is-invalid :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger) inset !important;
}
</style>
