<template>
  <div class="ti-card">
    <header class="ti-head">
      <span class="ti-title">教学意图</span>
      <span class="ti-sub">系统理解到的这节课</span>
    </header>

    <!-- 基本盘：主题/学科/年级/学段/课时 由顶部课程条维护，这里只做确认展示 -->
    <dl class="ti-base">
      <div><dt>主题</dt><dd>{{ store.topic || '（还没说）' }}</dd></div>
      <div><dt>学科</dt><dd>{{ store.subject || '（还没说）' }}</dd></div>
      <div><dt>年级</dt><dd>{{ store.grade || '（还没说）' }}</dd></div>
      <div><dt>学段</dt><dd>{{ store.level || '（由年级派生）' }}</dd></div>
      <div><dt>课时</dt><dd>{{ store.duration }} 分钟</dd></div>
    </dl>

    <p class="ti-hint">
      上面几项改顶部课程条即可 —— 它们只有一份，改哪儿都同步。
    </p>

    <!-- 扩展项：教师可补充，空着不编造 -->
    <section v-for="f in FIELDS" :key="f.key" class="ti-field">
      <div class="ti-label">
        {{ f.label }}
        <span class="ti-tip">{{ f.tip }}</span>
      </div>
      <div v-if="list(f.key).length" class="ti-tags">
        <el-tag
          v-for="(item, i) in list(f.key)"
          :key="i"
          size="small"
          closable
          :disable-transitions="false"
          @close="removeAt(f.key, i)"
        >
          {{ item }}
        </el-tag>
      </div>
      <p v-else class="ti-empty">还没填 —— 由模型按主题自行设计</p>
      <el-input
        v-model="draft[f.key]"
        size="small"
        :placeholder="f.placeholder"
        @keyup.enter="add(f.key)"
      />
    </section>

    <section class="ti-field">
      <div class="ti-label">
        本次使用哪些知识库
        <span class="ti-tip">决定生成时能引用什么</span>
      </div>
      <el-radio-group v-model="scope" size="small">
        <el-radio-button value="both">系统 + 我的</el-radio-button>
        <el-radio-button value="system">只要系统库</el-radio-button>
        <el-radio-button value="personal">只要我上传的</el-radio-button>
        <el-radio-button value="none">不用知识库</el-radio-button>
      </el-radio-group>
      <p v-if="scope === 'none'" class="ti-empty">
        本次不检索知识库，内容全靠模型自身 —— 引用面板会写明"未使用知识库"。
      </p>
    </section>
  </div>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { useLessonStore } from '@/store/lesson'

const store = useLessonStore()

const FIELDS = [
  { key: 'goals', label: '教学目标', tip: '要可观测', placeholder: '例如：能计算浮力大小，回车添加' },
  { key: 'knowledgePoints', label: '知识点', tip: '这节课要覆盖', placeholder: '例如：阿基米德原理，回车添加' },
  { key: 'focusPoints', label: '教学重点', tip: '', placeholder: '回车添加' },
  { key: 'hardPoints', label: '教学难点', tip: '模型会安排突破环节', placeholder: '例如：V排 与 V物 的辨析，回车添加' },
  { key: 'methods', label: '教学方法', tip: '', placeholder: '例如：探究式，回车添加' },
  { key: 'interactions', label: '互动形式', tip: '', placeholder: '例如：分组实验，回车添加' }
]

const draft = reactive({})

function list(key) {
  const v = store.intentExtras?.[key]
  return Array.isArray(v) ? v : []
}

function add(key) {
  const text = String(draft[key] || '').trim()
  if (!text) return
  const next = [...list(key)]
  // 允许一次加多条：教师常常直接粘一行"a；b；c"
  for (const part of text.split(/[；;，,、\n]/)) {
    const s = part.trim()
    if (s && !next.includes(s)) next.push(s)
  }
  store.intentExtras[key] = next.slice(0, 12)
  draft[key] = ''
}

function removeAt(key, i) {
  const next = [...list(key)]
  next.splice(i, 1)
  store.intentExtras[key] = next
}

const scope = computed({
  get: () => store.knowledgeScope || 'both',
  set: (v) => { store.knowledgeScope = v }
})
</script>

<style scoped>
.ti-card {
  padding: 12px 14px;
}
.ti-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}
.ti-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--wb-text);
}
.ti-sub {
  font-size: 11.5px;
  color: var(--wb-text-3);
}
.ti-base {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 12px;
  margin: 0 0 8px;
  padding: 10px;
  border-radius: 8px;
  background: var(--wb-surface-2);
}
.ti-base dt {
  font-size: 11.5px;
  color: var(--wb-text-3);
}
.ti-base dd {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--wb-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ti-hint {
  margin: 0 0 12px;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--wb-text-3);
}
.ti-field {
  padding-top: 10px;
  margin-bottom: 10px;
  border-top: 1px solid var(--wb-border);
}
.ti-label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--wb-text);
}
.ti-tip {
  font-size: 11px;
  font-weight: 400;
  color: var(--wb-text-3);
}
.ti-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}
.ti-empty {
  margin: 0 0 6px;
  font-size: 11.5px;
  color: var(--wb-text-3);
}
</style>
