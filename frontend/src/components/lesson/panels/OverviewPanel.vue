<template>
  <section class="overview">
    <header class="ov-head">
      <h2>这节课的备课进度</h2>
      <p>
        已生成 {{ store.doneCount }} / {{ ARTIFACTS.length }} 项。
        四类产物共用顶部的课程信息，任何一项失败都不影响其他项。
      </p>
    </header>

    <div class="ov-batch">
      <div class="ov-checks">
        <el-checkbox
          v-for="a in ARTIFACTS"
          :key="a.id"
          v-model="selected[a.id]"
          :disabled="batchRunning"
        >{{ a.name }}</el-checkbox>
      </div>
      <el-button
        type="primary"
        size="large"
        :loading="batchRunning"
        :disabled="!store.ready || !selectedCount"
        @click="runBatch"
      >
        <el-icon><MagicStick /></el-icon>
        批量生成（{{ selectedCount }} 项）
      </el-button>
    </div>

    <div v-if="batchRunning || batchReport.length" class="ov-report">
      <div v-for="row in batchReport" :key="row.id" class="ov-row">
        <el-icon v-if="row.state === 'done'" color="#00ff88"><CircleCheckFilled /></el-icon>
        <el-icon v-else-if="row.state === 'failed'" color="#ff6b6b"><CircleCloseFilled /></el-icon>
        <el-icon v-else-if="row.state === 'running'" class="is-loading"><Loading /></el-icon>
        <el-icon v-else color="#6b7280"><Clock /></el-icon>
        <span class="ov-name">{{ row.name }}</span>
        <span class="ov-msg">{{ row.message }}</span>
      </div>
    </div>

    <div class="ov-cards">
      <ArtifactCard
        v-for="a in ARTIFACTS"
        :key="a.id"
        :type-id="a.id"
        :artifact="store.artifacts[a.id]"
        :can-generate="store.ready"
        @generate="generateOne(a.id)"
      />
    </div>

    <p class="ov-foot">
      <el-tag v-if="store.taskId" type="success" size="small" effect="plain">
        已记入本机台账
      </el-tag>
      <el-tag v-else-if="store.ready" type="info" size="small" effect="plain">
        填写主题后自动建课
      </el-tag>
      <span v-if="store.taskId">
        刷新、换浏览器后凭台账找回这一节课；文件本身仍在后端，也可到「历史作品」重新下载。
      </span>
      <span v-else>
        台账按主题建立，用于把四类产物归到同一节课下。
      </span>
    </p>
  </section>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, CircleCheckFilled, CircleCloseFilled, Loading, Clock } from '@element-plus/icons-vue'
import ArtifactCard from '../ArtifactCard.vue'
import { useLessonStore, ARTIFACTS } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import {
  generateLessonPlan, generatePpt, generateAnimation, generateGame,
  contextPayload, assertContext
} from '@/api/lessonArtifacts'

const store = useLessonStore()

const runners = {
  lesson_plan: useArtifactRunner('lesson_plan'),
  ppt: useArtifactRunner('ppt'),
  animation: useArtifactRunner('animation'),
  game: useArtifactRunner('game')
}

const selected = reactive(
  ARTIFACTS.reduce((acc, a) => { acc[a.id] = true; return acc }, {})
)
const selectedCount = computed(() => ARTIFACTS.filter(a => selected[a.id]).length)
const batchRunning = ref(false)
const batchReport = ref([])

function taskFor(id) {
  const ctx = contextPayload(store)
  if (id === 'lesson_plan') return (setHint) => (setHint('正在生成教案'), generateLessonPlan(ctx))
  if (id === 'ppt') return (setHint) => generatePpt(ctx, {
    themeColor: store.pptTheme,
    onProgress: (value, step) => setHint(step ? `${step}（${value}%）` : `已完成 ${value}%`)
  })
  if (id === 'animation') return () => generateAnimation(ctx, { minutes: store.animationMinutes })
  if (id === 'game') return () => generateGame(ctx, { gameType: store.gameType })
  return () => Promise.reject(new Error('未知产物类型'))
}

async function generateOne(id) {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  const ok = await runners[id].run(taskFor(id))
  if (ok) ElMessage.success('生成完成')
}

async function runBatch() {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  const ids = ARTIFACTS.filter(a => selected[a.id]).map(a => a.id)
  batchRunning.value = true
  batchReport.value = ids.map(id => ({
    id,
    name: ARTIFACTS.find(a => a.id === id).name,
    state: 'pending',
    message: '排队中'
  }))

  let failed = 0
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i]
    const row = batchReport.value[i]
    row.state = 'running'
    row.message = '生成中'
    const ok = await runners[id].run(taskFor(id))
    row.state = ok ? 'done' : 'failed'
    row.message = ok ? '已完成' : (store.artifacts[id].error || '失败')
    if (!ok) failed++
  }

  batchRunning.value = false
  if (failed) ElMessage.warning(`${ids.length - failed} 项完成，${failed} 项失败，可单独重试`)
  else ElMessage.success(`${ids.length} 项全部生成完成`)
}
</script>

<style lang="scss" scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ov-head {
  h2 {
    font-size: 20px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 6px;
  }

  p {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.6;
  }
}

.ov-batch {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px;
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.12);
  border-radius: 12px;

  .ov-checks {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    flex: 1;
  }
}

.ov-report {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  background: rgba(0, 200, 255, 0.05);
  border: 1px solid rgba(0, 200, 255, 0.18);
  border-radius: 12px;

  .ov-row {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;

    .ov-name { color: #fff; min-width: 72px; }
    .ov-msg { color: rgba(255, 255, 255, 0.5); }
  }
}

.ov-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ov-foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.32);
}
</style>
