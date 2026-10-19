<template>
  <span class="wb-tag" :class="`wb-tag--${tone}`">
    <span v-if="dot" class="wb-tag__dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 状态标签。
 *
 * 状态色**只由这里决定**，页面不自己挑颜色 ——
 * 否则同一个"失败"会在教案面板是红的、在 PPT 面板是橙的，教师要重新学一遍。
 * 颜色之外还有文案与圆点，色盲用户靠文案也能分辨。
 */

const PRESET = {
  // 产物状态
  idle: { label: '未生成', tone: 'neutral' },
  running: { label: '生成中', tone: 'brand' },
  done: { label: '已完成', tone: 'success' },
  failed: { label: '生成失败', tone: 'danger' },
  // 通用
  archived: { label: '已归档', tone: 'neutral' },
  active: { label: '进行中', tone: 'brand' },
  pending: { label: '等待中', tone: 'neutral' },
  degraded: { label: '已降级', tone: 'warning' },
  // 合规
  pass: { label: '通过', tone: 'success' },
  warn: { label: '有提醒', tone: 'warning' },
  risk: { label: '需修改', tone: 'danger' },
  off: { label: '未开启', tone: 'neutral' },
  // 出校分级
  L1: { label: 'L1 公开', tone: 'success' },
  L2: { label: 'L2 校内一般', tone: 'brand' },
  L3: { label: 'L3 敏感', tone: 'warning' },
  L4: { label: 'L4 重要', tone: 'danger' },
  L5: { label: 'L5 核心', tone: 'danger' }
}

const props = defineProps({
  status: { type: String, default: '' },
  label: { type: String, default: '' },
  /** 直接指定色调，覆盖预设 */
  tone: { type: String, default: '' },
  dot: { type: Boolean, default: true }
})

const preset = computed(() => PRESET[props.status] || {})
const label = computed(() => props.label || preset.value.label || props.status || '未知')
const tone = computed(() => props.tone || preset.value.tone || 'neutral')
</script>

<style scoped>
.wb-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-xs);
  font-weight: 500;
  line-height: 20px;
  border: 1px solid transparent;
  white-space: nowrap;
}

.wb-tag__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-pill);
  background: currentColor;
}

.wb-tag--neutral {
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
  border-color: var(--wb-border);
}

.wb-tag--brand {
  background: var(--brand-soft-2);
  color: var(--brand-text);
  border-color: var(--brand-border);
}


.wb-tag--success {
  background: var(--success-bg);
  color: var(--wb-ok-text);
  border-color: rgba(16, 185, 129, 0.25);
}

.wb-tag--warning {
  background: var(--warning-bg);
  color: var(--wb-warn-text);
  border-color: rgba(245, 158, 11, 0.3);
}

.wb-tag--danger {
  background: var(--danger-bg);
  color: var(--wb-risk-text);
  border-color: rgba(239, 68, 68, 0.28);
}
</style>
