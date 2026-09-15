<template>
  <section class="panel-shell">
    <header class="ps-head">
      <h2>{{ title }}</h2>
      <p v-if="desc">{{ desc }}</p>
    </header>

    <div class="ps-form">
      <slot />
      <el-button
        type="primary"
        size="large"
        :loading="running"
        :disabled="!canGenerate"
        @click="emit('generate')"
      >
        <el-icon><MagicStick /></el-icon>
        {{ buttonText }}
      </el-button>
    </div>

    <div v-if="running" class="ps-progress">
      <el-progress
        :percentage="resolvedPercent"
        :stroke-width="8"
        :indeterminate="resolvedPercent <= 0"
        :show-text="resolvedPercent > 0"
      />
      <span class="ps-hint">{{ hint || '正在生成，完成后会自动出现在这里' }}</span>
    </div>

    <ArtifactCard
      :type-id="typeId"
      :artifact="artifact"
      :can-generate="canGenerate"
      @generate="emit('generate')"
    />

    <div v-if="$slots.after" class="ps-after">
      <slot name="after" />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import ArtifactCard from './ArtifactCard.vue'

const props = defineProps({
  typeId: { type: String, required: true },
  title: { type: String, required: true },
  desc: { type: String, default: '' },
  artifact: { type: Object, required: true },
  running: { type: Boolean, default: false },
  /** null 表示不确定进度（后端没给百分比），此时进度条走 indeterminate */
  percent: { type: Number, default: null },
  hint: { type: String, default: '' },
  canGenerate: { type: Boolean, default: true }
})
const emit = defineEmits(['generate'])

const resolvedPercent = computed(() => (props.percent === null ? 0 : Math.round(props.percent)))
const buttonText = computed(() => {
  if (props.running) return '生成中'
  return props.artifact.status === 'done' ? '重新生成' : '开始生成'
})
</script>

<style lang="scss" scoped>
.panel-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ps-head {
  h2 {
    font-size: 20px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 6px;
  }

  p {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.6;
  }
}

.ps-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px;
  background: rgba(10, 14, 39, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.12);
  border-radius: 12px;
}

.ps-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;

  .ps-hint {
    font-size: 12px;
    color: rgba(0, 200, 255, 0.8);
  }
}

.ps-after {
  margin-top: 4px;
}
</style>
