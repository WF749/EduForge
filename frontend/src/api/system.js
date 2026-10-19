import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 系统与可观测性：厂商元数据、运行指标、健康检查。
 * 这一组是运维向能力，页面放在「系统监控」里，导航上标注为运维。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(res, fallback) {
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data || {}
}

/** 厂商元数据（不含任何密钥） */
export async function fetchProviders() {
  return readJson(await trackedFetch(`${BASE()}/providers`), '厂商列表读取失败')
}

/** 可观测性：调用次数、成功率、P95 延迟、token 与成本 */
export async function fetchMetrics({ window: win, recent = 0 } = {}) {
  const params = new URLSearchParams()
  if (win) params.set('window', String(win))
  if (recent > 0) params.set('recent', String(recent))
  const qs = params.toString()
  return readJson(
    await trackedFetch(`${BASE()}/metrics${qs ? '?' + qs : ''}`),
    '指标读取失败'
  )
}

/** 按类型查看调用明细（llm / tool / agent / request） */
export async function fetchMetricEvents({ kind = '', limit = 100 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (kind) params.set('kind', kind)
  return readJson(
    await trackedFetch(`${BASE()}/metrics/events?${params.toString()}`),
    '调用明细读取失败'
  )
}

/** 健康检查。失败时后端根本连不上，所以这里不能抛，只如实返回状态。 */
export async function fetchHealth() {
  try {
    const res = await trackedFetch(`${BASE()}/health`)
    return { ok: res.ok, status: res.status }
  } catch (e) {
    return { ok: false, status: 0, error: e?.message || '无法连接后端' }
  }
}
