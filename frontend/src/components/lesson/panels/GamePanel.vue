<template>
  <PanelShell
    type-id="game"
    title="互动游戏"
    desc="生成可直接在浏览器里玩的 HTML5 小游戏，题型取自本节课的要点。"
    :artifact="store.artifacts.game"
    :running="running"
    :hint="hint"
    :can-generate="store.ready"
    @generate="handleGenerate"
  >
    <el-select v-model="store.gameType" size="large" style="width: 190px" placeholder="游戏类型">
      <el-option v-for="t in gameTypes" :key="t.id" :label="t.name" :value="t.id">
        <span>{{ t.name }}</span>
        <span class="game-desc">{{ t.description }}</span>
      </el-option>
    </el-select>
  </PanelShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import PanelShell from '../PanelShell.vue'
import { useLessonStore } from '@/store/lesson'
import { useArtifactRunner } from '@/composables/useArtifactRunner'
import { generateGame, contextPayload, assertContext } from '@/api/lessonArtifacts'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

const store = useLessonStore()
const { running, hint, run } = useArtifactRunner('game')

// 先从后端拉真实题型；拉不到才用内置兜底，兜底值与后端默认保持一致
const gameTypes = ref([
  { id: '选择题', name: '知识问答', description: '选择题形式测知识点' },
  { id: '填空题', name: '填空挑战', description: '填写正确答案' },
  { id: '匹配题', name: '连连看', description: '匹配相关概念' },
  { id: '排序题', name: '排序挑战', description: '按正确顺序排列' },
  { id: '闯关游戏', name: '知识闯关', description: '逐关挑战获取胜利' }
])

onMounted(async () => {
  try {
    const res = await trackedFetch(`${resolveApiBaseURL()}/courseware/game/types`)
    const data = await res.json()
    if (data?.success && Array.isArray(data.types) && data.types.length) {
      gameTypes.value = data.types
      // 只在当前选项不在后端列表里时才纠正，别每次进页面都重置用户的选择
      if (!data.types.some(t => t.id === store.gameType)) store.gameType = data.types[0].id
    }
  } catch {
    /* 拉不到就用内置列表，不打断页面 */
  }
})

async function handleGenerate() {
  try {
    assertContext(store)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  const ok = await run(() => generateGame(contextPayload(store), { gameType: store.gameType }))
  if (ok) ElMessage.success('互动游戏生成完成')
}
</script>

<style lang="scss" scoped>
.game-desc {
  float: right;
  margin-left: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
