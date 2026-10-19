<template>
  <div v-if="visible" class="cmp" :class="{ 'cmp--compact': compact }">
    <button
      class="cmp__head"
      type="button"
      :aria-expanded="open"
      @click="open = !open"
    >
      <StatusTag :status="tone" dot />
      <span class="cmp__title">教学合规质检</span>
      <span v-if="report.passed !== false && score" class="cmp__score">{{ score }} 分</span>
      <el-icon class="cmp__caret" :size="14"><component :is="open ? ArrowUp : ArrowDown" /></el-icon>
    </button>

    <!-- 未开启：如实说明，绝不假装检查过 -->
    <p v-if="report.enabled === false" class="cmp__note">
      本次未执行质检：{{ report.reason || '闸门已关闭' }}。这不影响生成结果。
    </p>

    <div v-show="open" class="cmp__body">
      <ul v-if="issues.length" class="cmp__list">
        <li v-for="(it, i) in issues" :key="i" class="cmp__item">
          <span class="cmp__code">{{ it.code }}</span>
          <div class="cmp__text">
            <p class="cmp__msg">{{ it.message }}</p>
            <p v-if="it.hint" class="cmp__hint">{{ it.hint }}</p>
          </div>
        </li>
      </ul>

      <p v-else class="cmp__note">未发现需要修改的问题。</p>

      <div v-if="suggestions.length" class="cmp__suggest">
        <b>建议</b>
        <ul>
          <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import StatusTag from '@/components/common/StatusTag.vue'

/**
 * 教学合规质检结果（R1–R8，纯规则离线）。
 *
 * 三条展示纪律：
 *  1. **只报告、不阻断**。这份报告永远不该挡住教师拿到产物，
 *     所以这里不做任何拦截，只是把问题摊开。
 *  2. `enabled=false` 要如实显示"未执行"。早年界面把"没检查"也画成绿色通过，
 *     那是比不检查更糟的假象。
 *  3. 问题项必须带 `hint`（怎么改），否则教师只知道不好、不知道怎么改。
 */
const props = defineProps({
  report: { type: Object, default: () => ({}) },
  compact: { type: Boolean, default: false }
})

const open = ref(false)

const visible = computed(() => !!props.report && Object.keys(props.report).length > 0)

const issues = computed(() => {
  const list = props.report?.issues
  return Array.isArray(list) ? list : []
})

const suggestions = computed(() => {
  const list = props.report?.suggestions
  return Array.isArray(list) ? list.filter(Boolean) : []
})

const score = computed(() => {
  const s = props.report?.score
  return Number.isFinite(s) ? s : 0
})

const tone = computed(() => {
  if (props.report?.enabled === false) return 'off'
  if (issues.value.some(i => /high|error|严重/i.test(i.severity || ''))) return 'risk'
  if (issues.value.length) return 'warn'
  return 'pass'
})
</script>

<style scoped>
.cmp {
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-sm);
  background: var(--wb-surface-2);
  overflow: hidden;
}

.cmp__head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border: none;
  background: transparent;
  color: var(--wb-text);
  font-size: var(--fs-sm);
  cursor: pointer;
  text-align: left;
}

.cmp__head:hover { background: var(--wb-hover); }

.cmp__title { font-weight: 600; }
.cmp__score { color: var(--wb-text-3); font-size: var(--fs-xs); }
.cmp__caret { margin-left: auto; color: var(--wb-text-3); }

.cmp__body {
  padding: 0 var(--sp-3) var(--sp-3);
  border-top: 1px solid var(--wb-border);
  padding-top: var(--sp-2);
}

.cmp__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.cmp__item {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-start;
}

.cmp__code {
  flex: 0 0 auto;
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
}

.cmp__text { min-width: 0; }

.cmp__msg {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--wb-text);
  line-height: 1.6;
}

.cmp__hint {
  margin: 2px 0 0;
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  line-height: 1.6;
}

.cmp__note {
  margin: var(--sp-2) var(--sp-3);
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  line-height: 1.6;
}

.cmp__suggest {
  margin-top: var(--sp-3);
  font-size: var(--fs-xs);
  color: var(--wb-text-2);
}

.cmp__suggest ul {
  margin: 4px 0 0;
  padding-left: 18px;
  color: var(--wb-text-3);
}

.cmp--compact .cmp__body { font-size: var(--fs-xs); }
</style>
