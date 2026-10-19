<template>
  <!--
    数据流向徽标：把后端 X-Data-* 响应头渲染成人能看懂的一句话。

    为什么放在顶栏常驻：合规可证性是"每次都能看见"，
    而不是"出事了才弹窗"。没有发生过生成调用时不显示，避免无意义噪音。
  -->
  <el-tooltip v-if="summary" placement="bottom-end" :show-after="200" effect="dark">
    <template #content>
      <div class="flow-tip">
        <div class="tip-row"><span class="tip-k">数据定级</span><span>{{ summary.level }} · {{ summary.levelText }}</span></div>
        <div class="tip-row"><span class="tip-k">处理位置</span><span>{{ summary.egress ? '云端厂商（已出校）' : '校内 / 本机（未出校）' }}</span></div>
        <div class="tip-row"><span class="tip-k">本次动作</span><span>{{ summary.actionLabel }}</span></div>
        <div v-if="summary.findings" class="tip-row">
          <span class="tip-k">命中项</span><span>{{ summary.findings }}</span>
        </div>
        <div class="tip-foot">后端已在发出请求前完成判定，此结果可在浏览器 Network 面板复核</div>
      </div>
    </template>

    <div class="flow-badge" :class="`tone-${summary.tone}`">
      <span class="dot"></span>
      <span class="txt">{{ shortText }}</span>
    </div>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { dataFlowSummary } from '@/api/dataFlow'

const summary = dataFlowSummary

// 顶栏空间有限，用最短的词表达最关键的事实：去了哪、有没有被处理
const shortText = computed(() => {
  const s = summary.value
  if (!s) return ''
  if (!s.egress) return '校内 · 未出校'
  if (s.action === 'block') return `已拦截 · ${s.level}`
  if (s.action === 'redact') return `云端 · 已脱敏`
  return `云端 · ${s.level}`
})
</script>

<style lang="scss" scoped>
.flow-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.6;
  cursor: default;
  user-select: none;
  white-space: nowrap;
  border: 1px solid transparent;
  transition: all 0.25s ease;

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex: none;
  }

  // 三档色调一律走语义 token。
  // 不能用 #00ff88 / #ffb020 这类"暗色界面上才亮"的颜色：浅色主题下
  // 亮绿字压在近白底上对比度只有 1.3:1，等于看不见 —— 而这个徽标常驻顶栏，
  // 是"数据去了哪"唯一的常驻可见证据，看不清就失去了存在意义。
  // 未出校 / 未检测到敏感信息 —— 安全
  &.tone-ok {
    background: var(--success-bg);
    border-color: rgba(16, 185, 129, 0.3);
    color: var(--wb-ok-text);
    .dot { background: var(--success); }
  }

  // 已发往云端（原样或脱敏后）—— 提醒，不是错误
  &.tone-warn {
    background: var(--warning-bg);
    border-color: rgba(245, 158, 11, 0.34);
    color: var(--wb-warn-text);
    .dot { background: var(--warning); }
  }

  // 已拦截 —— 明确告知被拦下及原因
  &.tone-block {
    background: var(--danger-bg);
    border-color: rgba(239, 68, 68, 0.34);
    color: var(--wb-risk-text);
    .dot { background: var(--danger); }
  }
}

// tooltip 内容（挂在 body 上，不能用 scoped 样式包裹，这里用 :deep 不适用，
// 故直接写在模板外层——Element Plus 会把 content 渲染到 popper 容器里）
.flow-tip {
  font-size: 12px;
  line-height: 1.9;
  max-width: 320px;

  .tip-row {
    display: flex;
    gap: 12px;
    justify-content: space-between;

    .tip-k {
      color: rgba(255, 255, 255, 0.55);
      flex: none;
    }
  }

  .tip-foot {
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.45);
    font-size: 11px;
    line-height: 1.6;
  }
}
</style>
