<template>
  <section class="gen" aria-label="通用问答">
    <div class="gen__head">
      <el-select v-model="mode" size="small" style="width: 148px" aria-label="问答模式">
        <el-option v-for="m in CHAT_MODES" :key="m.value" :label="m.label" :value="m.value" />
      </el-select>
      <span class="gen__hint">{{ modeHint }}</span>
      <el-checkbox v-model="useKnowledge" size="small">用知识库</el-checkbox>
      <el-select
        v-model="attachments"
        multiple
        collapse-tags
        collapse-tags-tooltip
        size="small"
        placeholder="附件"
        style="width: 160px"
      >
        <el-option v-for="f in files" :key="f.file_id" :label="f.filename" :value="f.file_id" />
      </el-select>
      <el-button size="small" text @click="onClear">清空</el-button>
    </div>

    <div ref="scroller" class="gen__log" aria-live="polite">
      <EmptyState
        v-if="!messages.length"
        title="开始一段通用问答"
        description="这里不绑定任何备课任务，适合临时问概念、查资料。要备一整节课，请切回「当前备课」。"
        icon="ChatDotRound"
      >
        <template #action>
          <div class="wb-row">
            <el-button v-for="ex in EXAMPLES" :key="ex" size="small" @click="draft = ex">
              {{ ex }}
            </el-button>
          </div>
        </template>
      </EmptyState>

      <div v-for="(m, i) in messages" :key="i" class="msg" :class="`msg--${m.role}`">
        <div class="msg__bubble">
          <div v-if="m.role === 'assistant' && m.md" class="msg__md" v-html="m.html" />
          <span v-else class="msg__text">{{ m.content }}</span>
        </div>
      </div>

      <div v-if="thinking" class="msg msg--assistant">
        <div class="msg__bubble msg__bubble--typing"><span /><span /><span /></div>
      </div>
    </div>

    <p v-if="notice" class="gen__notice">{{ notice }}</p>

    <div class="gen__input">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入内容，Enter 发送，Shift + Enter 换行"
        @keydown.enter.exact.prevent="onSend"
      />
      <div class="gen__foot">
        <span class="gen__foot-hint">{{ footHint }}</span>
        <el-button v-if="thinking" @click="onStop">停止</el-button>
        <el-button type="primary" :loading="thinking" :disabled="!draft.trim()" @click="onSend">
          发送
        </el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChatDotRound } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { CHAT_MODES, streamChat, fetchHistory, saveHistory } from '@/api/chat'
import { listUploadedFiles } from '@/api/upload'
import { formatMessage } from '@/utils/markdown'
import { notifyError } from '@/utils/notify'

/**
 * 通用问答（不绑定备课任务）。
 *
 * 与工作台对话的分工写死在这里，两边都不要越界：
 *   - 工作台走 `/lesson-chat/ask`，**带**这一节课的学科/年级/主题/蓝图/产物语境；
 *   - 这里走 `/chat/*`，**不带**任何备课语境。
 * 两条是各自独立的后端链路，本项目刻意不合并 —— 合并要么让备课问答丢语境，
 * 要么让临时提问被强塞一门课。所以这里是独立组件，由工作台"模式切换"按需挂载，
 * 而不是把两套状态塞进同一个聊天数组里。
 */
const props = defineProps({
  /** 会话 id；由父级（页面或工作台）持有，切换会话即切换历史 */
  convId: { type: String, default: '' }
})

const EXAMPLES = [
  '怎么给学生讲清楚浮力的本质？',
  '这份练习题的难度梯度合理吗？',
  '帮我查一下项目式学习的研究'
]

const messages = ref([])
const draft = ref('')
const thinking = ref(false)
const mode = ref('stream')
const useKnowledge = ref(true)
const attachments = ref([])
const files = ref([])
const scroller = ref(null)
const notice = ref('')

let controller = null

const modeHint = computed(() => CHAT_MODES.find(m => m.value === mode.value)?.hint || '')
const footHint = computed(() => (['search', 'deep-search'].includes(mode.value)
  ? '联网模式需要能访问外网；不通时后端会如实说明，不会假装查过'
  : ''))

function decorate(m) {
  const role = m.role === 'user' ? 'user' : 'assistant'
  const content = String(m.content || '')
  return { role, content, md: role === 'assistant', html: role === 'assistant' ? formatMessage(content) : '' }
}

function scrollToBottom() {
  nextTick(() => {
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadHistory() {
  if (!props.convId) { messages.value = []; return }
  messages.value = (await fetchHistory(props.convId)).map(decorate)
  scrollToBottom()
}

function onClear() {
  messages.value = []
  draft.value = ''
  notice.value = ''
}

async function onSend() {
  const text = draft.value.trim()
  if (!text || thinking.value) return
  draft.value = ''
  notice.value = ''

  messages.value.push({ role: 'user', content: text, md: false, html: '' })
  const reply = { role: 'assistant', content: '', md: true, html: '' }
  messages.value.push(reply)
  scrollToBottom()

  thinking.value = true
  controller = new AbortController()
  try {
    await streamChat({
      mode: mode.value,
      message: text,
      history: messages.value.slice(0, -2)
        .filter(m => m.content)
        .map(m => ({ role: m.role, content: m.content })),
      conversationId: props.convId,
      useKnowledge: useKnowledge.value,
      attachmentIds: attachments.value.slice(),
      signal: controller.signal,
      onDelta: txt => {
        reply.content = txt
        reply.html = formatMessage(txt)
        scrollToBottom()
      }
    })
    if (props.convId) {
      await saveHistory(props.convId, messages.value.filter(m => m.content)
        .map(m => ({ role: m.role, content: m.content })))
    }
  } catch (e) {
    // 主动中断不算失败，保留已输出的部分
    if (e?.name !== 'AbortError') {
      reply.content = `（生成失败：${e?.message || '服务未响应'}）`
      reply.html = formatMessage(reply.content)
      notifyError(e?.message || '生成失败')
    }
  } finally {
    thinking.value = false
    controller = null
  }
}

function onStop() {
  controller?.abort()
  thinking.value = false
}

watch(mode, () => {
  if (['search', 'deep-search'].includes(mode.value)) useKnowledge.value = true
})

watch(() => props.convId, loadHistory)

onMounted(async () => {
  try { files.value = await listUploadedFiles() } catch { files.value = [] }
  await loadHistory()
})
</script>

<style scoped>
.gen {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.gen__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--wb-border);
}

.gen__hint {
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  flex: 1 1 auto;
  min-width: 0;
}

.gen__log {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.gen__notice {
  margin: 0;
  padding: var(--sp-2) var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--wb-warn-text);
  background: var(--wb-warn-bg);
}

.gen__input {
  border-top: 1px solid var(--wb-border);
  padding: var(--sp-3);
}

.gen__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

.gen__foot-hint {
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
}

.msg { display: flex; }
.msg--user { justify-content: flex-end; }

.msg__bubble {
  max-width: 78%;
  padding: var(--sp-3);
  border-radius: var(--radius-md);
  background: var(--wb-surface-2);
  font-size: var(--fs-sm);
  line-height: 1.75;
  word-break: break-word;
}

.msg--user .msg__bubble {
  background: var(--brand-soft-2);
  color: var(--wb-text);
}

.msg__md :deep(p) { margin: 0 0 var(--sp-2); }
.msg__md :deep(p:last-child) { margin-bottom: 0; }
.msg__md :deep(pre) {
  background: var(--wb-code-bg);
  padding: var(--sp-2);
  border-radius: var(--radius-sm);
  overflow-x: auto;
}
.msg__md :deep(code) { font-family: var(--font-mono); font-size: var(--fs-xs); }
.msg__md :deep(th),
.msg__md :deep(td) { border: 1px solid var(--wb-border); padding: 4px 8px; }

.msg__bubble--typing { display: flex; gap: 4px; align-items: center; }

.msg__bubble--typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--wb-text-3);
  animation: blink 1.2s infinite ease-in-out;
}

.msg__bubble--typing span:nth-child(2) { animation-delay: 0.2s; }
.msg__bubble--typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 60%, 100% { opacity: 0.25; }
  30% { opacity: 1; }
}
</style>
