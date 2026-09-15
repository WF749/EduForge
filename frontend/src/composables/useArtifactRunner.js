import { ref } from 'vue'
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
 */
export function useArtifactRunner(artifactId) {
  const store = useLessonStore()
  const running = ref(false)
  const hint = ref('')

  async function run(task) {
    if (store.artifacts[artifactId]?.status === 'running') return false
    store.setArtifact(artifactId, { status: 'running', error: '', summary: '', at: Date.now() })
    running.value = true
    hint.value = ''
    try {
      const patch = await task(text => { hint.value = text || '' })
      store.setArtifact(artifactId, { status: 'done', ...patch, error: '', at: Date.now() })
      return true
    } catch (e) {
      store.setArtifact(artifactId, {
        status: 'failed',
        error: e?.message || '生成失败，请重试',
        at: Date.now()
      })
      return false
    } finally {
      running.value = false
      hint.value = ''
    }
  }

  return { running, hint, run }
}
