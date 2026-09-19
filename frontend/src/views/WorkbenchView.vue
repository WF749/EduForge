<template>
  <div class="workbench">
    <LessonContextBar />

    <div class="wb-body" :class="{ 'is-side-collapsed': sideCollapsed }">
      <!-- 主舞台：对话。成品是它的附属，不再是并列的两半 -->
      <main class="wb-chat">
        <LessonChat
          :active-kind="activeTab"
          :busy="anyRunning"
          @switch-kind="openPanel"
          @generate="handleGenerate"
          @revise="handleRevise"
        />
      </main>

      <section class="wb-side">
        <header class="wb-side-head">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="wb-tab"
            :class="{ active: activeTab === tab.id }"
            type="button"
            :title="tab.name"
            @click="activeTab = tab.id"
          >
            <el-icon :size="15"><component :is="tab.icon" /></el-icon>
            <span class="wb-tab-name">{{ tab.name }}</span>
            <span v-if="statusOf(tab.id)" class="wb-dot" :class="`dot-${statusOf(tab.id)}`" />
          </button>

          <button
            class="wb-collapse"
            type="button"
            title="收起成品栏，把宽度让给对话"
            @click="sideCollapsed = true"
          >
            <el-icon :size="14"><DArrowRight /></el-icon>
          </button>
        </header>

        <div class="wb-side-body">
          <component :is="currentPanel" />
        </div>
      </section>

      <!-- 收起后留一个竖标签，成品始终一键可达（不能让人找不到） -->
      <button
        v-if="sideCollapsed"
        class="wb-expand"
        type="button"
        title="展开成品栏"
        @click="sideCollapsed = false"
      >
        <el-icon :size="14"><DArrowLeft /></el-icon>
        <span>成品</span>
        <span v-if="doneCount" class="wb-expand-badge">{{ doneCount }}</span>
      </button>
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
  HomeFilled, Files, Document, VideoCamera, TrophyBase,
  DArrowLeft, DArrowRight
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

const activeTab = ref('lesson_plan')
const sideCollapsed = ref(false)

// 顺序按"一节课的产出顺序"排，概览放最后 —— 它是回看用的，不是产出
const tabs = [
  { id: 'lesson_plan', name: '教案', icon: Files },
  { id: 'ppt', name: 'PPT', icon: Document },
  { id: 'animation', name: '动画', icon: VideoCamera },
  { id: 'game', name: '游戏', icon: TrophyBase },
  { id: 'overview', name: '概览', icon: HomeFilled }
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

const doneCount = computed(() =>
  Object.values(store.artifacts).filter((a) => a.status === 'done').length)

function statusOf(id) {
  return store.artifacts[id]?.status || 'idle'
}

/** 打开某个成品的面板：对话里说"在右侧查看"、点标签、切换类型都走这里 */
function openPanel(id) {
  if (!panels[id]) return
  activeTab.value = id
  sideCollapsed.value = false
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
  // 生成时把成品栏让出来看进度；但不动用户已经收起的意图之外的布局
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
/*
 * 布局原则：对话是主舞台，成品是它的附属。
 *
 * 之前的写法是 200px（最近课程）| 320-400px（对话）| 1fr（成品）：
 * 对话被夹在中间最窄的一列，右侧一大片空白，而左边那 200px 的"最近课程"
 * 和顶部课程条里的切换下拉是**同一个功能**。现在把重复的那一栏删掉、
 * 成品降为可收起的辅列，宽度全部让给对话。
 */
.workbench {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-sizing: border-box;
  /* 68px 顶栏 + 44px 底栏：让工作台正好占满一屏，内部各自滚动，
     而不是整页滚动时对话被拉到看不见输入框 */
  height: calc(100vh - 112px);
  /* 小窗口下退化成整页滚动，而不是把对话压成一条缝 */
  min-height: 560px;
  max-width: 1560px;
  margin: 0 auto;
  padding: 16px 24px 18px;
}

.wb-body {
  flex: 1;
  min-height: 0;
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 420px);
  gap: 16px;
  align-items: stretch;

  &.is-side-collapsed {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;

    .wb-side { display: none; }
    .wb-chat { max-width: 1180px; margin: 0 auto; width: 100%; }
  }
}

.wb-chat {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.wb-side {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(8, 12, 33, 0.72);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 16px;
  overflow: hidden;
}

.wb-side-head {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 8px 8px 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  flex: none;
}

.wb-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 9px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 9px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover { background: rgba(0, 200, 255, 0.08); color: #fff; }

  &.active {
    background: rgba(0, 200, 255, 0.14);
    border-color: rgba(0, 200, 255, 0.38);
    color: #fff;
  }
}

.wb-collapse {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-left: auto;
  color: rgba(255, 255, 255, 0.4);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    color: #fff;
    background: rgba(0, 200, 255, 0.1);
    border-color: rgba(0, 200, 255, 0.3);
  }
}

.wb-side-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 200, 255, 0.2);
    border-radius: 3px;
  }
}

/* 收起后的竖标签：贴在工作台右缘，不占宽度也不消失 */
.wb-expand {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 7px;
  font-family: inherit;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(8, 12, 33, 0.92);
  border: 1px solid rgba(0, 200, 255, 0.28);
  border-right: none;
  border-radius: 10px 0 0 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  z-index: 5;

  span { writing-mode: vertical-rl; }

  &:hover {
    color: #fff;
    background: rgba(0, 200, 255, 0.16);
  }
}

.wb-expand-badge {
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  color: #04121f;
  background: #00ff88;
  border-radius: 8px;
  writing-mode: horizontal-tb;
}

.wb-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  flex: none;

  &.dot-done { background: #00ff88; box-shadow: 0 0 6px rgba(0, 255, 136, 0.7); }
  &.dot-running { background: #00c8ff; animation: rail-blink 1.2s ease-in-out infinite; }
  &.dot-failed { background: #ff6b6b; }
}

@keyframes rail-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

@media (max-width: 1400px) {
  .wb-body { grid-template-columns: minmax(0, 1fr) minmax(320px, 380px); }
}

@media (max-width: 1080px) {
  /* 窄屏：成品压到对话下面，仍然以对话为主 */
  .workbench { height: auto; min-height: 0; }
  .wb-body {
    grid-template-columns: minmax(0, 1fr);
    grid-auto-rows: minmax(0, auto);
  }
  .wb-chat { min-height: 62vh; }
  .wb-side { max-height: 70vh; }
}

@media (max-width: 860px) {
  .workbench { padding: 12px 12px 16px; gap: 12px; }
  .wb-chat { min-height: 70vh; }
  .wb-tab-name { display: none; }
  .wb-side-body { padding: 12px; }
}
</style>
