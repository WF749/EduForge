<template>
  <PanelShell
    type-id="lesson_plan"
    title="教案"
    desc="按学段与课时生成结构化教案，导出 Word。参考资料的正文会一并参与生成。"
    :artifact="store.artifacts.lesson_plan"
    :running="running"
    :hint="hint"
    :can-generate="store.ready"
    @generate="handleGenerate"
  >
    <el-tag type="info" size="large" effect="plain">导出 Word（.docx）</el-tag>
    <span class="lp-tip">学段：{{ store.level }} · 学科：{{ store.subject }} · 年级：{{ store.grade }} · 课时：{{ store.duration }} 分钟</span>
  </PanelShell>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import PanelShell from '../PanelShell.vue'
import { useLessonStore } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import { generateLessonPlan, contextPayload, assertContext } from '@/api/lessonArtifacts'

const store = useLessonStore()
const { running, hint, run } = useArtifactRunner('lesson_plan')

async function handleGenerate() {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  const ok = await run(() => generateLessonPlan(contextPayload(store)))
  if (ok) ElMessage.success('教案生成完成')
}
</script>

<style lang="scss" scoped>
.lp-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
</style>
