import { defineStore } from 'pinia'
import { llmApi } from '../api/llm'

export const useLLMStore = defineStore('llm', {
  state: () => ({
    configs: [],
    loading: false,
    error: null
  }),
  
  getters: {
    // 获取当前激活的配置
    getActiveConfig: (state) => {
      return state.configs.find(config => config.is_active) || null
    },
    
    // 根据提供商获取配置
    getConfigByProvider: (state) => (provider) => {
      return state.configs.find(config => config.provider === provider) || null
    }
  },
  
  actions: {
    // 加载配置
    async loadConfig() {
      this.loading = true
      this.error = null
      try {
        const response = await llmApi.getConfig()
        this.configs = response.providers
      } catch (error) {
        this.error = '加载配置失败'
        console.error(error)
      } finally {
        this.loading = false
      }
    },
    
    // 保存配置
    async saveConfig(configData) {
      this.loading = true
      this.error = null
      try {
        const response = await llmApi.saveConfig(configData)
        if (response.success) {
          // 重新加载配置
          await this.loadConfig()
        }
        return response
      } catch (error) {
        this.error = '保存配置失败'
        console.error(error)
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})
