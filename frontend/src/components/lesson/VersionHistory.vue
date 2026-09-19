<template>
  <div class="version-bar">
    <div class="vb-head">
      <span class="vb-title">版本</span>
      <el-tag v-if="current" size="small" type="success" effect="plain">当前 v{{ current }}</el-tag>
      <el-tag v-else size="small" type="info" effect="plain">还没有版本</el-tag>
      <span v-if="!store.taskId" class="vb-warn">课程未同步到后端，版本历史不可用</span>
    </div>

    <!--
      这里**故意不再放第二个输入框**。
      改内容只需要一条路：主对话。同一个功能摆两处，教师不知道该用哪个，
      而且两边的判定规则（chatAction 的改/生成分流）早晚会走偏。
      版本历史与"回退"是对话里没有的能力，所以留在面板上。
    -->
    <p class="vb-hint">
      要改内容，在左边对话里说一句就行 —— 例如「导入环节太抽象，换成煮饺子的例子」，
      只会改那一处，并自动记为一版。
    </p>

    <ul v-if="log.length" class="vb-log">
      <li v-for="(item, i) in log" :key="i">{{ item }}</li>
    </ul>

    <el-collapse v-if="versions.length > 1" class="vb-history">
      <el-collapse-item :title="`历史 ${versions.length} 个版本（可回退）`">
        <ul class="vb-versions">
          <li v-for="v in versions" :key="v.version">
            <span class="rv-no">v{{ v.version }}</span>
            <span class="rv-note" :title="v.note">{{ v.note || '（无说明）' }}</span>
            <span class="rv-time">{{ timeOf(v) }}</span>
            <el-button
              v-if="v.version !== current"
              link
              type="primary"
              size="small"
              :disabled="busy"
              @click="revert(v.version)"
            >
              回到这版
            </el-button>
            <el-tag v-else size="small" type="success" effect="plain">当前</el-tag>
          </li>
        </ul>
      </el-collapse-item>
    </el-collapse>

    <p v-else-if="current" class="vb-hint vb-dim">
      改动会记为新版本（历史不删除），这里就会出现可以回退的列表。
    </p>
  </div>
</template>

<script setup>
/**
 * 成品的版本历史与回退。
 *
 * 原本这里还带一个"说一句要改什么"的输入框，与主对话框重复 —— 已移除。
 * 现在它只负责对话做不到的事：**列出历史版本、回退到任意一版**。
 * 改内容本身走主对话（`LessonChat` → `emit('revise')`），
 * 那边有一套可解释的"改/生成"分流规则，不该有第二条路径。
 *
 * 只做交互与展示，不碰生成链路；回退完成后通过 `revised` 事件把新链接交回上层。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useLessonStore } from '@/store/lesson'
import { listVersions, revertVersion, contextPayload } from '@/api/lessonArtifacts'

const props = defineProps({
  kind: { type: String, required: true }
})

const emit = defineEmits(['revised'])

const store = useLessonStore()
const versions = ref([])
const busy = ref(false)
const log = ref([])

const current = computed(() => {
  const list = versions.value
  return list.length ? Number(list[list.length - 1].version || 0) : 0
})

function timeOf(v) {
  const ts = Number(v.timestamp || 0)
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  if (!store.taskId) {
    versions.value = []
    return
  }
  try {
    versions.value = (await listVersions(store.taskId, props.kind)).versions
  } catch (e) {
    // 版本历史读不出来不该挡住生成与修改，静默降级为"没有历史"
    versions.value = []
  }
}

async function revert(version) {
  try {
    await ElMessageBox.confirm(
      `会把教案内容恢复到 v${version}，并记为新版本（历史不会被删除）。继续？`,
      '回退版本',
      { type: 'warning' }
    )
  } catch {
    return
  }
  busy.value = true
  try {
    const out = await revertVersion({
      lessonId: store.taskId, kind: props.kind, version, ctx: contextPayload(store)
    })
    log.value = [`已回退到 v${version}`]
    ElMessage.success(out.message || `已回退到 v${version}`)
    emit('revised', out)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '回退失败')
  } finally {
    busy.value = false
  }
}

onMounted(load)
// 也盯产物时间戳：对话里改完一版，store 会更新 at，但 taskId 没变，
// 只盯 taskId 的话这里会一直显示改之前的历史。
watch(() => [store.taskId, store.artifacts[props.kind]?.at], load)
</script>

<style lang="scss" scoped>
.version-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.vb-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);

  .vb-title {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.75);
  }

  .vb-warn { color: #e6a23c; }
}

.vb-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(0, 200, 255, 0.72);

  &.vb-dim { color: rgba(255, 255, 255, 0.35); }
}

.vb-log {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
}

.vb-history {
  :deep(.el-collapse-item__header) {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
  }
}

.vb-versions {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.65);
  }

  .rv-no {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
    min-width: 32px;
  }

  .rv-note {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rv-time { color: rgba(255, 255, 255, 0.35); }
}
</style>
