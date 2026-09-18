<template>
  <!--
    教学合规质检报告：把后端「出厂质检闸门」的结果渲染成可扫读的清单。

    设计取舍：
      1. 闸门关闭 / 出错时（enabled !== true）整块不渲染 —— 没有结果时不制造噪音。
      2. 有必须修改项（error）时默认展开，只有建议项时默认收起，
         避免每次生成完都被一长串提示糊脸。
      3. 只做展示与提示，绝不阻断下载/预览 —— 质检是建议，不是审判。
  -->
  <div v-if="visible" class="compliance-report" :class="`tone-${toneClass}`" role="region"
       :aria-label="`${label}教学合规质检报告`">
    <button type="button" class="cr-head" @click="toggle" :aria-expanded="String(expanded)">
      <span class="cr-badge">
        <span class="dot"></span>
        <span class="txt">{{ headline }}</span>
      </span>
      <span class="cr-score">合规分 {{ report.score }}</span>
      <span class="cr-count">{{ countText }}</span>
      <span class="cr-caret" :class="{ open: expanded }">
        <el-icon><ArrowDown /></el-icon>
      </span>
    </button>

    <div v-show="expanded" class="cr-body">
      <p class="cr-summary">{{ summaryText }}</p>

      <ul v-if="sortedIssues.length" class="cr-issues">
        <li v-for="(it, idx) in sortedIssues" :key="idx" :class="`sev-${it.severity}`">
          <span class="cr-code">{{ it.code }}</span>
          <span class="cr-msg">
            <strong>{{ it.message }}</strong>
            <em v-if="it.hint">{{ it.hint }}</em>
          </span>
        </li>
      </ul>

      <div v-if="suggestions.length" class="cr-suggest">
        <div class="cr-suggest-title">修改建议</div>
        <ol>
          <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
        </ol>
      </div>

      <!--
        可选的模型深度复查：规则查"有没有、合不合规范"，它查"好不好、上不上的下去"。
        默认关闭且必须手动点——它慢、要花钱、还会抖，不该跟着每次生成自动跑。
      -->
      <div class="cr-review">
        <button
          type="button"
          class="cr-review-btn"
          :disabled="reviewing || !canReview"
          @click="runReview"
        >
          {{ reviewing ? '复查中…' : '深度复查（模型）' }}
        </button>
        <span class="cr-review-hint">规则查不到的：课时做不完、目标没人管、学生卡在哪</span>

        <p v-if="reviewError" class="cr-review-off">{{ reviewError }}</p>

        <template v-if="review">
          <p v-if="!review.enabled" class="cr-review-off">{{ review.reason || '未开启' }}</p>
          <template v-else>
            <p v-if="review.summary" class="cr-review-summary">{{ review.summary }}</p>
            <ul v-if="review.findings.length" class="cr-review-list">
              <li v-for="(f, i) in review.findings" :key="i" :class="`rv-${f.severity}`">
                <span v-if="f.dimension" class="rv-dim">{{ f.dimension }}</span>
                <span class="rv-advice">{{ f.advice || f.quote }}</span>
                <em v-if="f.advice && f.quote" class="rv-quote">原文：{{ f.quote }}</em>
              </li>
            </ul>
            <p v-else class="cr-review-off">没有查出规则之外的问题。</p>
          </template>
        </template>
      </div>

      <div class="cr-foot">离线规则扫描（依据 2022 版课标通行规范），仅供参考，最终以教师判断为准</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { useLessonStore } from '@/store/lesson'
import { deepReview } from '@/api/lessonArtifacts'

const props = defineProps({
  // 后端 compliance 报告：{enabled, artifact_type, passed, score, issues[], suggestions[]}
  report: { type: Object, default: null },
  // 产物名称，用于无障碍标签与文案
  label: { type: String, default: '本次生成' },
  // 深度复查要读哪一课的当前版本。留空时退回 store 里的当前课程。
  lessonId: { type: String, default: '' },
  kind: { type: String, default: 'lesson_plan' }
})

const store = useLessonStore()
const reviewing = ref(false)
const review = ref(null)
const reviewError = ref('')

// 没有课程 ID 就读不到版本链里的正文，这时不给按钮，避免点了必然失败
const canReview = computed(() => Boolean(props.lessonId || store.taskId))

async function runReview() {
  if (reviewing.value) return
  reviewing.value = true
  reviewError.value = ''
  try {
    review.value = await deepReview({
      lessonId: props.lessonId || store.taskId || '',
      kind: props.kind,
      ctx: { level: store.level || '', topic: store.topic || '', duration: store.duration }
    })
  } catch (e) {
    // 复查失败绝不能影响已经生成好的内容，只在这里提示一句
    reviewError.value = e?.message || '复查失败'
    review.value = null
  } finally {
    reviewing.value = false
  }
}

// 严重程度排序：必须先改的排最前
const SEV_ORDER = { error: 0, warn: 1, info: 2 }

const visible = computed(() => {
  const r = props.report
  return !!r && r.enabled === true
})

const issues = computed(() => props.report?.issues || [])
const errorCount = computed(() => issues.value.filter(i => i.severity === 'error').length)
const warnCount = computed(() => issues.value.filter(i => i.severity === 'warn').length)
const infoCount = computed(() => issues.value.filter(i => i.severity === 'info').length)

const sortedIssues = computed(() =>
  [...issues.value].sort(
    (a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9)
  )
)

const suggestions = computed(() => props.report?.suggestions || [])

const toneClass = computed(() => {
  if (errorCount.value) return 'error'
  if (warnCount.value) return 'warn'
  return 'ok'
})

const headline = computed(() => {
  if (errorCount.value) return `发现 ${errorCount.value} 处必须修改`
  if (warnCount.value) return `有 ${warnCount.value} 处建议优化`
  return '教学合规检查通过'
})

const countText = computed(() => {
  const parts = []
  if (errorCount.value) parts.push(`${errorCount.value} 错误`)
  if (warnCount.value) parts.push(`${warnCount.value} 提醒`)
  if (infoCount.value) parts.push(`${infoCount.value} 提示`)
  return parts.length ? parts.join(' · ') : '无问题'
})

const summaryText = computed(() => {
  if (errorCount.value) {
    return `${props.label}存在 ${errorCount.value} 处硬性合规问题，建议修改后再用于课堂。`
  }
  if (warnCount.value) {
    return `${props.label}未发现硬性合规问题，但有 ${warnCount.value} 处可优化项，按需调整即可。`
  }
  return `${props.label}未发现教学合规问题，可直接使用。`
})

const expanded = ref(false)

// 有必须修改项时自动展开；否则收起，只留一行摘要
watch(
  () => props.report,
  (r) => {
    expanded.value = !!r && (r.issues || []).some((i) => i.severity === 'error')
  },
  { immediate: true, deep: false }
)

function toggle() {
  expanded.value = !expanded.value
}
</script>

<style lang="scss" scoped>
.compliance-report {
  margin: 16px 0;
  border-radius: 10px;
  border: 1px solid transparent;
  overflow: hidden;
  font-size: 13px;
  transition: border-color 0.25s ease, background 0.25s ease;

  // 三种基调沿用顶栏数据流向徽标的配色，保证全站语义一致
  &.tone-ok {
    background: rgba(0, 255, 136, 0.06);
    border-color: rgba(0, 255, 136, 0.22);
    .dot { background: #00ff88; box-shadow: 0 0 6px rgba(0, 255, 136, 0.8); }
    .cr-badge .txt { color: #00ff88; }
  }
  &.tone-warn {
    background: rgba(255, 176, 32, 0.07);
    border-color: rgba(255, 176, 32, 0.28);
    .dot { background: #ffb020; box-shadow: 0 0 6px rgba(255, 176, 32, 0.8); }
    .cr-badge .txt { color: #ffb020; }
  }
  &.tone-error {
    background: rgba(255, 107, 107, 0.08);
    border-color: rgba(255, 107, 107, 0.35);
    .dot { background: #ff6b6b; box-shadow: 0 0 6px rgba(255, 107, 107, 0.85); }
    .cr-badge .txt { color: #ff6b6b; }
  }
}

.cr-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  background: transparent;
  border: 0;
  cursor: pointer;
  color: inherit;
  text-align: left;
  font-size: 13px;
  transition: background 0.2s ease;

  &:hover { background: rgba(255, 255, 255, 0.04); }
  &:focus-visible { outline: 2px solid rgba(255, 255, 255, 0.35); outline-offset: -2px; }

  .cr-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-weight: 600;
    flex: none;

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      flex: none;
    }
  }

  .cr-score {
    color: rgba(255, 255, 255, 0.72);
    font-variant-numeric: tabular-nums;
  }

  .cr-count {
    color: rgba(255, 255, 255, 0.45);
    font-size: 12px;
    margin-left: auto;
  }

  .cr-caret {
    display: inline-flex;
    color: rgba(255, 255, 255, 0.5);
    transition: transform 0.25s ease;
    &.open { transform: rotate(180deg); }
  }
}

.cr-body {
  padding: 0 14px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);

  .cr-summary {
    margin: 10px 0;
    color: rgba(255, 255, 255, 0.78);
    line-height: 1.7;
  }
}

.cr-issues {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;

  li {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 8px 10px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.04);
    border-left: 3px solid transparent;

    &.sev-error { border-left-color: #ff6b6b; }
    &.sev-warn { border-left-color: #ffb020; }
    &.sev-info { border-left-color: #00ff88; }
  }

  .cr-code {
    flex: none;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.75);
    line-height: 1.7;
  }

  .cr-msg {
    display: flex;
    flex-direction: column;
    gap: 3px;

    strong {
      font-weight: 600;
      color: rgba(255, 255, 255, 0.9);
      line-height: 1.6;
    }
    em {
      font-style: normal;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.5);
      line-height: 1.6;
    }
  }
}

.cr-suggest {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.03);

  .cr-suggest-title {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 6px;
  }

  ol {
    margin: 0;
    padding-left: 18px;
    color: rgba(255, 255, 255, 0.68);
    line-height: 1.8;
    font-size: 12px;
  }
}

.cr-foot {
  margin-top: 10px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  line-height: 1.6;
}

.cr-review {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(255, 255, 255, 0.12);

  .cr-review-btn {
    padding: 4px 12px;
    font-size: 12px;
    font-family: inherit;
    color: rgba(0, 200, 255, 0.9);
    background: rgba(0, 200, 255, 0.08);
    border: 1px solid rgba(0, 200, 255, 0.32);
    border-radius: 999px;
    cursor: pointer;

    &:hover:not(:disabled) { background: rgba(0, 200, 255, 0.18); }
    &:disabled { opacity: 0.45; cursor: not-allowed; }
  }

  .cr-review-hint {
    margin-left: 8px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.35);
  }

  .cr-review-off {
    margin: 8px 0 0;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.45);
  }

  .cr-review-summary {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 1.7;
    color: rgba(255, 255, 255, 0.82);
  }

  .cr-review-list {
    margin: 8px 0 0;
    padding-left: 18px;
    font-size: 12px;
    line-height: 1.75;

    .rv-dim {
      margin-right: 6px;
      padding: 1px 6px;
      font-size: 11px;
      color: rgba(0, 200, 255, 0.85);
      background: rgba(0, 200, 255, 0.1);
      border-radius: 4px;
    }

    .rv-quote {
      display: block;
      font-style: normal;
      font-size: 11px;
      color: rgba(255, 255, 255, 0.38);
    }

    .rv-high .rv-advice { color: #ff9b9b; }
    .rv-medium .rv-advice { color: #ffd479; }
  }
}

// 窄屏：分数与计数容易挤在一行，收起次要信息
@media (max-width: 640px) {
  .cr-head {
    flex-wrap: wrap;
    gap: 8px 12px;
    .cr-count { margin-left: 0; }
  }
}
</style>
