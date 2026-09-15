<template>
  <PanelShell
    type-id="animation"
    title="动画演示"
    desc="生成可直接播放的 HTML5 动画，用于课堂演示。风格由后端按学科自动选择。"
    :artifact="store.artifacts.animation"
    :running="running"
    :hint="hint"
    :can-generate="store.ready"
    @generate="handleGenerate"
  >
    <div class="anim-minutes">
      <span class="anim-label">动画时长</span>
      <el-input-number v-model="store.animationMinutes" :min="1" :max="15" :step="1" size="large" controls-position="right" />
      <span class="anim-unit">分钟</span>
    </div>
    <span class="anim-tip">与课时时长分开：课时 {{ store.duration }} 分钟，动画只占其中一段</span>
  </PanelShell>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import PanelShell from '../PanelShell.vue'
import { useLessonStore } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import { generateAnimation, contextPayload, assertContext } from '@/api/lessonArtifacts'

const store = useLessonStore()
const { running, hint, run } = useArtifactRunner('animation')

async function handleGenerate() {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  // 动画时长与课时时长是两个概念，默认 5 分钟而不是把 45 分钟课时塞进去
  const ok = await run(() => generateAnimation(contextPayload(store), { minutes: store.animationMinutes }))
  if (ok) ElMessage.success('动画生成完成')
}
</script>

<style lang="scss" scoped>
.anim-minutes {
  display: flex;
  align-items: center;
  gap: 6px;

  .anim-label, .anim-unit {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.55);
    white-space: nowrap;
  }
}

.anim-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
</style>
