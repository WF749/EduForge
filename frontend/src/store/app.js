import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { installDataFlowInterceptor } from '@/api/dataFlow'

const api = axios.create({
  baseURL: resolveApiBaseURL(),
  timeout: 60000
})

// 记录每次响应的数据流向（只读响应头，不改变任何请求/响应）
installDataFlowInterceptor(api)

export const useAppStore = defineStore('app', () => {
  // 状态
  const config = ref({
    llm_provider: 'demo',
    api_key_configured: false
  })
  const conversations = ref([])
  const currentConversation = ref(null)
  const uploadedFiles = ref([])
  const knowledgeStats = ref({ total_chunks: 0 })
  const isLoading = ref(false)

  // 计算属性
  const hasApiKey = computed(() => config.value.api_key_configured)

  // 方法
  async function fetchConfig() {
    try {
      const res = await api.get('/llm/config')
      config.value = res.data
      // 从providers数组中找到激活的提供商
      const activeProvider = res.data.providers.find(p => p.is_active)
      if (activeProvider) {
        config.value.llm_provider = activeProvider.provider
        config.value.api_key_configured = activeProvider.has_api_key
      } else {
        config.value.llm_provider = 'demo'
        config.value.api_key_configured = false
      }
    } catch (e) {
      console.error('获取配置失败:', e)
      // 出错时使用默认值
      config.value.llm_provider = 'demo'
      config.value.api_key_configured = false
    }
  }

  async function updateProviderConfig(provider, apiKey) {
    try {
      // 使用新的LLM配置接口
      const configData = {
        provider: provider,
        api_key: apiKey,
        is_active: true
      }
      
      const res = await api.post('/llm/config', configData)
      return res.data
    } catch (e) {
      console.error('更新提供商配置失败:', e)
      throw e
    }
  }

  // 完整的配置保存方法 - 使用新的统一API
  async function saveFullConfig(config) {
    try {
      console.log('开始保存完整配置到后端:', config)

      // 使用新的统一API端点
      const response = await api.post('/llm/save-full-config', config)
      console.log('保存配置响应:', response.data)
      
      if (!response.data.success) {
        throw new Error(`保存配置失败: ${response.data.message}`)
      }

      // 刷新配置状态
      await fetchConfig()
      console.log('配置状态已刷新')

      return response.data
    } catch (e) {
      console.error('保存完整配置失败:', e)
      if (e.code === 'ERR_NETWORK' || e.message.includes('Network Error')) {
        throw new Error('后端服务未启动或无法连接')
      }
      throw e
    }
  }

  async function updateKnowledgeConfig(config) {
    try {
      const res = await api.post('/config/knowledge', null, {
        params: config
      })
      return res.data
    } catch (e) {
      console.error('更新知识库配置失败:', e)
      throw e
    }
  }

  async function updateFileConfig(config) {
    try {
      // 处理 allowedTypes 数组
      const params = { ...config }
      if (params.allowedTypes && Array.isArray(params.allowedTypes)) {
        // 将数组转换为逗号分隔的字符串
        params.allowedTypes = params.allowedTypes.join(',')
      }
      
      const res = await api.post('/config/file', null, {
        params: params
      })
      return res.data
    } catch (e) {
      console.error('更新文件配置失败:', e)
      throw e
    }
  }

  async function sendMessage(message, conversationId = null, attachments = []) {
    isLoading.value = true
    try {
      const res = await api.post('/chat/send', {
        message,
        conversation_id: conversationId,
        attachments: attachments || []
      })
      return res.data
    } catch (e) {
      console.error('发送消息失败:', e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function getChatHistory(conversationId) {
    try {
      const res = await api.get(`/chat/history?conversation_id=${conversationId}`)
      return res.data
    } catch (e) {
      console.error('获取历史失败:', e)
      return null
    }
  }

  async function getConversations() {
    try {
      const res = await api.get('/chat/conversations')
      conversations.value = res.data.conversations
      return res.data
    } catch (e) {
      console.error('获取会话列表失败:', e)
      return { success: false, conversations: [] }
    }
  }

  async function understandIntent(message, conversationId) {
    isLoading.value = true
    try {
      const res = await api.post('/chat/understand-intent', {
        message,
        conversation_id: conversationId
      })
      return res.data
    } finally {
      isLoading.value = false
    }
  }

  async function uploadFile(file, category = 'general', addToKnowledge = false) {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const url = addToKnowledge ? '/upload/file?add_to_knowledge=true' : '/upload/file'
      const res = await api.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000
      })
      // 确保返回 file_id 字段（兼容 ChatView 使用 file_id）
      const data = res.data
      if (!data.file_id) data.file_id = data.filename
      return data
    } catch (e) {
      console.error('上传失败:', e)
      throw e
    }
  }

  async function fetchUploadedFiles() {
    try {
      const res = await api.get('/upload/files')
      uploadedFiles.value = res.data.files
      return res.data
    } catch (e) {
      console.error('获取文件列表失败:', e)
      return { files: [] }
    }
  }

  async function processFile(fileId) {
    try {
      const res = await api.post(`/upload/process/${fileId}`)
      return res.data
    } catch (e) {
      console.error('处理文件失败:', e)
      throw e
    }
  }

  async function addToKnowledge(fileId) {
    try {
      const res = await api.post(`/knowledge/add-file/${fileId}`)
      return res.data
    } catch (e) {
      console.error('添加到知识库失败:', e)
      throw e
    }
  }

  async function fetchKnowledgeStats() {
    try {
      const res = await api.get('/knowledge/stats')
      knowledgeStats.value = res.data
      return res.data
    } catch (e) {
      console.error('获取知识库统计失败:', e)
      return null
    }
  }

  async function fetchKnowledgeDocuments(limit = 100) {
    try {
      const res = await api.get('/knowledge/documents', { params: { limit } })
      return res.data?.documents || []
    } catch (e) {
      console.error('获取知识库文档列表失败:', e)
      return []
    }
  }

  async function queryKnowledge(query, topK = null) {
    try {
      const payload = { query }
      if (topK) payload.top_k = topK
      const res = await api.post('/knowledge/query', payload)
      return res.data
    } catch (e) {
      console.error('查询知识库失败:', e)
      return null
    }
  }

  async function generateCourseware(generationReq) {
    isLoading.value = true
    try {
      const { requirements, reference_files, conversation_id } = generationReq
      
      // 转换为后端接口期望的参数格式，传递所有可用参数
      const params = {
        topic: requirements.topic,
        duration: requirements.duration,
        audience: requirements.target_audience,
        format: 'PPT+Word',
        subject: requirements.subject || 'general',
        template: requirements.template || 'standard',
        theme_color: requirements.theme_color || '蓝色系',
        key_points: requirements.key_points || []
      }
      
      const res = await api.post('/courseware/generate', params)
      return res.data
    } finally {
      isLoading.value = false
    }
  }

  async function getGenerationStatus(taskId) {
    try {
      const res = await api.get(`/ppt/status/${taskId}`)
      return res.data
    } catch (e) {
      console.error('获取生成状态失败:', e)
      return { success: false, status: 'unknown', message: e?.message || 'error' }
    }
  }

  async function previewCourseware(topic) {
    try {
      const res = await api.get(`/courseware/preview?topic=${encodeURIComponent(topic)}`)
      return res.data
    } catch (e) {
      console.error('预览课件失败:', e)
      return null
    }
  }

  async function downloadCoursewareFile(format, taskDir, topic) {
    try {
      const url = `/api/courseware/download/${format}?task_dir=${encodeURIComponent(taskDir)}&topic=${encodeURIComponent(topic)}`
      window.open(url, '_blank')
      return true
    } catch (e) {
      console.error('下载文件失败:', e)
      throw e
    }
  }

  return {
    // 状态
    config,
    conversations,
    currentConversation,
    uploadedFiles,
    knowledgeStats,
    isLoading,
    // 计算属性
    hasApiKey,
    // 方法
    fetchConfig,
    updateProviderConfig,
    saveFullConfig,
    updateKnowledgeConfig,
    updateFileConfig,
    sendMessage,
    getChatHistory,
    getConversations,
    understandIntent,
    uploadFile,
    fetchUploadedFiles,
    processFile,
    addToKnowledge,
    fetchKnowledgeStats,
    fetchKnowledgeDocuments,
    queryKnowledge,
    generateCourseware,
    getGenerationStatus,
    previewCourseware,
    downloadCoursewareFile,
    // API实例
    api
  }
})
