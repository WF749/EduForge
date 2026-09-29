import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 教学蓝图接口。
 *
 * 只有两个调用点，故意保持很小：蓝图是"生成前的对齐环节"，
 * 不是业务流程本身。把它塞进 lessonArtifacts 会让生成失败与蓝图失败互相拖累。
 *
 * 约定：**蓝图失败不能阻断正式生成**。
 * 因此 requestBlueprint 只把后端给的 degraded/error 原样带回，
 * 由调用方决定怎么提示 —— 绝不在这里抛异常中断生成流程。
 */

const BASE = () => resolveApiBaseURL()

async function post(path, body, fallback) {
  const res = await trackedFetch(`${BASE()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const data = await res.json()
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data
}

/**
 * 生成教学蓝图（课堂环节安排）。
 *
 * @returns {{ blueprint, intent, knowledge, degraded, error }}
 *   `degraded=true` 表示模型没生成成功、用的是离线骨架 —— 仍然可用，
 *   调用方必须允许教师"直接生成"。
 */
export async function requestBlueprint({ intent, scope = 'both', lessonId = '', topic = '' }) {
  try {
    return await post('/teaching/blueprint', {
      teachingIntent: intent || undefined,
      knowledgeScope: scope,
      lessonId: lessonId || undefined,
      topic: topic || undefined
    }, '教学蓝图生成失败')
  } catch (e) {
    // 蓝图是锦上添花：失败必须可恢复，交给上层走"直接生成"
    return { success: false, degraded: true, error: e.message || '蓝图服务未响应', blueprint: null }
  }
}

/** 校验教师改过的蓝图。**只返回提示**，不做任何拦截。 */
export async function validateBlueprint({ blueprint, intent }) {
  try {
    const d = await post('/teaching/blueprint/validate', {
      teachingBlueprint: blueprint || undefined,
      teachingIntent: intent || undefined
    }, '蓝图校验失败')
    return { warnings: Array.isArray(d.warnings) ? d.warnings : [], totalMinutes: d.totalMinutes || 0 }
  } catch {
    return { warnings: [], totalMinutes: 0 }
  }
}
