<template>
  <div class="rail">
    <header class="rail-head">
      <button
        v-for="t in RAIL_TABS"
        :key="t.id"
        class="rail-tab"
        :class="{ active: tab === t.id }"
        type="button"
        @click="tab = t.id"
      >
        {{ t.name }}
      </button>
      <button class="rail-close" type="button" title="收起" @click="emit('close')">
        <el-icon :size="14"><DArrowLeft /></el-icon>
      </button>
    </header>

    <div class="rail-body">
      <!-- 课程历史：换课用 -->
      <template v-if="tab === 'history'">
        <p class="rail-hint">点一节课就切过去，当前这节会自动保存。</p>
        <ul v-if="tasks.length" class="rail-list">
          <li v-for="t in tasks" :key="t.id">
            <button
              class="rail-item"
              :class="{ current: t.id === store.taskId }"
              type="button"
              @click="pick(t.id)"
            >
              <span class="ri-topic">{{ t.topic || '（未命名）' }}</span>
              <span class="ri-meta">{{ [t.subject, t.grade].filter(Boolean).join(' · ') }}</span>
              <span v-if="t.id === store.taskId" class="ri-now">当前</span>
            </button>
          </li>
        </ul>
        <p v-else class="rail-empty">还没有别的课。先在对话里说一句要备什么课。</p>
      </template>

      <!-- 版本时间线：回退用 -->
      <template v-else>
        <p class="rail-hint">
          每版都保留，回退不会删历史。当前类型：{{ kindName }}
        </p>
        <ul v-if="versions.length" class="rail-list">
          <li v-for="v in versions" :key="v.version">
            <div class="rail-ver">
              <span class="rv-no">v{{ v.version }}</span>
              <span class="rv-note" :title="v.note">{{ v.note || '（无说明）' }}</span>
              <span v-if="v.version === current" class="ri-now">当前</span>
              <button
                v-else
                class="rv-back"
                type="button"
                :disabled="busy"
                @click="emit('revert', v.version)"
              >
                回到这版
              </button>
            </div>
          </li>
        </ul>
        <p v-else class="rail-empty">
          {{ store.taskId ? '这一类产物还没有版本记录。' : '课程未同步到后端，版本历史不可用。' }}
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { DArrowLeft } from '@element-plus/icons-vue'
import { useLessonStore, ARTIFACTS } from '@/store/lesson'
import { listVersions } from '@/api/lessonArtifacts'

const props = defineProps({
  kind: { type: String, default: 'lesson_plan' },
  busy: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'revert', 'switch'])

const RAIL_TABS = [
  { id: 'history', name: '课程历史' },
  { id: 'version', name: '版本时间线' }
]

const store = useLessonStore()
const tab = ref('history')
const versions = ref([])
const current = ref(0)

const tasks = computed(() => (store.recentTasks || []).slice(0, 20))
const kindName = computed(
  () => (ARTIFACTS.find((a) => a.id === props.kind) || ARTIFACTS[0]).name)

async function loadVersions() {
  if (!store.taskId) {
    versions.value = []
    current.value = 0
    return
  }
  try {
    const d = await listVersions(store.taskId, props.kind)
    versions.value = d.versions || []
    current.value = d.current || 0
  } catch {
    versions.value = []
    current.value = 0
  }
}

// 切到时间线才读，且课程或类型变了要重读 —— 否则会一直显示上一节课的版本
watch([tab, () => props.kind, () => store.taskId], () => {
  if (tab.value === 'version') loadVersions()
}, { immediate: true })

async function pick(id) {
  if (!id || id === store.taskId) return
  const ok = await store.switchTask(id)
  emit('switch', { id, ok })
  loadVersions()
}
</script>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--wb-surface);
  border-right: 1px solid var(--wb-border);
}
.rail-head {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--wb-border);
}
.rail-tab {
  padding: 5px 10px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--wb-text-2);
  cursor: pointer;
  transition: all 0.2s ease;
}
.rail-tab.active {
  background: var(--wb-hover);
  color: var(--wb-text);
}
.rail-close {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding: 4px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--wb-text-3);
  cursor: pointer;
}
.rail-close:hover {
  color: var(--wb-text);
  background: var(--wb-hover);
}
.rail-body {
  flex: 1;
  overflow: auto;
  padding: 10px;
}
.rail-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--wb-text-3);
}
.rail-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.rail-item {
  display: block;
  width: 100%;
  padding: 8px 10px;
  margin-bottom: 6px;
  text-align: left;
  border: 1px solid var(--wb-border);
  border-radius: 8px;
  background: var(--wb-surface-2);
  cursor: pointer;
  transition: all 0.2s ease;
}
.rail-item:hover {
  border-color: var(--wb-border-strong);
  transform: translateX(2px);
}
.rail-item.current {
  border-color: var(--wb-border-strong);
  background: var(--wb-hover);
}
.ri-topic {
  display: block;
  font-size: 13.5px;
  color: var(--wb-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ri-meta {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--wb-text-3);
}
.ri-now {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 4px;
  background: var(--wb-hover);
  color: var(--wb-text-2);
}
.rail-ver {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  margin-bottom: 6px;
  border-radius: 8px;
  background: var(--wb-surface-2);
}
.rv-no {
  font-size: 12px;
  font-weight: 600;
  color: var(--wb-text-2);
}
.rv-note {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  color: var(--wb-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rv-back {
  flex-shrink: 0;
  padding: 2px 6px;
  font-size: 11.5px;
  border: 1px solid var(--wb-border);
  border-radius: 5px;
  background: transparent;
  color: var(--wb-text-2);
  cursor: pointer;
}
.rv-back:hover:not(:disabled) {
  color: var(--primary);
  border-color: var(--wb-border-strong);
}
.rv-back:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.rail-empty {
  padding: 18px 6px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--wb-text-3);
}
</style>
