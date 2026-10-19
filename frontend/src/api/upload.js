import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'

/**
 * 资料上传与入库。
 *
 * 上传用 multipart（不能走 JSON），但**仍然过 trackedFetch** ——
 * 数据出校的观测要覆盖到这一条链路，否则上传是唯一"看不见"的数据出口。
 */

const BASE = () => resolveApiBaseURL()

async function readJson(res, fallback) {
  const data = await res.json().catch(() => null)
  if (!res.ok || data?.success === false) {
    throw new Error(data?.detail || data?.message || fallback)
  }
  return data || {}
}

/**
 * 上传文件。
 *
 * `addToKnowledge=true` 时后端会顺手切分入库；扫描版 PDF 提取不出文本，
 * 后端会返回 success=false 并说明原因 —— 这里原样抛出给界面，不替它圆场。
 */
export async function uploadFile(file, { addToKnowledge = false } = {}) {
  const form = new FormData()
  form.append('file', file)
  const qs = addToKnowledge ? '?add_to_knowledge=true' : ''
  return readJson(
    await trackedFetch(`${BASE()}/upload/file${qs}`, { method: 'POST', body: form }),
    '上传失败'
  )
}

export async function listUploadedFiles() {
  const data = await readJson(
    await trackedFetch(`${BASE()}/upload/files`),
    '文件列表读取失败'
  )
  return Array.isArray(data.files) ? data.files : []
}

/** 只解析文本，不入库。用来先确认这份资料能不能提取出内容。 */
export async function processUpload(fileId) {
  return readJson(
    await trackedFetch(`${BASE()}/upload/process/${encodeURIComponent(fileId)}`, {
      method: 'POST'
    }),
    '解析失败'
  )
}

/** 把已上传的文件补进知识库 */
export async function addFileToKnowledge(fileId) {
  return readJson(
    await trackedFetch(`${BASE()}/knowledge/add-file/${encodeURIComponent(fileId)}`, {
      method: 'POST'
    }),
    '入库失败'
  )
}
