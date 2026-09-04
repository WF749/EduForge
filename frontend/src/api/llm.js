import axios from 'axios'
import { resolveApiBaseURL } from './baseUrl'
import { installDataFlowInterceptor } from './dataFlow'

// 创建axios实例
const apiClient = axios.create({
  baseURL: resolveApiBaseURL(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 记录每次响应的数据流向（只读响应头，不改变任何请求/响应）
installDataFlowInterceptor(apiClient)

// 重试机制
apiClient.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config
    
    // 只重试500错误和网络错误，最多重试3次
    if ((error.response?.status === 500 || !error.response) && !originalRequest._retryCount) {
      originalRequest._retryCount = 1
      
      // 等待2秒后重试
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      try {
        return apiClient(originalRequest)
      } catch (retryError) {
        // 第二次尝试失败后，再等待3秒重试
        if (!originalRequest._retryCount2) {
          originalRequest._retryCount2 = 1
          await new Promise(resolve => setTimeout(resolve, 3000))
          return apiClient(originalRequest)
        }
        throw retryError
      }
    }
    
    throw error
  }
)

// LLM API封装
export const llmApi = {
  // 获取配置
  getConfig: async () => {
    const response = await apiClient.get('/llm/config')
    return response.data
  },
  
  // 保存配置
  saveConfig: async (configData) => {
    const response = await apiClient.post('/llm/config', configData)
    return response.data
  },
  
  // 保存完整配置
  saveFullConfig: async (configData) => {
    const response = await apiClient.post('/llm/save-full-config', configData)
    return response.data
  },
  
  // 测试连接
  testConnection: async (testData) => {
    const response = await apiClient.post('/llm/test-connection', testData)
    return response.data
  },
  
  // 获取模型列表
  getModels: async (provider, apiKey, baseUrl) => {
    const params = {
      provider,
      api_key: apiKey
    }
    if (baseUrl) {
      params.base_url = baseUrl
    }
    const response = await apiClient.get('/llm/models', { params })
    return response.data
  },

  // 删除配置
  deleteConfig: async (provider) => {
    const response = await apiClient.delete(`/llm/config/${provider}`)
    return response.data
  }
}
