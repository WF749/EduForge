import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 企业级 RAG：检索、文档、索引状态。
 * 挂载前缀是 /api/rag，所以这里写的路径都不带 /api。
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

/** 索引与两通道可用状态。降级（比如只有关键词检索）要能在界面上说明白。 */
export async function fetchRagStatus() {
  return readJson(await trackedFetch(`${BASE()}/rag/status`), '检索状态读取失败')
}

/**
 * 混合检索。
 *
 * `refused=true` 表示判定为"知识库里没有" —— 调用方必须明确告知，
 * 不能让模型自由发挥，否则教师会以为这段答案是查到的。
 */
export async function searchKnowledge({ query, topK = 5, rerank = true }) {
  return readJson(await post('/rag/search', {
    query,
    top_k: topK,
    rerank
  }), '检索失败')
}

export async function listRagDocuments() {
  return readJson(await trackedFetch(`${BASE()}/rag/documents`), '文档列表读取失败')
}

export async function addRagDocument({ documentId, content, metadata }) {
  return readJson(await post('/rag/documents', {
    document_id: documentId,
    content,
    metadata: metadata || {}
  }), '文档入库失败')
}

export async function deleteRagDocument(documentId) {
  return readJson(
    await trackedFetch(`${BASE()}/rag/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE'
    }),
    '文档删除失败'
  )
}

/**
 * 重建**种子**索引。
 *
 * 只重建 knowledge_base/ 下的内置文档，用户上传的资料不受影响 ——
 * 这条语义必须写进界面，否则教师会以为点了就会把自己传的资料清掉。
 */
export async function reindexSeed() {
  return readJson(await post('/rag/reindex', {}), '索引重建失败')
}
