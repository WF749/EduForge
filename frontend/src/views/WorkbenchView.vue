<template>
  <div class="workbench">
    <LessonContextBar />

    <div class="wb-body">
      <aside class="wb-rail">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="rail-item"
          :class="{ active: activeTab === tab.id }"
          type="button"
          @click="activeTab = tab.id"
        >
          <el-icon :size="18"><component :is="tab.icon" /></el-icon>
          <span class="rail-name">{{ tab.name }}</span>
          <span v-if="statusOf(tab.id)" class="rail-dot" :class="`dot-${statusOf(tab.id)}`" />
        </button>

        <!-- 知识库 / 历史作品 已从这里移除：顶部导航里有，两处都放只是重复入口 -->
        <div class="rail-foot">
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
        </div>
      </aside>

      <main class="wb-work">
        <component :is="currentPanel" />
      </main>
    </div>
  </div>
</template>

<script>
export default { name: 'WorkbenchView' }
</script>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Files, Document, VideoCamera, TrophyBase, Refresh
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import LessonContextBar from '@/components/lesson/LessonContextBar.vue'
import OverviewPanel from '@/components/lesson/panels/OverviewPanel.vue'
import LessonPlanPanel from '@/components/lesson/panels/LessonPlanPanel.vue'
import PptPanel from '@/components/lesson/panels/PptPanel.vue'
import AnimationPanel from '@/components/lesson/panels/AnimationPanel.vue'
import GamePanel from '@/components/lesson/panels/GamePanel.vue'
import { useLessonStore } from '@/store/lesson'

const route = useRoute()
const store = useLessonStore()

const activeTab = ref('overview')

const tabs = [
  { id: 'overview', name: '课程概览', icon: HomeFilled },
  { id: 'lesson_plan', name: '教案', icon: Files },
  { id: 'ppt', name: 'PPT 课件', icon: Document },
  { id: 'animation', name: '动画演示', icon: VideoCamera },
  { id: 'game', name: '互动游戏', icon: TrophyBase }
]

const panels = {
  overview: OverviewPanel,
  lesson_plan: LessonPlanPanel,
  ppt: PptPanel,
  animation: AnimationPanel,
  game: GamePanel
}
const currentPanel = computed(() => panels[activeTab.value] || OverviewPanel)

function statusOf(id) {
  if (id === 'overview') return ''
  return store.artifacts[id]?.status || 'idle'
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
    // 历史作品点"在工作台打开"：按课程 ID 直接切换过去
    if (q.lesson) {
      await store.switchTask(String(q.lesson))
      return
    }
    if (q.topic || q.subject) store.applyQuery(q)
  },
  { immediate: true }
)

// 启动时先渲染本地存档，再异步用后端台账覆盖 —— 顺序反了会白屏等网络。
// 台账是权威来源：换浏览器/清缓存后，只要有 taskId 就能把这一节课找回来。
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
  max-width: 1440px;
  margin: 0 auto;
  padding: 20px 24px 32px;
}

.wb-body {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.wb-rail {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: rgba(10, 14, 39, 0.72);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 14px;
  position: sticky;
  top: 12px;
}

.rail-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 14px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.66);
  font-size: 14px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 200, 255, 0.08);
    color: #fff;
  }

  &.active {
    background: rgba(0, 200, 255, 0.14);
    border-color: rgba(0, 200, 255, 0.4);
    color: #fff;
  }

  .rail-name { flex: 1; }
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

.rail-foot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);

  .rail-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 6px 4px 14px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.35);
  }

  .rail-empty {
    padding: 4px 14px 8px;
    font-size: 12px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.28);
  }
}

.rail-recent {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 14px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 200, 255, 0.08);
    color: #fff;
  }

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

  .rr-meta {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.35);
  }
}

.wb-work {
  min-width: 0;
  padding: 22px;
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 16px;
}

@media (max-width: 1080px) {
  .wb-body { grid-template-columns: 1fr; }

  .wb-rail {
    position: static;
    flex-direction: row;
    flex-wrap: wrap;

    .rail-item { width: auto; }
    .rail-foot { flex-direction: row; margin-top: 0; padding-top: 0; border-top: none; }
  }
}

@media (max-width: 720px) {
  .workbench { padding: 14px 12px 24px; gap: 14px; }
  .wb-work { padding: 16px 14px; }
}
</style>
