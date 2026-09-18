<template>
  <div class="ai-model-setting">
    <el-card class="setting-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>AI大模型配置</span>
        </div>
      </template>
      
      <div class="provider-cards">
        <el-card
          v-for="provider in providers"
          :key="provider.value"
          class="provider-card"
          :class="{ active: activeProvider === provider.value }"
          @click="selectProvider(provider.value)"
        >
          <div class="provider-info">
            <el-icon class="provider-icon"><component :is="provider.icon" /></el-icon>
            <h3>{{ provider.label }}</h3>
            <p>{{ provider.description }}</p>
          </div>
        </el-card>
      </div>
      
      <div class="config-form">
        <el-form :model="form" :rules="rules" ref="formRef">
          <!-- API Key -->
          <el-form-item label="API Key" prop="apiKey">
            <el-input
              v-model="form.apiKey"
              :type="showApiKey ? 'text' : 'password'"
              :placeholder="apiKeyMasked ? `已保存：${apiKeyMasked}（重新输入可覆盖）` : '请输入API Key'"
            >
              <template #append>
                <el-button @click="showApiKey = !showApiKey">
                  <el-icon v-if="showApiKey"><View /></el-icon>
                  <el-icon v-else><Hide /></el-icon>
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 模型选择 -->
          <el-form-item label="模型选择" prop="model">
            <el-select
              v-model="form.model"
              placeholder="请选择模型"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="model in models"
                :key="model.name"
                :value="model.name"
              >
                <div class="model-option">
                  <div class="model-name">{{ model.name }}</div>
                  <div class="model-desc">{{ model.description }}</div>
                  <div class="model-price" v-if="model.price_info">
                    <el-tag size="small" type="info">价格</el-tag>
                    {{ model.price_info }}
                  </div>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          
          <!-- 温度参数 -->
          <el-form-item label="温度参数" prop="temperature">
            <div class="temperature-control">
              <el-slider
                v-model="form.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                show-input
                :input-size="'small'"
              />
            </div>
          </el-form-item>
          
          <!-- 基础URL (仅OpenAI和DeepSeek) -->
          <el-form-item v-if="activeProvider === 'openai' || activeProvider === 'deepseek' || activeProvider === 'local'" label="基础URL">
            <el-input
              v-model="form.baseUrl"
              placeholder="请输入基础URL"
            />
          </el-form-item>
          
          <!-- 操作按钮 -->
          <div class="form-actions">
            <el-button
              type="primary"
              @click="testConnection"
              :loading="testingConnection"
            >
              测试连接
            </el-button>
            <el-button
              type="success"
              @click="saveConfig"
              :loading="savingConfig"
            >
              保存配置
            </el-button>
          </div>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { View, Hide, Server, Globe, Cpu, Code, InfoFilled } from '@element-plus/icons-vue'
import { useLLMStore } from '../store/llm'
import { llmApi } from '../api/llm'

// 状态管理
const llmStore = useLLMStore()

// 响应式数据
const activeProvider = ref('demo')
const showApiKey = ref(false)
const testingConnection = ref(false)
const savingConfig = ref(false)
const formRef = ref(null)

// 表单数据
const form = reactive({
  apiKey: '',
  model: '',
  temperature: 0.7,
  baseUrl: ''
})

// 已保存的Key掩码（仅展示用，不会回传后端）
const apiKeyMasked = ref('')

// 表单验证规则
const rules = {
  apiKey: [
    {
      required: activeProvider.value !== 'demo' && activeProvider.value !== 'local',
      message: '请输入API Key',
      trigger: 'blur'
    }
  ],
  model: [
    {
      required: true,
      message: '请选择模型',
      trigger: 'change'
    }
  ]
}

// 模型列表
const models = ref([])

// 提供商配置
const providers = [
  {
    value: 'dashscope',
    label: '阿里云百炼（通义千问）',
    description: '国内领先的大语言模型服务',
    icon: Server
  },
  {
    value: 'openai',
    label: 'OpenAI',
    description: 'GPT系列模型服务',
    icon: Globe
  },
  {
    value: 'deepseek',
    label: 'DeepSeek',
    description: '专注于代码和数学的大模型',
    icon: Code
  },
  {
    value: 'local',
    label: '本地模型',
    description: '基于Ollama的本地模型',
    icon: Cpu
  },
  {
    value: 'demo',
    label: '演示模式',
    description: '无需API Key，用于演示',
    icon: InfoFilled
  }
]

// 选择提供商
const selectProvider = (provider) => {
  activeProvider.value = provider
  // 加载对应提供商的配置
  loadProviderConfig(provider)
}

// 加载提供商配置
const loadProviderConfig = async (provider) => {
  try {
    const config = llmStore.getConfigByProvider(provider)
    if (config) {
      apiKeyMasked.value = config.api_key_masked || config.api_key || ''
      // 安全：后端返回的是掩码，不能回填到输入框；需要用户重新输入才覆盖
      form.apiKey = ''
      form.model = config.model || ''
      form.temperature = config.temperature || 0.7
      form.baseUrl = config.base_url || ''
      
      // 如果有API Key，加载模型列表
      if (provider !== 'demo') {
        // 允许不传 apiKey：后端会从已保存配置中读取
        await loadModels(provider, '', form.baseUrl)
      }
    } else {
      // 重置表单
      form.apiKey = ''
      form.model = ''
      form.temperature = 0.7
      form.baseUrl = ''
      models.value = []
      apiKeyMasked.value = ''
    }
  } catch (error) {
    ElMessage.error('加载配置失败')
    console.error(error)
  }
}

// 加载模型列表
const loadModels = async (provider, apiKey, baseUrl) => {
  try {
    const response = await llmApi.getModels(provider, apiKey, baseUrl)
    if (response.success) {
      models.value = response.models
    }
  } catch (error) {
    console.error('加载模型列表失败', error)
  }
}

// 测试连接
const testConnection = async () => {
  if (activeProvider.value === 'demo') {
    ElMessage.success('演示模式无需测试连接')
    return
  }

  if (activeProvider.value !== 'local' && !form.apiKey) {
    ElMessage.warning('请先输入API Key（已保存的Key不会回显，重新输入可覆盖）')
    return
  }
  
  testingConnection.value = true
  try {
    const response = await llmApi.testConnection({
      provider: activeProvider.value,
      api_key: form.apiKey,
      base_url: form.baseUrl
    })
    
    if (response.success) {
      ElMessage.success(response.message)
      // 测试成功后加载模型列表
      await loadModels(activeProvider.value, form.apiKey, form.baseUrl)
    } else {
      ElMessage.error(response.message)
    }
  } catch (error) {
    ElMessage.error('测试连接失败')
    console.error(error)
  } finally {
    testingConnection.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  // 表单验证
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      savingConfig.value = true
      try {
        const response = await llmApi.saveConfig({
          provider: activeProvider.value,
          api_key: form.apiKey,
          model: form.model,
          temperature: form.temperature,
          base_url: form.baseUrl,
          is_active: true
        })
        
        if (response.success) {
          ElMessage.success('配置保存成功')
          // 重新加载配置
          await llmStore.loadConfig()
          // 重新加载当前提供商配置（更新掩码显示等）
          await loadProviderConfig(activeProvider.value)
        } else {
          ElMessage.error('配置保存失败')
        }
      } catch (error) {
        ElMessage.error('配置保存失败')
        console.error(error)
      } finally {
        savingConfig.value = false
      }
    }
  })
}

// 初始化
onMounted(async () => {
  // 加载配置
  await llmStore.loadConfig()
  
  // 设置默认激活的提供商
  const activeConfig = llmStore.getActiveConfig()
  if (activeConfig) {
    activeProvider.value = activeConfig.provider
  }
  
  // 加载对应提供商的配置
  await loadProviderConfig(activeProvider.value)
})
</script>

<style scoped>
.ai-model-setting {
  padding: 20px;
}

.setting-card {
  max-width: 800px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.provider-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 30px;
}

.provider-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.provider-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.provider-card.active {
  border-color: #409eff;
  background-color: rgba(64, 158, 255, 0.05);
}

.provider-info {
  text-align: center;
  padding: 20px;
}

.provider-icon {
  font-size: 48px;
  margin-bottom: 16px;
  color: #409eff;
}

.provider-info h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.provider-info p {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.config-form {
  margin-top: 30px;
}

.temperature-control {
  width: 100%;
}

.form-actions {
  margin-top: 30px;
  display: flex;
  gap: 16px;
}

.model-option {
  padding: 4px 0;
}

.model-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.model-desc {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
  line-height: 1.4;
}

.model-price {
  font-size: 11px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .provider-cards {
    grid-template-columns: 1fr;
  }
  
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions .el-button {
    width: 100%;
  }
}
</style>
