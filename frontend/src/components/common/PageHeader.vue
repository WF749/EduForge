<template>
  <header class="wb-header">
    <div class="wb-header__main">
      <div class="wb-header__text">
        <h1 class="wb-header__title">
          {{ title }}
          <span v-if="badge" class="wb-header__badge">{{ badge }}</span>
        </h1>
        <!-- 每页一句话说清"这页能拿来干什么"，新用户不需要猜 -->
        <p v-if="description" class="wb-header__desc">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="wb-header__actions">
        <slot name="actions" />
      </div>
    </div>
    <div v-if="$slots.extra" class="wb-header__extra">
      <slot name="extra" />
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  badge: { type: String, default: '' }
})
</script>

<style scoped>
.wb-header {
  margin-bottom: var(--sp-5);
}

.wb-header__main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
}

.wb-header__title {
  font-size: var(--fs-xl);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.wb-header__badge {
  font-size: var(--fs-xs);
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
}

.wb-header__desc {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
  max-width: 760px;
  line-height: 1.7;
}

.wb-header__actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.wb-header__extra {
  margin-top: var(--sp-4);
}

@media (max-width: 768px) {
  .wb-header__title { font-size: var(--fs-lg); }
  .wb-header__main { flex-direction: column; }
}
</style>
