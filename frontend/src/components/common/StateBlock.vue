<template>
  <div class="wb-state">
    <!--
      加载中：骨架屏 + **文字**。
      只给骨架屏等于"没有信息" —— 教师无法区分"在加载"和"卡死了"。
      超过 slowAfter 说明服务可能正忙（例如另一端在跑生成任务）；
      超过 timeoutAfter 就给出重试，而不是让他一直等到地老天荒。
    -->
    <div v-if="loading" class="wb-state__body" aria-busy="true" aria-live="polite">
      <el-skeleton :rows="rows" animated />
      <p v-if="hint" class="wb-state__hint">{{ hint }}</p>
      <p v-if="slow && !timedOut" class="wb-state__hint wb-state__hint--warn">
        <el-icon><Loading /></el-icon>
        {{ slowHint }}
      </p>
      <template v-if="timedOut">
        <p class="wb-state__desc">{{ timeoutHint }}</p>
        <el-button size="small" @click="$emit('retry')">
          <el-icon><RefreshRight /></el-icon>
          重试
        </el-button>
      </template>
    </div>

    <!-- 失败：必须给重试，否则教师只能刷新整页 -->
    <div v-else-if="error" class="wb-state__body" role="alert">
      <div class="wb-state__icon wb-state__icon--error" aria-hidden="true">
        <el-icon :size="22"><WarningFilled /></el-icon>
      </div>
      <p class="wb-state__title">{{ errorTitle }}</p>
      <p class="wb-state__desc">{{ error }}</p>
      <el-button v-if="retryable" size="small" @click="$emit('retry')">
        <el-icon><RefreshRight /></el-icon>
        重试
      </el-button>
    </div>

    <!-- 空数据 -->
    <EmptyState
      v-else-if="empty"
      :title="emptyTitle"
      :description="emptyDescription"
      :icon="emptyIcon"
    >
      <template v-if="$slots.emptyAction" #action>
        <slot name="emptyAction" />
      </template>
    </EmptyState>

    <!-- 正常：内容 -->
    <slot v-else />
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Loading, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'

/**
 * 四态容器：加载 / 慢加载 / 失败 / 空 / 正常。
 *
 * 存在的理由：这些状态如果不集中管理，每个页面都会漏掉一两个 ——
 * 而漏掉的那个恰恰是最容易出事的地方（请求失败但界面一片空白，没人知道发生了什么）。
 *
 * 「慢加载」这一态是 2026-10-16 补的：生成任务在跑时后端会忙不过来，
 * 其它页面的请求要排队。此前界面只是**一直转骨架屏**，教师无从判断是
 * "还在加载"还是"系统坏了"。现在会明说原因，并在等太久之后给重试。
 */
const props = defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  empty: { type: Boolean, default: false },
  /** 加载中的补充说明，例如"正在读取备课记录…" */
  hint: { type: String, default: '' },
  rows: { type: Number, default: 3 },
  errorTitle: { type: String, default: '加载失败' },
  emptyTitle: { type: String, default: '这里还没有内容' },
  emptyDescription: { type: String, default: '' },
  emptyIcon: { type: [String, Object], default: 'Inbox' },
  /** 有些失败重试也没用（如 404），由调用方关掉按钮 */
  retryable: { type: Boolean, default: true },
  /** 多久算"慢"（毫秒） */
  slowAfter: { type: Number, default: 4000 },
  /** 等多久算"太久了"，给出重试 */
  timeoutAfter: { type: Number, default: 25000 },
  slowHint: { type: String, default: '服务响应比平时慢，可能正在生成内容，请稍等' },
  timeoutHint: { type: String, default: '等太久了。生成任务会占用较长时间，可以稍后再来，或直接重试。' }
})

defineEmits(['retry'])

const slow = ref(false)
const timedOut = ref(false)
let slowTimer = null
let timeoutTimer = null

function clearTimers() {
  if (slowTimer) { clearTimeout(slowTimer); slowTimer = null }
  if (timeoutTimer) { clearTimeout(timeoutTimer); timeoutTimer = null }
}

watch(() => props.loading, v => {
  clearTimers()
  slow.value = false
  timedOut.value = false
  if (!v) return
  slowTimer = setTimeout(() => { slow.value = true }, props.slowAfter)
  timeoutTimer = setTimeout(() => { timedOut.value = true }, props.timeoutAfter)
}, { immediate: true })

onBeforeUnmount(clearTimers)
</script>

<style scoped>
.wb-state__body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6) var(--sp-4);
  text-align: center;
}

.wb-state__icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
}

.wb-state__icon--error {
  background: var(--danger-bg);
  color: var(--wb-risk-text);
}

.wb-state__title {
  margin: 0;
  font-weight: 600;
  color: var(--wb-text);
}

.wb-state__desc {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
  max-width: 460px;
  line-height: 1.7;
}

.wb-state__hint {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
}

.wb-state__hint--warn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--wb-warn-text);
  background: var(--wb-warn-bg);
  padding: 4px 12px;
  border-radius: var(--radius-pill);
}
</style>
