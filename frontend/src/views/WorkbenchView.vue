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

        <div class="rail-foot">
          <router-link to="/knowledge" class="rail-link">
            <el-icon :size="16"><Collection /></el-icon> 知识库
          </router-link>
          <router-link to="/history" class="rail-link">
            <el-icon :size="16"><Clock /></el-icon> 历史作品
          </router-link>
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
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Files, Document, VideoCamera, TrophyBase, Collection, Clock
} from '@element-plus/icons-vue'
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

// 从对话页带 query 跳过来时（/?topic=...）填进这一节课。
// 用 watch 而不是 onMounted：本页被 keep-alive 缓存，"已访问过工作台 → 去对话 → 再回来"
// 这条路径不会重新触发 onMounted，只靠它会静默丢掉传过来的主题。
watch(
  () => route.query,
  (q) => {
    if (q && (q.topic || q.subject)) store.applyQuery(q)
  },
  { immediate: true }
)
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

  .rail-link {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 8px;
    color: rgba(255, 255, 255, 0.45);
    font-size: 13px;
    text-decoration: none;

    &:hover {
      background: rgba(0, 200, 255, 0.08);
      color: #fff;
    }
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
