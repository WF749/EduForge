<template>
  <div class="revise-bar">
    <div class="rb-head">
      <span class="rb-title">迭代</span>
      <el-tag v-if="current" size="small" type="success" effect="plain">当前 v{{ current }}</el-tag>
      <el-tag v-else size="small" type="info" effect="plain">还没有版本</el-tag>
      <span v-if="!store.taskId" class="rb-warn">课程未同步到后端，迭代不可用</span>
    </div>

    <div class="rb-input">
      <el-input
        v-model="instruction"
        :placeholder="placeholder"
        :disabled="!canRevise"
        maxlength="120"
        clearable
        @keyup.enter="submit"
      />
      <el-button type="primary" :loading="busy" :disabled="!canRevise || !instruction.trim()" @click="submit">
        按这句改
      </el-button>
    </div>

    <ul v-if="log.length" class="rb-log">
      <li v-for="(item, i) in log" :key="i">{{ item }}</li>
    </ul>

    <el-collapse v-if="versions.length > 1" class="rb-history">
      <el-collapse-item :title="`历史 ${versions.length} 个版本（可回退）`">
        <ul class="rb-versions">
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
  </div>
</template>

<script setup>
/**
 * 成品的迭代条：一句话指令修改 + 版本历史 + 回退。
 *
 * 只做交互与展示，不碰生成链路；改完之后通过 `revised` 事件把新的下载链接交回上层，
 * 由上层决定怎么更新产物卡片。这样动画/游戏以后接同一套版本机制时可以直接复用。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useLessonStore } from '@/store/lesson'
import { listVersions, reviseLessonPlan, revertVersion, contextPayload } from '@/api/lessonArtifacts'

const props = defineProps({
  kind: { type: String, required: true },
  placeholder: {
    type: String,
    default: '说一句要改什么，例如「导入环节太抽象，换成煮饺子的例子」'
  }
})

const emit = defineEmits(['revised'])

const store = useLessonStore()
const versions = ref([])
const instruction = ref('')
const busy = ref(false)
const log = ref([])

const current = computed(() => {
  const list = versions.value
  return list.length ? Number(list[list.length - 1].version || 0) : 0
})
// 没生成过（无版本）就不能改 —— 后端也会拒绝，这里提前禁用省得白点一次
const canRevise = computed(() => Boolean(store.taskId) && current.value > 0 && !busy.value)

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

function ctx() {
  return contextPayload(store)
}

async function submit() {
  const text = instruction.value.trim()
  if (!text || !canRevise.value) return
  busy.value = true
  log.value = []
  try {
    const out = await reviseLessonPlan({ lessonId: store.taskId, instruction: text, ctx: ctx() })
    instruction.value = ''
    log.value = out.changeLog.length ? out.changeLog : [`已记为 v${out.version?.version ?? '?'}`]
    ElMessage.success(out.message || '已按指令修改')
    emit('revised', out)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '修改失败')
  } finally {
    busy.value = false
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
      lessonId: store.taskId, kind: props.kind, version, ctx: ctx()
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
watch(() => store.taskId, load)
</script>

<style lang="scss" scoped>
.revise-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.rb-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);

  .rb-title {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.75);
  }

  .rb-warn {
    color: #e6a23c;
  }
}

.rb-input {
  display: flex;
  gap: 8px;
  width: 100%;
}

.rb-log {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
}

.rb-history {
  :deep(.el-collapse-item__header) {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
  }
}

.rb-versions {
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

  .rv-time {
    color: rgba(255, 255, 255, 0.35);
  }
}
</style>
