<template>
  <section class="lesson-chat">
    <header class="lc-head">
      <span class="lc-title">备课对话</span>
      <el-button text size="small" @click="clear">清空</el-button>
    </header>

    <div ref="scroller" class="lc-log">
      <p v-if="!messages.length" class="lc-empty">
        直接说要做什么。<br />
        例：<b>生成一份浮力教案</b><br />
        生成后可以说 <b>导入环节太抽象，换成煮饺子的例子</b> ——
        只会改那一处，并留下一版可回退。
      </p>

      <div v-for="(m, i) in messages" :key="i" class="lc-msg" :class="`is-${m.role}`">
        <div class="lc-bubble">
          {{ m.text }}
          <span v-if="m.hint" class="lc-hint">{{ m.hint }}</span>
        </div>
        <div v-if="m.chips && m.chips.length" class="lc-chips">
          <button v-for="c in m.chips" :key="c" type="button" class="lc-chip" @click="send(c)">
            {{ c }}
          </button>
        </div>
      </div>

      <div v-if="thinking" class="lc-msg is-agent">
        <div class="lc-bubble lc-typing">正在思考…</div>
      </div>
    </div>

    <div class="lc-quick">
      <button
        v-for="q in quickActions"
        :key="q.label"
        type="button"
        class="lc-chip"
        :disabled="busy"
        @click="quick(q)"
      >
        {{ q.label }}
      </button>
    </div>

    <div class="lc-input">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        resize="none"
        maxlength="300"
        placeholder="说一句要做什么，回车发送"
        @keydown.enter.exact.prevent="send()"
      />
      <el-button type="primary" :loading="thinking" :disabled="thinking || !draft.trim()" @click="send()">
        发送
      </el-button>
    </div>
  </section>
</template>

<script setup>
/**
 * 课程内嵌对话：把教师的一句话变成动作。
 *
 * 分工刻意为之：
 *  - 「这句话是什么意思」由 chatAction.js 的纯规则判定（不调模型、毫秒级、可测试）；
 *  - 只有规则判不出来（提问、需求描述）才交给后端对话管理器去澄清追问；
 *  - 生成与修改**不由本组件直接调接口**，而是 emit 给工作台——
 *    因为生成的状态机在 useArtifactRunner 里，工作台持有它，面板上的进度条才不会各说各话。
 *
 * 不做成通用聊天：这里每句话都应该指向"这一节课要产出什么"，
 * 纯粹的闲聊/知识问答仍走 /chat 那个对话页。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useLessonStore } from '@/store/lesson'
import { detectKind, routeUserMessage } from '@/utils/chatAction'
import { fieldLabels } from '@/utils/dialogueFields'
import { postDialogue, resetDialogue } from '@/api/lessonChat'
import { listVersions } from '@/api/lessonArtifacts'

const props = defineProps({
  activeKind: { type: String, default: 'lesson_plan' },
  // 哪些成品支持"按指令修改"。目前只有教案，其余要如实说明而不是假装能改。
  reviseKinds: { type: Array, default: () => ['lesson_plan'] },
  busy: { type: Boolean, default: false }
})

const emit = defineEmits(['generate', 'revise', 'switch-kind'])

const store = useLessonStore()
const messages = ref([])
const draft = ref('')
const thinking = ref(false)
const scroller = ref(null)
const currentVersion = ref(0)

const conversationId = computed(() => `lesson-${store.taskId || 'local'}`)
const reviseSupported = computed(() => props.reviseKinds.includes(props.activeKind))

const quickActions = [
  { label: '生成教案', action: 'generate', kind: 'lesson_plan' },
  { label: '生成 PPT', action: 'generate', kind: 'ppt' },
  { label: '生成动画', action: 'generate', kind: 'animation' },
  { label: '生成游戏', action: 'generate', kind: 'game' }
]

const KIND_NAME = {
  lesson_plan: '教案', ppt: 'PPT', animation: '动画', game: '游戏'
}

function push(role, text, chips = [], hint = '') {
  messages.value.push({ role, text, chips, hint })
  nextTick(scrollToBottom)
}

function scrollToBottom() {
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

async function clear() {
  messages.value = []
  // 后端上下文也得清：否则本地清空了，服务端还停在"等你确认"的状态
  try {
    await resetDialogue(conversationId.value)
  } catch {
    // 重置失败不影响本地继续用，最多是追问节奏对不上
  }
}

async function refreshVersion() {
  if (!store.taskId || !reviseSupported.value) {
    currentVersion.value = 0
    return
  }
  try {
    currentVersion.value = (await listVersions(store.taskId, props.activeKind)).current
  } catch {
    currentVersion.value = 0
  }
}

/** 把判定结果翻译成对话里的一句话 + 实际动作 */
function dispatch(text, route) {
  const kindName = KIND_NAME[route.kind] || '成品'
  if (route.kind !== props.activeKind) emit('switch-kind', route.kind)

  if (route.action === 'generate') {
    push('agent', `好的，开始生成${kindName}。右侧会显示进度，完成后可以直接下载。`)
    emit('generate', route.kind)
    return
  }

  if (route.action === 'revise') {
    if (!reviseSupported.value) {
      push('agent', `现在只有教案支持"按指令修改"，${kindName}还不行。要调整的话请重新生成，或直接去 /chat 里让我帮你改内容。`)
      return
    }
    if (route.blocked) {
      push('agent', `${route.blocked}。要不要我先生成一份？`, ['生成教案'])
      return
    }
    push('agent', `按这句改${kindName}：「${text}」。改完会记为新版本，不满意可以回退。`)
    emit('revise', { kind: route.kind, instruction: text })
    return
  }

  // 规则判不出来 → 交给后端对话管理器澄清。这是唯一会调模型的一条路。
  chatFallback(text)
}

/** 后端说的"意图"能不能落到某一种成品上；落不到就老实聊天，不硬凑 */
function kindFromResult(r) {
  if (r.intentType === 'course_design') return 'lesson_plan'
  if (r.intentType === 'resource_generation') {
    return detectKind(String(r.fields.resource_type || '')) || null
  }
  return null
}

function requestGenerate(kind) {
  if (kind !== props.activeKind) emit('switch-kind', kind)
  emit('generate', kind)
}

async function chatFallback(text) {
  thinking.value = true
  try {
    const r = await postDialogue(conversationId.value, text)

    // 澄清：把"还缺什么"明说出来，同时留一个直接开干的出口 —— 追问不能把人卡死
    if (r.action === 'clarify') {
      // 后端 message 常常只是一句"请提供更多信息。"，真正有用的信息在缺字段里
      const missing = fieldLabels(r.missingFields)
      push(
        'agent',
        r.message || '还差一点信息才能开始。',
        ['生成教案'],
        missing.length ? `还缺：${missing.join('、')}` : ''
      )
      return
    }

    // 确认：把"确认/取消"做成按钮，别让教师猜该回哪个词
    if (r.action === 'confirm') {
      push('agent', r.message || '请确认我理解得对不对。', ['确认', '取消'])
      return
    }

    if (r.action === 'reset') {
      push('agent', r.message || '好的，请重新描述你的需求。')
      return
    }

    // 执行：确认过的直接开做；没确认过的只给入口，不能说"我已经做了"
    const kind = kindFromResult(r)
    if (r.confirmed && kind) {
      push('agent', `确认收到，开始生成${KIND_NAME[kind]}。右侧会显示进度。`)
      requestGenerate(kind)
      return
    }

    if (r.message) {
      push('agent', r.message, r.suggestions.slice(0, 3))
      return
    }

    // 后端判定"可以直接执行"但没话要说，如实告知而不是编一句
    push('agent', '我理解了你的需求。你可以直接说要生成什么，例如「生成教案」。',
      ['生成教案', '生成 PPT'])
  } catch (e) {
    push('agent', `对话服务没响应：${e.message}。你可以直接说要生成什么，我照样能做。`,
      ['生成教案'])
  } finally {
    thinking.value = false
  }
}

function send(text) {
  const content = String(text ?? draft.value).trim()
  if (!content || thinking.value) return
  draft.value = ''

  const route = routeUserMessage(content, {
    hasVersion: reviseSupported.value && currentVersion.value > 0,
    activeKind: props.activeKind
  })
  push('user', content)
  dispatch(content, route)
}

function quick(q) {
  emit('switch-kind', q.kind)
  push('user', q.label)
  push('agent', `好的，开始生成${KIND_NAME[q.kind]}。`)
  emit('generate', q.kind)
}

onMounted(refreshVersion)
watch(() => [store.taskId, props.activeKind], refreshVersion)
</script>

<style lang="scss" scoped>
.lesson-chat {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  padding: 14px;
  background: rgba(10, 14, 39, 0.72);
  border: 1px solid rgba(0, 200, 255, 0.14);
  border-radius: 14px;
}

.lc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .lc-title {
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.8);
  }
}

.lc-log {
  flex: 1;
  min-height: 240px;
  max-height: 46vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}

.lc-empty {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.38);

  b { color: rgba(0, 200, 255, 0.75); font-weight: 600; }
}

.lc-msg {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 92%;

  &.is-user { align-self: flex-end; align-items: flex-end; }
  &.is-agent { align-self: flex-start; }
}

.lc-bubble {
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.65;
  border-radius: 10px;
  white-space: pre-wrap;
  word-break: break-word;

  .is-user & {
    background: rgba(0, 200, 255, 0.18);
    border: 1px solid rgba(0, 200, 255, 0.32);
    color: #fff;
  }

  .is-agent & {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.82);
  }
}

.lc-typing { color: rgba(255, 255, 255, 0.45); font-size: 12px; }

.lc-hint {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: rgba(0, 200, 255, 0.7);
}

.lc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lc-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.lc-chip {
  padding: 5px 10px;
  font-size: 12px;
  font-family: inherit;
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    color: #fff;
    background: rgba(0, 200, 255, 0.14);
    border-color: rgba(0, 200, 255, 0.36);
  }

  &:disabled { opacity: 0.45; cursor: not-allowed; }
}

.lc-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
</style>
