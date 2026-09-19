<template>
  <el-drawer
    v-model="visible"
    title="智能体知道的事"
    direction="rtl"
    size="440px"
    class="ctx-drawer"
    @open="load"
  >
    <div class="ctx-body">
      <p class="ctx-lead">
        这段内容每轮都会随你的问题一起交给模型。下面就是**原文**，不是概括 ——
        你看到的和它看到的是同一份。
      </p>

      <div v-if="error" class="ctx-error">{{ error }}</div>

      <template v-else>
        <!-- 1. 这节课 -->
        <section class="ctx-sec">
          <h4>这节课</h4>
          <dl class="ctx-list">
            <div v-for="row in rows" :key="row.label">
              <dt>{{ row.label }}</dt>
              <dd :class="{ 'is-empty': !row.value }">{{ row.value || '（还没填）' }}</dd>
            </div>
          </dl>
          <p class="ctx-note">
            要改这些，用工作台顶部的「更多设置」；改完这里会同步。
          </p>
        </section>

        <!-- 2. 已生成的成果 -->
        <section class="ctx-sec">
          <h4>已生成的成果</h4>
          <ul class="ctx-artifacts">
            <li v-for="a in artifacts" :key="a.id">
              <span class="ca-dot" :class="`dot-${a.status}`" />
              <span class="ca-name">{{ a.name }}</span>
              <span class="ca-status">{{ a.label }}</span>
            </li>
          </ul>
          <p v-if="!artifacts.some(a => a.status !== 'idle')" class="ctx-note">
            这节课还没生成任何成果。这一点也会如实告诉模型 ——
            它不会假称"已经生成好了"。
          </p>
        </section>

        <!-- 3. 对话记忆 -->
        <section class="ctx-sec">
          <h4>对话记忆</h4>
          <p class="ctx-note">
            本地保留 {{ messageCount }} 条消息；每轮最多带上最近
            <b>{{ historyTurns || 20 }}</b> 轮提问与回答，更早的不会被带走。
            点「清空」会同时清掉本地气泡和服务端的对话状态。
          </p>
        </section>

        <!-- 4. 原文 -->
        <section class="ctx-sec">
          <el-collapse>
            <el-collapse-item :title="`我每次会告诉模型的原话（${system.length} 字）`">
              <pre class="ctx-raw">{{ system }}</pre>
            </el-collapse-item>
          </el-collapse>
        </section>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
/**
 * 「智能体知道的事」抽屉。
 *
 * 解决的是"上下文和记忆到底怎么处理的，我完全不知道"这类疑问。
 * 做法不是写一段解释，而是**把原文摆出来** —— 解释会过时、会与实际不符，
 * 原文不会。数据全部来自 `/api/lesson-chat/context`，与真正发给模型的是同一份。
 */
import { computed, ref } from 'vue'
import { ARTIFACTS, useLessonStore } from '@/store/lesson'
import { fetchLessonContext } from '@/api/lessonChat'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 对话里已有的消息条数，用于"记忆"那一节说实话 */
  messageCount: { type: Number, default: 0 },
  /** 传给后端的课程语境，与问答请求用的是同一个组装函数 */
  lesson: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])

const store = useLessonStore()
const system = ref('')
const historyTurns = ref(0)
const error = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const rows = computed(() => [
  { label: '教学主题', value: store.topic },
  { label: '学科', value: store.subject },
  { label: '年级', value: store.grade },
  { label: '课时', value: `${store.duration} 分钟` },
  { label: '难度', value: store.difficultyLabel },
  { label: '教学要点', value: store.keyPoints },
  {
    label: '参考资料',
    value: store.referenceFiles.length
      ? `${store.referenceFiles.length} 份：${store.referenceFiles.map(f => f.name).join('、')}`
      : ''
  }
])

const STATUS_LABEL = { idle: '未生成', running: '生成中', done: '已完成', failed: '生成失败' }
const artifacts = computed(() => ARTIFACTS.map((a) => ({
  id: a.id,
  name: a.name,
  status: store.artifacts[a.id]?.status || 'idle',
  label: STATUS_LABEL[store.artifacts[a.id]?.status || 'idle']
})))

async function load() {
  error.value = ''
  try {
    const out = await fetchLessonContext(props.lesson)
    system.value = out.system
    historyTurns.value = out.historyTurns
  } catch (e) {
    error.value = `读不到上下文原文：${e.message || e}`
  }
}
</script>

<style lang="scss" scoped>
.ctx-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
}

.ctx-lead {
  margin: 0;
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.7;
  color: rgba(0, 200, 255, 0.85);
  background: rgba(0, 200, 255, 0.07);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 8px;
}

.ctx-error {
  padding: 10px 12px;
  font-size: 12.5px;
  color: #ff9b9b;
  background: rgba(255, 107, 107, 0.08);
  border: 1px solid rgba(255, 107, 107, 0.25);
  border-radius: 8px;
}

.ctx-sec h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.ctx-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;

  > div {
    display: flex;
    gap: 10px;
    font-size: 12.5px;
  }

  dt {
    flex: none;
    width: 76px;
    color: rgba(255, 255, 255, 0.42);
  }

  dd {
    margin: 0;
    flex: 1;
    word-break: break-word;

    &.is-empty { color: rgba(255, 255, 255, 0.25); }
  }
}

.ctx-artifacts {
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
    font-size: 12.5px;
  }

  .ca-name { flex: 1; }
  .ca-status { color: rgba(255, 255, 255, 0.45); }
}

.ca-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: none;
  background: rgba(255, 255, 255, 0.22);

  &.dot-done { background: #00ff88; }
  &.dot-running { background: #00c8ff; }
  &.dot-failed { background: #ff6b6b; }
}

.ctx-note {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.42);

  b { color: rgba(0, 200, 255, 0.9); }
}

.ctx-raw {
  margin: 0;
  padding: 10px;
  max-height: 340px;
  overflow: auto;
  font-size: 11.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(255, 255, 255, 0.7);
  background: rgba(0, 0, 0, 0.35);
  border-radius: 8px;
}
</style>

<!--
  这一段**必须非 scoped**：el-drawer 会把自己 teleport 到 body，
  scoped 的 data-v 属性选不中它的外壳，于是抽屉会是亮色而内容区是暗色。
  用 .ctx-drawer 前缀把作用域圈住，不污染其它地方的抽屉。
-->
<style lang="scss">
.el-drawer.ctx-drawer,
.ctx-drawer .el-drawer {
  background: #0a0e27;

  .el-drawer__header {
    margin-bottom: 0;
    padding: 16px 20px;
    color: #fff;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .el-drawer__title {
    font-size: 15px;
    color: #fff;
  }

  .el-drawer__body {
    padding: 16px 20px;
    background: #0a0e27;
  }

  .el-drawer__close-btn { color: rgba(255, 255, 255, 0.6); }

  .el-collapse {
    border-top: none;
    border-bottom: none;
  }

  .el-collapse-item__header,
  .el-collapse-item__wrap {
    background: transparent;
    border-color: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.72);
    font-size: 12.5px;
  }

  .el-collapse-item__content { padding-bottom: 10px; }
}
</style>

