<template>
  <section class="lesson-chat">
    <header class="lc-head">
      <div class="lc-head-main">
        <span class="lc-title">备课对话</span>
        <span class="lc-sub">能生成四类成品，也能直接问知识点、问教法</span>
      </div>
      <div class="lc-head-tools">
        <!--
          上下文透明：教师有权知道"它记住了什么、每轮到底把什么发给了模型"。
          放一个按钮而不是写一段说明 —— 说明会过时，原文不会。
        -->
        <el-button text size="small" :icon="View" @click="ctxOpen = true">
          智能体知道的事
        </el-button>
        <label class="lc-kb" :title="useKnowledge ? '回答时会先查你的知识库' : '只用模型自身知识回答'">
          <el-switch v-model="useKnowledge" size="small" />
          <span>知识库</span>
        </label>
        <el-button text size="small" @click="clear">清空</el-button>
      </div>
    </header>

    <LessonContextDrawer
      v-model="ctxOpen"
      :message-count="memoryCount"
      :lesson="lessonPayload()"
    />

    <div ref="scroller" class="lc-log">
      <div v-if="!messages.length" class="lc-empty">
        <p class="lc-empty-lead">这节课的智能体，你可以 ——</p>
        <button type="button" class="lc-empty-item" @click="send('什么是三角函数')">
          <b>直接问</b><span>什么是三角函数</span>
        </button>
        <button type="button" class="lc-empty-item" @click="send('学生总把 k 和 b 搞混，怎么讲比较好？')">
          <b>问教法</b><span>学生总把 k 和 b 搞混，怎么讲</span>
        </button>
        <button type="button" class="lc-empty-item" @click="send('生成一份浮力教案')">
          <b>要做成品</b><span>生成一份浮力教案</span>
        </button>
        <button type="button" class="lc-empty-item" @click="send('导入环节太抽象，换成煮饺子的例子')">
          <b>要改</b><span>导入环节太抽象，换成煮饺子的例子</span>
        </button>

        <!--
          手动设置的入口必须长在这里。
          它在"用户一定会看的那块屏幕区域"里 —— 顶部的课程信息条虽然也能编辑，
          但那条长得像标题栏，新手不会去点它（实测反馈）。
          所以引导放在对话流里，顶部只做"已填好之后的摘要"。
        -->
        <div class="lc-empty-setup">
          <span>不想打字？也可以手动设置主题、学科和年级</span>
          <button type="button" class="lc-empty-setup-btn" @click="emit('open-context')">
            设置这节课信息
          </button>
        </div>
      </div>

      <div
        v-for="(m, i) in messages"
        :key="i"
        class="lc-msg"
        :class="`is-${m.role}`"
      >
        <!-- 产物卡片直接出现在对话流里：这是"以对话为主"的关键 —— 老师不用去右边找 -->
        <div v-if="m.card" class="lc-card" :class="`lc-card-${statusOf(m.kind)}`">
          <div class="lc-card-head">
            <el-icon :size="16"><component :is="iconOf(m.kind)" /></el-icon>
            <span class="lc-card-name">{{ nameOf(m.kind) }}</span>
            <span class="lc-card-status">{{ statusText(m.kind) }}</span>
          </div>
          <p v-if="artifactError(m.kind)" class="lc-card-err">{{ artifactError(m.kind) }}</p>
          <div class="lc-card-actions">
            <el-button
              v-if="statusOf(m.kind) === 'done'"
              size="small"
              type="primary"
              @click="emit('switch-kind', m.kind)"
            >在右侧查看</el-button>
            <el-button
              v-if="statusOf(m.kind) === 'done' && artifactUrl(m.kind)"
              size="small"
              @click="openArtifact(m.kind)"
            >打开</el-button>
            <el-button
              v-if="statusOf(m.kind) === 'failed' || statusOf(m.kind) === 'idle'"
              size="small"
              type="primary"
              :disabled="busy"
              @click="requestGenerate(m.kind)"
            >{{ statusOf(m.kind) === 'failed' ? '重试' : '开始生成' }}</el-button>
          </div>
        </div>

        <template v-else>
          <div class="lc-bubble" :class="{ 'lc-bubble-md': m.md }">
            <!-- 模型回答走 Markdown（列表/公式/代码块）；它自己的提示语是纯文本，
                 不渲染 —— 否则中文里的书名号、星号会被当成标记 -->
            <div v-if="m.md" class="lc-md" v-html="formatMessage(m.text)"></div>
            <template v-else>{{ m.text }}</template>
            <span v-if="m.hint" class="lc-hint">{{ m.hint }}</span>
          </div>

          <div v-if="m.chips && m.chips.length" class="lc-chips">
            <button v-for="c in m.chips" :key="c" type="button" class="lc-chip" @click="send(c)">
              {{ c }}
            </button>
          </div>

          <div v-if="m.role === 'agent' && m.text && !m.streaming" class="lc-msg-tools">
            <button type="button" @click="copyText(m.text)">复制</button>
            <button v-if="ttsSupported" type="button" @click="toggleSpeak(m.text)">
              {{ speaking ? '停止' : '朗读' }}
            </button>
            <span v-if="m.elapsed" class="lc-elapsed">{{ m.elapsed }}s</span>
          </div>
        </template>
      </div>

      <div v-if="thinking" class="lc-msg is-agent">
        <div class="lc-bubble lc-typing">
          <span class="lc-dots"><i /><i /><i /></span>
          {{ statusText2 }}
        </div>
      </div>
    </div>

    <div class="lc-quick">
      <span class="lc-quick-label">生成</span>
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
      <!-- 这句原来写的是"先在顶部填好教学主题"，与"直接说一句话就能开始"自相矛盾：
           新手看到的是"你被拒绝了"，而实际能力是"你直接说我就懂"。
           现在改成可点的补救入口，而不是一句抱怨。 -->
      <button
        v-if="!store.ready"
        type="button"
        class="lc-quick-warn"
        @click="emit('open-context')"
      >
        还没设主题 · 点这里设置，或直接在下面说一句
      </button>
    </div>

    <div class="lc-input">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        resize="none"
        maxlength="300"
        placeholder="要生成、要修改、或者直接问 —— 回车发送，Shift+回车换行"
        @keydown.enter.exact.prevent="send()"
      />
      <el-button
        v-if="thinking"
        class="lc-send"
        type="danger"
        plain
        @click="stopAnswer"
      >停止</el-button>
      <el-button
        v-else
        class="lc-send"
        type="primary"
        :disabled="!draft.trim()"
        @click="send()"
      >发送</el-button>

      <!--
        语音：教师站在讲台边、手上拿着教具时，说话比打字快得多。
        不支持时（非 Chrome / 非 HTTPS）直接不给按钮，而不是点了才报错。
      -->
      <el-button
        v-if="sttSupported"
        :type="listening ? 'danger' : 'default'"
        :icon="Microphone"
        :title="listening ? '停止录音' : '语音输入'"
        @click="toggleVoice"
      />
    </div>
  </section>
</template>

<script setup>
/**
 * 课程内嵌对话 —— 工作台的主界面。
 *
 * 这个组件承担两类完全不同的活儿，**必须分开走**：
 *
 *  1. 「要做点什么」：由 `chatAction.js` 的纯规则判定生成 / 修改。
 *     不调模型、毫秒级、可测试 —— 且判错的代价不对称（见该文件注释）。
 *  2. 「就是问一句」：交给后端教学问答（流式）。
 *
 * 曾经只有第 1 类 + 一个状态机，于是所有提问都被当成"需求没说全"：
 * 教师问「什么是三角函数」，拿回来的是「请问您想了解什么主题的知识」，
 * 再问一句就只剩「你直接说要生成什么」。对话成了套了层壳的菜单。
 * 现在提问走真问答，且**兜底也是回答**，不再有那句话。
 *
 * 生成与修改不由本组件直接调接口，而是 emit 给工作台 ——
 * 生成的状态机在 useArtifactRunner 里，工作台持有它，面板上的进度条才不会各说各话。
 */
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, View } from '@element-plus/icons-vue'
import { Files, Document, VideoCamera, TrophyBase } from '@element-plus/icons-vue'
import { useLessonStore, SUBJECTS, GRADES } from '@/store/lesson'
import { detectKind, looksLikeQuestion, routeUserMessage } from '@/utils/chatAction'
import { applyInferred, inferLessonFields } from '@/utils/lessonIntent'
import { fieldLabels } from '@/utils/dialogueFields'
import { formatMessage } from '@/utils/markdown'
import { useSpeech } from '@/composables/useSpeech'
import LessonContextDrawer from './LessonContextDrawer.vue'
import { askLessonStream, postDialogue, resetDialogue } from '@/api/lessonChat'
import { listVersions } from '@/api/lessonArtifacts'

const props = defineProps({
  activeKind: { type: String, default: 'lesson_plan' },
  // 哪些成品支持"按指令修改"。目前只有教案，其余要如实说明而不是假装能改。
  reviseKinds: { type: Array, default: () => ['lesson_plan'] },
  busy: { type: Boolean, default: false }
})

// open-context：请父级展开顶部的课程信息条。
// 有意做成事件而不是让对话直接改 store —— 展开与否是界面状态，不是备课数据。
const emit = defineEmits(['generate', 'revise', 'switch-kind', 'open-context'])

const store = useLessonStore()
const messages = ref([])
const draft = ref('')
const thinking = ref(false)        // 正在等模型（含流式输出中）
const useKnowledge = ref(true)
const ctxOpen = ref(false)
const scroller = ref(null)
const currentVersion = ref(0)
let answerController = null

const conversationId = computed(() => `lesson-${store.taskId || 'local'}`)
/** 抽屉里"记忆"那一节要说实话：只有带正文的消息才算一轮 */
const memoryCount = computed(() => messages.value.filter((m) => !m.card && m.text).length)
const reviseSupported = computed(() => props.reviseKinds.includes(props.activeKind))

const {
  listening, speaking, sttSupported, ttsSupported,
  toggleListening, stopListening, speak, stopSpeaking
} = useSpeech()

const KIND_NAME = { lesson_plan: '教案', ppt: 'PPT', animation: '动画', game: '游戏' }
const KIND_ICON = {
  lesson_plan: Files, ppt: Document, animation: VideoCamera, game: TrophyBase
}

const quickActions = [
  { label: '生成教案', action: 'generate', kind: 'lesson_plan' },
  { label: '生成 PPT', action: 'generate', kind: 'ppt' },
  { label: '生成动画', action: 'generate', kind: 'animation' },
  { label: '生成游戏', action: 'generate', kind: 'game' }
]

/** 还没读到主题时给的例句：点了就真的能开工（主题在句子里，能被读出来） */
const ASK_TOPIC_EXAMPLES = [
  '生成一份浮力教案',
  '生成一份《细胞的结构》教案'
]

function nameOf(kind) { return KIND_NAME[kind] || '成品' }
function iconOf(kind) { return KIND_ICON[kind] || Files }
function statusOf(kind) { return store.artifacts[kind]?.status || 'idle' }
function artifactError(kind) { return store.artifacts[kind]?.error || '' }
function artifactUrl(kind) {
  const a = store.artifacts[kind] || {}
  return a.previewUrl || a.downloadUrl || ''
}

const statusText2 = computed(() => (thinking.value ? '正在思考…' : ''))

function statusText(kind) {
  return {
    idle: '还没生成',
    running: '正在生成…',
    done: '已完成',
    failed: '生成失败'
  }[statusOf(kind)] || ''
}

function push(role, text, opts = {}) {
  const msg = {
    role,
    text,
    chips: opts.chips || [],
    hint: opts.hint || '',
    md: opts.md === true,
    streaming: opts.streaming === true,
    elapsed: 0
  }
  messages.value.push(msg)
  nextTick(scrollToBottom)
  return messages.value.length - 1
}

function pushCard(kind) {
  // 同一个成品不重复插卡：连点两次生成只该有一张卡
  const exists = messages.value.some((m) => m.card && m.kind === kind)
  if (exists) return
  messages.value.push({ role: 'agent', card: true, kind })
  nextTick(scrollToBottom)
}

function scrollToBottom() {
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

function toggleVoice() {
  toggleListening({
    // 实时回灌到输入框：教师能看到自己说的话被识别成什么，错了可以手改
    onText: (text) => { draft.value = text },
    onError: (msg) => ElMessage.error(msg)
  })
}

function toggleSpeak(text) {
  speaking.value ? stopSpeaking() : speak(text || '')
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动选中')
  }
}

function openArtifact(kind) {
  const url = artifactUrl(kind)
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

async function clear() {
  stopAnswer()
  stopListening()
  stopSpeaking()
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

/** 传给后端的"这节课"是什么样：语境 + 已生成到哪一步 */
function lessonPayload() {
  const artifacts = {}
  for (const id of Object.keys(store.artifacts)) {
    artifacts[id] = store.artifacts[id]?.status || 'idle'
  }
  return {
    topic: store.topic,
    subject: store.subject,
    grade: store.grade,
    duration: store.duration,
    difficulty: store.difficulty,
    keyPoints: store.keyPoints,
    artifacts
  }
}

/** 最近几轮交给模型，让它接得住"那再举一个例子"这种追问 */
function historyPayload() {
  return messages.value
    .filter((m) => !m.card && m.text && (m.role === 'user' || m.role === 'agent'))
    .slice(-8)
    .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }))
}

function stopAnswer() {
  if (answerController) {
    answerController.abort()
    answerController = null
  }
  thinking.value = false
  // 半截的流式回答留着（已经收到的内容对教师仍有用），但去掉"正在输入"标记
  const last = messages.value[messages.value.length - 1]
  if (last && last.streaming) last.streaming = false
}

/**
 * 真的去回答问题。这是这次改造补上的那一半能力。
 *
 * 失败时如实说失败，并且**给出下一步**（生成按钮仍然可用），
 * 不回退成"你直接说要生成什么"那种把锅推给用户的话。
 */
async function answer(text) {
  // 历史必须在推入占位气泡**之前**截好：historyPayload 按"有正文"过滤，
  // 推完再算虽然也能过滤掉空占位，但一旦以后改了过滤条件就会把上一条真实回答吃掉
  const history = historyPayload()
  thinking.value = true
  const idx = push('agent', '', { md: true, streaming: true })
  const msg = messages.value[idx]
  const started = Date.now()
  answerController = new AbortController()
  try {
    await askLessonStream({
      conversationId: conversationId.value,
      message: text,
      history,
      lesson: lessonPayload(),
      useKnowledge: useKnowledge.value,
      signal: answerController.signal,
      onDelta: (acc) => {
        msg.text = acc
        scrollToBottom()
      }
    })
    msg.elapsed = Math.max(1, Math.round((Date.now() - started) / 1000))
    if (!msg.text.trim()) {
      // 流开了但一个字没回来：明说，而不是留一个空气泡让人以为界面卡了
      msg.text = '这次没有收到内容。可能是模型侧超时或返回为空，再说一次或换个问法试试。'
    }
    msg.streaming = false
  } catch (e) {
    msg.streaming = false
    if (e?.name === 'AbortError') {
      if (!msg.text.trim()) msg.text = '已停止。'
      return
    }
    msg.text = `问答服务没响应：${e?.message || e}。\n\n生成功能不受影响，可以直接点下面的生成按钮。`
  } finally {
    answerController = null
    thinking.value = false
    nextTick(scrollToBottom)
  }
}

/** 规则判不出来时先交给后端状态机澄清；它给不出可执行结果就改为直接回答 */
async function chatFallback(text) {
  thinking.value = true
  let r = null
  try {
    r = await postDialogue(conversationId.value, text)
  } catch {
    // 状态机这条路挂了（后端没起、接口异常）→ 直接走问答，不要卡在这里
    thinking.value = false
    return answer(text)
  }
  thinking.value = false

  // 澄清：把"还缺什么"明说出来，同时留一个直接开干的出口 —— 追问不能把人卡死
  if (r.action === 'clarify') {
    // 后端 message 常常只是一句"请提供更多信息。"，真正有用的信息在缺字段里
    const missing = fieldLabels(r.missingFields)
    push(
      'agent',
      r.message || '还差一点信息才能开始。',
      { chips: ['生成教案'], hint: missing.length ? `还缺：${missing.join('、')}` : '' }
    )
    return
  }

  // 确认：把"确认/取消"做成按钮，别让教师猜该回哪个词
  if (r.action === 'confirm') {
    push('agent', r.message || '请确认我理解得对不对。', { chips: ['确认', '取消'] })
    return
  }

  if (r.action === 'reset') {
    push('agent', r.message || '好的，请重新描述你的需求。')
    return
  }

  // 执行：确认过的直接开做；没确认过的只给入口，不能说"我已经做了"
  const kind = kindFromResult(r)
  if (r.confirmed && kind) {
    startGenerate(kind, `确认收到，开始生成${nameOf(kind)}。`)
    return
  }

  // 状态机判"可以直接执行"却不打算说一句话 —— 这在以前会掉进
  // 那句「我理解了你的需求，你可以直接说要生成什么」里。
  // 现在改为**真的去回答**：教师说了一句人话，就该得到一句人话。
  if (!r.message) return answer(text)

  push('agent', r.message, { chips: r.suggestions.slice(0, 3) })
}

/** 后端说的"意图"能不能落到某一种成品上；落不到就老实聊天，不硬凑 */
function kindFromResult(r) {
  if (r.intentType === 'course_design') return 'lesson_plan'
  if (r.intentType === 'resource_generation') {
    return detectKind(String(r.fields.resource_type || '')) || null
  }
  return null
}

function startGenerate(kind, lead, sourceText = '') {
  // 先把他这句话里的"这节课是什么"读出来 —— 新手最常见的说法是
  // 「生成一份浮力教案」一口气说完，此时主题、学科、年级都在句子里，
  // 再去要求他"先填好教学主题"就是让他把说过的话再说一遍。
  const inferred = sourceText
    ? inferLessonFields(sourceText, { subjects: SUBJECTS, grades: GRADES })
    : null
  const changes = inferred ? applyInferred(store, inferred) : []
  if (changes.length) push('agent', `（已记下：${changes.join(' · ')}）`)

  if (!String(store.topic || '').trim()) {
    // 读不出来就问一句人话，并且给出**可以直接点的完整例句** ——
    // 空手给一句"请填主题"对新手等于没说
    push('agent', '这节课讲什么？在句子里带上主题就行，我会自己读出来。', {
      chips: ASK_TOPIC_EXAMPLES
    })
    return
  }

  if (kind !== props.activeKind) emit('switch-kind', kind)
  push('agent', lead)
  pushCard(kind)
  emit('generate', kind)
}

function requestGenerate(kind) {
  startGenerate(kind, `好的，开始生成${nameOf(kind)}。`)
}

/** 把判定结果翻译成对话里的一句话 + 实际动作 */
function dispatch(text, route) {
  const kindName = nameOf(route.kind)

  if (route.action === 'generate') {
    startGenerate(route.kind, `好的，开始生成${kindName}。右侧会显示进度，完成后可以直接打开。`, text)
    return
  }

  if (route.action === 'revise') {
    if (!reviseSupported.value) {
      push('agent', `现在只有教案支持"按指令修改"，${kindName}还不行。要调整的话请重新生成，或直接在这里问我要改什么。`)
      return
    }
    if (route.blocked) {
      push('agent', `${route.blocked}。要不要我先生成一份？`, { chips: ['生成教案'] })
      return
    }
    push('agent', `按这句改${kindName}：「${text}」。改完会记为新版本，不满意可以回退。`)
    emit('revise', { kind: route.kind, instruction: text })
    return
  }

  // 规则判不出来 —— 提问就直接回答，含糊的诉求先让状态机澄清
  if (looksLikeQuestion(text)) return answer(text)
  chatFallback(text)
}

function send(text) {
  const content = String(text ?? draft.value).trim()
  if (!content) return
  // 发送时还开着麦克风的话，下一句会被继续灌进输入框
  if (listening.value) stopListening()
  // 上一条还在流式输出 → 让它停，别两条回答同时往一个气泡里写
  if (answerController) stopAnswer()

  draft.value = ''
  const route = routeUserMessage(content, {
    hasVersion: reviseSupported.value && currentVersion.value > 0,
    activeKind: props.activeKind
  })
  push('user', content)
  dispatch(content, route)
}

/** 快捷按钮与卡片上的"重试/开始生成"是同一条路，避免两套入口说法不一致 */
function quick(q) {
  push('user', q.label)
  requestGenerate(q.kind)
}

onMounted(refreshVersion)
onBeforeUnmount(() => {
  stopAnswer()
  stopListening()
  stopSpeaking()
})
watch(() => [store.taskId, props.activeKind], refreshVersion)
</script>

<style lang="scss" scoped>
.lesson-chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  height: 100%;
  padding: 16px 18px 18px;
  background:
    radial-gradient(120% 90% at 12% 0%, var(--brand-glow), transparent 60%),
    var(--wb-surface);
  border: 1px solid var(--wb-border-strong);
  border-radius: 16px;
}

.lc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--wb-border);

  .lc-head-main {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    min-width: 0;
  }

  .lc-title {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--wb-text);
  }

  .lc-sub {
    font-size: 12px;
    color: var(--wb-text-3);
  }

  .lc-head-tools {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: none;
  }

  .lc-kb {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--wb-text-3);
    cursor: pointer;
    user-select: none;
  }
}

.lc-log {
  flex: 1;
  min-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 6px 4px 2px;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: var(--wb-border-strong);
    border-radius: 3px;
  }
}

/* 空状态做成"可点的示例"，而不是一段使用说明 —— 教师第一步不知道能说什么 */
.lc-empty {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 2px;

  .lc-empty-lead {
    margin: 0 0 2px;
    font-size: 13px;
    color: var(--wb-text-3);
  }

  .lc-empty-setup {
    display: flex;
    align-items: center;
    gap: var(--sp-3);
    flex-wrap: wrap;
    margin-top: 6px;
    padding-top: 10px;
    border-top: 1px dashed var(--wb-border);
    font-size: 12.5px;
    color: var(--wb-text-3);
  }

  .lc-empty-setup-btn {
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 999px;
    border: 1px solid var(--brand-border);
    background: var(--brand-soft);
    color: var(--brand-text);
    cursor: pointer;
    transition: all 0.18s ease;

    &:hover { background: var(--brand-soft-2); }
  }
}

.lc-empty-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 9px 12px;
  font-family: inherit;
  font-size: 13px;
  text-align: left;
  color: var(--wb-text-2);
  background: var(--wb-surface-2);
  border: 1px solid var(--wb-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.18s ease;

  b {
    flex: none;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--brand-text);
  }

  span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  &:hover {
    color: var(--wb-text);
    background: var(--wb-hover);
    border-color: var(--brand-border);
    transform: translateX(2px);
  }
}

.lc-msg {
  display: flex;
  flex-direction: column;
  gap: 7px;
  max-width: 86%;

  &.is-user { align-self: flex-end; align-items: flex-end; }
  &.is-agent { align-self: flex-start; max-width: 92%; }
}

.lc-bubble {
  padding: 11px 14px;
  font-size: 13.5px;
  line-height: 1.75;
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-word;

  .is-user & {
    background: linear-gradient(135deg, var(--wb-border-strong), rgba(0, 140, 255, 0.16));
    border: 1px solid var(--brand-border);
    color: var(--wb-text);
    border-bottom-right-radius: 4px;
  }

  .is-agent & {
    background: var(--wb-surface-2);
    border: 1px solid var(--wb-border);
    color: var(--wb-text);
    border-bottom-left-radius: 4px;
  }

  /* Markdown 正文自己管换行，别再叠 pre-wrap（会把列表挤歪） */
  &.lc-bubble-md { white-space: normal; }
}

.lc-md {
  :deep(p) { margin: 0 0 8px; }
  :deep(p:last-child) { margin-bottom: 0; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 20px; }
  :deep(li) { margin: 3px 0; }
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    margin: 12px 0 6px;
    font-size: 14px;
    font-weight: 600;
    color: var(--wb-text);
  }
  :deep(h1:first-child), :deep(h2:first-child), :deep(h3:first-child) { margin-top: 0; }
  :deep(code) {
    padding: 1px 5px;
    font-size: 12.5px;
    background: rgba(0, 0, 0, 0.32);
    border-radius: 4px;
    color: #7fe3ff;
  }
  :deep(pre) {
    margin: 8px 0;
    padding: 10px 12px;
    overflow-x: auto;
    background: rgba(0, 0, 0, 0.42);
    border: 1px solid var(--wb-border);
    border-radius: 8px;
    position: relative;

    code { padding: 0; background: none; color: inherit; }
  }
  :deep(blockquote) {
    margin: 8px 0;
    padding: 2px 0 2px 12px;
    border-left: 2px solid var(--brand-border);
    color: var(--wb-text-2);
  }
  :deep(table) {
    width: 100%;
    margin: 8px 0;
    border-collapse: collapse;
    font-size: 12.5px;
  }
  :deep(th), :deep(td) {
    padding: 6px 8px;
    border: 1px solid var(--wb-border);
    text-align: left;
  }
  :deep(th) { background: var(--wb-surface-2); color: var(--wb-text); font-weight: 600; }
  :deep(a) { color: #4fd1ff; text-decoration: underline; }
  :deep(hr) { border: none; border-top: 1px solid var(--wb-border); margin: 12px 0; }
  :deep(.copy-btn) {
    position: absolute;
    top: 6px;
    right: 6px;
    padding: 2px 7px;
    font-size: 11px;
    color: var(--wb-text-2);
    background: var(--wb-border);
    border: 1px solid var(--wb-border);
    border-radius: 5px;
    cursor: pointer;
  }
  :deep(.katex) { font-size: 1.02em; }
  :deep(.math-block) { margin: 8px 0; overflow-x: auto; }
}

.lc-typing {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--wb-text-3);
}

.lc-dots {
  display: inline-flex;
  gap: 3px;

  i {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--brand-500);
    animation: lc-bounce 1.1s ease-in-out infinite;

    &:nth-child(2) { animation-delay: 0.15s; }
    &:nth-child(3) { animation-delay: 0.3s; }
  }
}

@keyframes lc-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.lc-hint {
  display: block;
  margin-top: 7px;
  font-size: 12px;
  color: var(--brand-text);
}

.lc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lc-msg-tools {
  display: flex;
  gap: 10px;
  padding-left: 2px;

  button {
    padding: 0;
    font-family: inherit;
    font-size: 11.5px;
    color: var(--wb-text-3);
    background: none;
    border: none;
    cursor: pointer;
    transition: color 0.18s ease;

    &:hover { color: var(--brand-text); }
  }

  .lc-elapsed { font-size: 11.5px; color: var(--wb-text-3); }
}

/* 产物卡片 —— 生成进度直接长在对话流里 */
.lc-card {
  width: 100%;
  padding: 12px 14px;
  background: var(--wb-surface-2);
  border: 1px solid var(--wb-border);
  border-left-width: 3px;
  border-radius: 12px;
  transition: border-color 0.25s ease;

  &.lc-card-running {
    border-left-color: var(--brand-500);
    box-shadow: 0 0 0 1px var(--brand-border);
  }
  &.lc-card-done { border-left-color: #00ff88; }
  &.lc-card-failed { border-left-color: #ff6b6b; }
  &.lc-card-idle { border-left-color: var(--wb-border-strong); }
}

.lc-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--wb-text);

  .lc-card-name { font-size: 13.5px; font-weight: 600; }
  .lc-card-status {
    margin-left: auto;
    font-size: 12px;
    color: var(--wb-text-3);
  }

  .lc-card-running & .lc-card-status { color: #5fdcff; }
  .lc-card-done & .lc-card-status { color: #5cf7a4; }
  .lc-card-failed & .lc-card-status { color: #ff8b8b; }
}

.lc-card-err {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #ff9b9b;
}

.lc-card-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.lc-quick {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding-top: 12px;
  border-top: 1px solid var(--wb-border);

  .lc-quick-label {
    font-size: 11.5px;
    letter-spacing: 0.06em;
    color: var(--wb-text-3);
  }

  /* 是按钮，不是一句抱怨：点一下就能直达设置 */
  .lc-quick-warn {
    margin-left: auto;
    font-family: inherit;
    font-size: 11.5px;
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px dashed var(--wb-border-strong);
    background: transparent;
    color: var(--wb-warn-text);
    cursor: pointer;

    &:hover { border-style: solid; }
  }
}

.lc-chip {
  padding: 5px 11px;
  font-size: 12px;
  font-family: inherit;
  color: var(--wb-text-2);
  background: var(--wb-surface-2);
  border: 1px solid var(--wb-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover:not(:disabled) {
    color: var(--wb-text);
    background: var(--wb-border-strong);
    border-color: var(--brand-border);
  }

  &:disabled { opacity: 0.45; cursor: not-allowed; }
}

.lc-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;

  :deep(.el-textarea) { flex: 1; }

  .lc-send { min-width: 68px; }
}

@media (max-width: 860px) {
  .lc-msg { max-width: 100%; }
  .lesson-chat { padding: 12px; }
}
</style>
