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

    <RevisionBar kind="lesson_plan" @revised="handleRevised" />
  </PanelShell>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import PanelShell from '../PanelShell.vue'
import RevisionBar from '../RevisionBar.vue'
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
  // 生成时要带上课程 id，后端才会把成品落为该课教案的 v1；
  // 没有 id 就先同步一次（幂等 upsert），否则后面"按指令修改"没有基线。
  if (!store.taskId) await store.syncContext()
  const ok = await run(() => generateLessonPlan(contextPayload(store)))
  if (ok) ElMessage.success('教案生成完成')
}

/** 迭代条改完/回退后：产物还是同一份 docx（文件名按课题，会被覆盖），只需刷新指针与合规结论 */
function handleRevised(out) {
  const prev = store.artifacts.lesson_plan
  store.setArtifact('lesson_plan', {
    downloadUrl: out.downloadUrl || prev.downloadUrl,
    fileName: out.fileName || prev.fileName,
    compliance: out.compliance || prev.compliance,
    summary: out.version?.version ? `第 ${out.version.version} 版` : prev.summary
  })
  store.pushArtifact('lesson_plan')
}
</script>

<style lang="scss" scoped>
.lp-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
</style>
