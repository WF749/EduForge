<template>
  <div class="wb-empty" role="status">
    <div class="wb-empty__icon" aria-hidden="true">
      <el-icon :size="28"><component :is="icon" /></el-icon>
    </div>
    <p class="wb-empty__title">{{ title }}</p>
    <p v-if="description" class="wb-empty__desc">{{ description }}</p>
    <div v-if="$slots.action" class="wb-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
/**
 * 空状态。
 *
 * 空态不是"没东西可画"，而是**新用户最需要被引导的一刻**：
 * 所以除了"这里还没有数据"，还必须说清"下一步点哪"。
 * `description` 讲原因，`action` 插槽放唯一的主按钮（不要放两个，选择成本比空白更劝退）。
 */
defineProps({
  title: { type: String, default: '这里还没有内容' },
  description: { type: String, default: '' },
  icon: { type: [String, Object], default: 'Inbox' }
})
</script>

<style scoped>
.wb-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: var(--sp-7) var(--sp-4);
  text-align: center;
  color: var(--wb-text-3);
}

.wb-empty__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--wb-surface-2);
  border: 1px solid var(--wb-border);
  color: var(--wb-text-3);
  margin-bottom: var(--sp-1);
}

.wb-empty__title {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--wb-text);
}

.wb-empty__desc {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
  max-width: 420px;
  line-height: 1.7;
}

.wb-empty__action {
  margin-top: var(--sp-3);
}
</style>
