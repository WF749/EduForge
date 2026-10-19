import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 轻量知识库（与 /rag 那套企业级检索并存的两组接口）。
 *
 * 为什么两套都留：/knowledge/* 是早期分块存储，/rag/* 是向量 + BM25 + rerank。
 * 两边存的不是同一批数据，界面上必须分开管理，混在一起会让教师以为"删了没生效"。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(res, fallback) {
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data || {}
}

export async function fetchKnowledgeStats() {
  return readJson(await trackedFetch(`${BASE()}/knowledge/stats`), '统计读取失败')
}

export async function listKnowledgeDocuments(limit = 100) {
  const data = await readJson(
    await trackedFetch(`${BASE()}/knowledge/documents?limit=${limit}`),
    '文档列表读取失败'
  )
  return Array.isArray(data.documents) ? data.documents : []
}

export async function queryKnowledge(query, topK = 5) {
  const res = await trackedFetch(`${BASE()}/knowledge/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK })
  })
  const data = await readJson(res, '检索失败')
  return Array.isArray(data.results) ? data.results : []
}

export async function deleteKnowledgeDocument(docId) {
  return readJson(
    await trackedFetch(`${BASE()}/knowledge/document/${encodeURIComponent(docId)}`, {
      method: 'DELETE'
    }),
    '删除失败'
  )
}

/**
 * 清空轻量知识库。
 *
 * 危险操作：只清这一套，不动 /rag 里的种子索引与文档。
 * 调用方必须二次确认，并把"会清掉什么、不会清掉什么"写清楚。
 */
export async function clearKnowledge() {
  return readJson(
    await trackedFetch(`${BASE()}/knowledge/clear`, { method: 'DELETE' }),
    '清空失败'
  )
}
