<template>
  <div class="ct-panel">
    <header class="ct-head">
      <span class="ct-title">引用与依据</span>
      <span class="ct-kind">{{ kindName }}</span>
    </header>

    <p v-if="!store.taskId" class="ct-empty">课程还没同步到后端，暂无引用记录。</p>

    <template v-else-if="used">
      <p class="ct-ok">
        本次检索用上了知识库（范围：{{ scopeName }}），共 {{ citations.length }} 条依据。
      </p>
      <p v-if="relaxed" class="ct-warn">
        本学科库内没有直接命中，以下是放宽学科后的内容，请教师核验。
      </p>
      <ul class="ct-list">
        <li v-for="(c, i) in citations" :key="i">
          <span class="ct-src">{{ c.source || '（未标注来源）' }}</span>
          <span v-if="c.heading_path" class="ct-path">{{ c.heading_path }}</span>
        </li>
      </ul>
      <p v-if="blueprintUsed" class="ct-meta">本版按已确认的教学蓝图生成。</p>
      <p v-else class="ct-meta">
        本版没有使用蓝图（教师跳过，或蓝图尚未确认）。
      </p>
    </template>

    <template v-else-if="reason">
      <!-- 没检索到必须如实说，不能让教师以为"系统查过了没问题" -->
      <p class="ct-none">{{ reason }}</p>
      <p class="ct-tip">内容由模型自行生成，建议按自己的教学经验核对后再用。</p>
    </template>

    <p v-else class="ct-empty">这类产物还没有生成过，生成后这里会列出它依据了哪些资料。</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useLessonStore, ARTIFACTS } from '@/store/lesson'

const props = defineProps({
  kind: { type: String, default: 'lesson_plan' }
})

const store = useLessonStore()
const art = computed(() => store.artifacts?.[props.kind] || {})
const kindName = computed(
  () => (ARTIFACTS.find((a) => a.id === props.kind) || ARTIFACTS[0]).name)

const SCOPE_NAMES = {
  system: '系统教学知识库',
  personal: '我的个人知识库',
  both: '系统 + 个人',
  none: '不使用知识库'
}

const knowledge = computed(() => art.value.knowledge || null)
const used = computed(() => knowledge.value?.used === true)
const citations = computed(() =>
  Array.isArray(art.value.citations) ? art.value.citations : [])
const relaxed = computed(() => knowledge.value?.relaxed === true)
const scopeName = computed(() => SCOPE_NAMES[knowledge.value?.scope] || '知识库')
const reason = computed(() => {
  if (knowledge.value?.used === false) {
    return knowledge.value.reason || '本次未能检索到相关知识'
  }
  return ''
})
const blueprintUsed = computed(() => art.value.contextMeta?.blueprint_used === true)
</script>

<style scoped>
.ct-panel {
  padding: 12px 14px;
}
.ct-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}
.ct-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--wb-text);
}
.ct-kind {
  font-size: 11.5px;
  color: var(--wb-text-3);
}
.ct-ok,
.ct-meta {
  margin: 0 0 8px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--wb-text-2);
}
.ct-warn {
  margin: 0 0 8px;
  padding: 7px 9px;
  font-size: 12px;
  line-height: 1.7;
  border-radius: 6px;
  background: var(--wb-warn-bg);
  color: var(--wb-warn-text);
}
.ct-none {
  margin: 0 0 6px;
  padding: 8px 10px;
  font-size: 12.5px;
  line-height: 1.7;
  border-radius: 6px;
  background: var(--wb-warn-bg);
  color: var(--wb-warn-text);
}
.ct-tip,
.ct-empty {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--wb-text-3);
}
.ct-list {
  margin: 0 0 10px;
  padding: 0;
  list-style: none;
}
.ct-list li {
  padding: 7px 9px;
  margin-bottom: 6px;
  border-left: 2px solid var(--wb-border-strong);
  border-radius: 0 6px 6px 0;
  background: var(--wb-surface-2);
}
.ct-src {
  display: block;
  font-size: 12.5px;
  color: var(--wb-text);
}
.ct-path {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--wb-text-3);
}
</style>
