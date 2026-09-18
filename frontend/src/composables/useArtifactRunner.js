import { computed, ref } from 'vue'
import { useLessonStore } from '@/store/lesson'

/**
 * 单个产物的生成执行器。
 *
 * 收敛了四类产物共同的「状态机 + 提示」逻辑，避免每个面板各写一遍：
 *   idle → running → done | failed
 *
 * 关键约定（与第一阶段一致）：
 *  1. 失败只记在**这一个**产物上，其他已完成的产物不受影响。
 *  2. 不吞异常：错误文案进 artifact.error，由 ArtifactCard 原样展示给用户。
 *  3. 恢复存档时 running 会被降级成 idle（见 store.hydrate），所以这里不用担心"永久转圈"。
 *
 * `running` 从 store 派生而不是用本地 ref：工作台的对话和面板的按钮都能触发生成，
 * 各自持有一个本地 ref 的话，谁触发的就只有谁的按钮会转圈，另一处看起来像卡住了。
 */
export function useArtifactRunner(artifactId) {
  const store = useLessonStore()
  const running = computed(() => store.artifacts[artifactId]?.status === 'running')
  const hint = ref('')

  async function run(task) {
    if (store.artifacts[artifactId]?.status === 'running') return false
    store.setArtifact(artifactId, { status: 'running', error: '', summary: '', at: Date.now() })
    hint.value = ''
    try {
      const patch = await task(text => { hint.value = text || '' })
      store.setArtifact(artifactId, { status: 'done', ...patch, error: '', at: Date.now() })
      store.pushArtifact(artifactId)
      return true
    } catch (e) {
      store.setArtifact(artifactId, {
        status: 'failed',
        error: e?.message || '生成失败，请重试',
        at: Date.now()
      })
      store.pushArtifact(artifactId)
      return false
    } finally {
      hint.value = ''
    }
  }

  return { running, hint, run }
}
