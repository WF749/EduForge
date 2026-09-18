<template>
  <div class="workbench">
    <LessonContextBar />

    <div class="wb-body">
      <aside class="wb-rail">
        <div class="rail-title">
          <span>最近课程</span>
          <el-button text size="small" :icon="Refresh" @click="store.loadRecent()" />
        </div>
        <p v-if="!store.recentTasks.length" class="rail-empty">
          还没有课程记录。填好教学主题后自动建立。
        </p>
        <button
          v-for="t in store.recentTasks"
          :key="t.id"
          type="button"
          class="rail-recent"
          :class="{ current: t.id === store.taskId }"
          @click="switchTo(t.id)"
        >
          <span class="rr-topic">{{ t.topic || '（未命名课程）' }}</span>
          <span class="rr-meta">{{ t.subject }} · {{ t.grade }} · {{ t.artifactCount }}/4</span>
        </button>
      </aside>

      <!-- 左：对话（主界面） -->
      <LessonChat
        :active-kind="activeTab"
        :busy="anyRunning"
        @switch-kind="activeTab = $event"
        @generate="handleGenerate"
        @revise="handleRevise"
      />

      <!-- 右：成品 -->
      <main class="wb-work">
        <div class="wb-tabs">
          <button
            v-for="tab in artifactTabs"
            :key="tab.id"
            class="wb-tab"
            :class="{ active: activeTab === tab.id }"
            type="button"
            @click="activeTab = tab.id"
          >
            <el-icon :size="16"><component :is="tab.icon" /></el-icon>
            <span>{{ tab.name }}</span>
            <span v-if="statusOf(tab.id)" class="rail-dot" :class="`dot-${statusOf(tab.id)}`" />
          </button>
          <button
            class="wb-tab"
            :class="{ active: activeTab === 'overview' }"
            type="button"
            @click="activeTab = 'overview'"
          >
            <el-icon :size="16"><HomeFilled /></el-icon>
            <span>课程概览</span>
          </button>
        </div>

        <component :is="currentPanel" class="wb-panel" />
      </main>
    </div>
  </div>
</template>

<script>
export default { name: 'WorkbenchView' }
</script>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Files, Document, VideoCamera, TrophyBase, Refresh
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import LessonContextBar from '@/components/lesson/LessonContextBar.vue'
import LessonChat from '@/components/lesson/LessonChat.vue'
import OverviewPanel from '@/components/lesson/panels/OverviewPanel.vue'
import LessonPlanPanel from '@/components/lesson/panels/LessonPlanPanel.vue'
import PptPanel from '@/components/lesson/panels/PptPanel.vue'
import AnimationPanel from '@/components/lesson/panels/AnimationPanel.vue'
import GamePanel from '@/components/lesson/panels/GamePanel.vue'
import { useLessonStore } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import {
  generateLessonPlan, generatePpt, generateAnimation, generateGame,
  reviseLessonPlan, contextPayload
} from '@/api/lessonArtifacts'

const route = useRoute()
const store = useLessonStore()

const activeTab = ref('overview')

const artifactTabs = [
  { id: 'lesson_plan', name: '教案', icon: Files },
  { id: 'ppt', name: 'PPT', icon: Document },
  { id: 'animation', name: '动画', icon: VideoCamera },
  { id: 'game', name: '游戏', icon: TrophyBase }
]

const panels = {
  overview: OverviewPanel,
  lesson_plan: LessonPlanPanel,
  ppt: PptPanel,
  animation: AnimationPanel,
  game: GamePanel
}
const currentPanel = computed(() => panels[activeTab.value] || OverviewPanel)

// 四个执行器各持一份，但 running 从 store 派生，
// 所以对话触发的生成和面板按钮看到的进度是同一份状态。
const runners = {
  lesson_plan: useArtifactRunner('lesson_plan'),
  ppt: useArtifactRunner('ppt'),
  animation: useArtifactRunner('animation'),
  game: useArtifactRunner('game')
}

const anyRunning = computed(() =>
  Object.values(runners).some((r) => r.running.value))

function statusOf(id) {
  return store.artifacts[id]?.status || 'idle'
}

const GENERATORS = {
  lesson_plan: (ctx) => generateLessonPlan(ctx),
  ppt: (ctx) => generatePpt(ctx, {
    themeColor: store.pptTheme,
    onProgress: () => {}
  }),
  animation: (ctx) => generateAnimation(ctx, { minutes: store.animationMinutes }),
  game: (ctx) => generateGame(ctx, { gameType: store.gameType })
}

async function ensureTask() {
  // 生成/修改都要挂在某一节课上；没有 id 就先同步一次（幂等 upsert）
  if (!store.taskId) await store.syncContext()
  return Boolean(store.taskId)
}

async function handleGenerate(kind) {
  if (!store.ready) {
    ElMessage.warning('请先填好教学主题、学科与年级')
    return
  }
  const runner = runners[kind]
  if (!runner || runner.running.value) return
  if (!(await ensureTask())) {
    ElMessage.error('课程同步失败，请刷新页面重试')
    return
  }
  activeTab.value = kind
  const ok = await runner.run(() => GENERATORS[kind](contextPayload(store)))
  if (ok) ElMessage.success('生成完成')
  else ElMessage.error(store.artifacts[kind]?.error || '生成失败')
}

async function handleRevise({ kind, instruction }) {
  // 目前只有教案的版本链通了修改。其余如实说明，不给"点了没反应"的选项。
  if (kind !== 'lesson_plan') {
    ElMessage.warning('目前只有教案支持按指令修改')
    return
  }
  const runner = runners[kind]
  if (!runner || runner.running.value) return
  if (!store.ready) {
    ElMessage.warning('请先填好学科与年级')
    return
  }
  if (!(await ensureTask())) {
    ElMessage.error('课程同步失败，请刷新页面重试')
    return
  }
  const ok = await runner.run(() =>
    reviseLessonPlan({ lessonId: store.taskId, instruction, ctx: contextPayload(store) }))
  if (ok) ElMessage.success('已按指令修改')
  else ElMessage.error(store.artifacts[kind]?.error || '修改失败（原版本未被改动）')
}

async function switchTo(id) {
  if (!id || id === store.taskId) return
  const ok = await store.switchTask(id)
  if (ok) ElMessage.success('已切换到该课程')
  else ElMessage.error('切换失败：读不到这节课的记录')
}

// 从对话页带 query 跳过来时（/?topic=...）填进这一节课。
// 用 watch 而不是 onMounted：本页被 keep-alive 缓存，"已访问过工作台 → 去对话 → 再回来"
// 这条路径不会重新触发 onMounted，只靠它会静默丢掉传过来的主题。
watch(
  () => route.query,
  async (q) => {
    if (!q) return
    if (q.lesson) {
      await store.switchTask(String(q.lesson))
      return
    }
    if (q.topic || q.subject) store.applyQuery(q)
  },
  { immediate: true }
)

// 启动时先渲染本地存档，再异步用后端台账覆盖 —— 顺序反了会白屏等网络。
onMounted(async () => {
  if (store.taskId) await store.restoreFromServer()
  else if (store.ready) await store.syncContext()
  await store.loadRecent()
})
</script>

<style lang="scss" scoped>
.workbench {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1560px;
  margin: 0 auto;
  padding: 20px 24px 32px;
}

.wb-body {
  display: grid;
  grid-template-columns: 200px minmax(320px, 400px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.wb-rail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: rgba(10, 14, 39, 0.72);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 14px;
  position: sticky;
  top: 12px;

  .rail-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 6px 4px 12px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.35);
  }

  .rail-empty {
    padding: 4px 12px 8px;
    font-size: 12px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.28);
  }
}

.rail-recent {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover { background: rgba(0, 200, 255, 0.08); color: #fff; }

  &.current {
    background: rgba(0, 200, 255, 0.12);
    border-color: rgba(0, 200, 255, 0.32);
    color: #fff;
  }

  .rr-topic {
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rr-meta { font-size: 11px; color: rgba(255, 255, 255, 0.35); }
}

.wb-work {
  min-width: 0;
  padding: 16px 22px 22px;
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 16px;
}

.wb-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 14px;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.wb-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover { background: rgba(0, 200, 255, 0.08); color: #fff; }

  &.active {
    background: rgba(0, 200, 255, 0.14);
    border-color: rgba(0, 200, 255, 0.4);
    color: #fff;
  }
}

.rail-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);

  &.dot-done { background: #00ff88; box-shadow: 0 0 6px rgba(0, 255, 136, 0.7); }
  &.dot-running { background: #00c8ff; animation: rail-blink 1.2s ease-in-out infinite; }
  &.dot-failed { background: #ff6b6b; }
}

@keyframes rail-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

@media (max-width: 1400px) {
  .wb-body { grid-template-columns: 180px minmax(300px, 360px) minmax(0, 1fr); }
}

@media (max-width: 1180px) {
  .wb-body { grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); }
  .wb-rail { grid-column: 1 / -1; position: static; flex-direction: row; flex-wrap: wrap; align-items: center; }
  .wb-rail .rail-empty { display: none; }
}

@media (max-width: 860px) {
  .wb-body { grid-template-columns: 1fr; }
  .workbench { padding: 14px 12px 24px; gap: 14px; }
  .wb-work { padding: 14px 14px 18px; }
}
</style>
