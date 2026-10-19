import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * Agent 能力：工具清单、任务规划、执行。
 *
 * 人机协同（红线）：默认**不**自动批准高风险操作。只有请求里显式带上
 * `approvals` 才放行对应工具，所以这里把 approvals 做成显式入参，
 * 绝不默认填空数组就发 —— 那等于替教师批准了高风险动作。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(res, fallback) {
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data || {}
}

function post(path, body) {
  return trackedFetch(`${BASE()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

export async function fetchAgentTools() {
  return readJson(await trackedFetch(`${BASE()}/agent/tools`), '工具清单读取失败')
}

/** 只做任务拆解，不执行 —— 用来给教师看"它打算怎么做" */
export async function planAgent(goal) {
  return readJson(await post('/agent/plan', { goal }), '任务规划失败')
}

/** 完整运行一次（同步返回，适合短任务与调试） */
export async function runAgent({ goal, approvals = [], maxSteps = 6, verify = true, grade = '', subject = '' }) {
  return readJson(await post('/agent/run', {
    goal,
    approvals,
    max_steps: maxSteps,
    verify,
    grade,
    subject
  }), 'Agent 运行失败')
}
