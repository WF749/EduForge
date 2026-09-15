<template>
  <PanelShell
    type-id="ppt"
    title="PPT 课件"
    desc="先建后台任务再轮询真实进度，完成后可下载 .pptx，也可进入预览页继续修改。"
    :artifact="store.artifacts.ppt"
    :running="running"
    :percent="percent"
    :hint="hint || progressText"
    :can-generate="store.ready"
    @generate="handleGenerate"
  >
    <el-select v-model="store.pptTheme" size="large" style="width: 150px">
      <el-option v-for="c in THEME_COLORS" :key="c" :label="c" :value="c" />
    </el-select>
    <span class="ppt-tip">主题色会随请求一起发给后端，不是前端换个皮肤</span>
  </PanelShell>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import PanelShell from '../PanelShell.vue'
import { useLessonStore, THEME_COLORS } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import { generatePpt, contextPayload, assertContext } from '@/api/lessonArtifacts'

const store = useLessonStore()
const { running, hint, run } = useArtifactRunner('ppt')
const percent = ref(null)
const progressText = ref('')

async function handleGenerate() {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  percent.value = 0
  progressText.value = '正在创建任务'
  const ok = await run((setHint) => generatePpt(contextPayload(store), {
    themeColor: store.pptTheme,
    onProgress: (value, step) => {
      percent.value = value
      const text = step ? `${step}（${value}%）` : `已完成 ${value}%`
      progressText.value = text
      setHint(text)
    }
  }))
  percent.value = null
  progressText.value = ''
  if (ok) ElMessage.success('PPT 生成完成')
}
</script>

<style lang="scss" scoped>
.ppt-tip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
}
</style>
