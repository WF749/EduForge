<template>
  <div class="settings-view page-container">
    <div class="settings-content">
      <h1>系统设置</h1>

      <!-- LLM 配置 -->
      <div class="settings-section glass-card">
        <h3>
          <el-icon><Cpu /></el-icon>
          AI 大模型配置
        </h3>
        <p class="section-desc">
          厂商清单、接口地址与默认模型均由后端「厂商注册表」下发（{{ providerCount }} 家），
          模型列表用你自己的 Key 向厂商实时查询 —— 不在前端硬编码任何模型名。
        </p>

        <el-alert
          v-if="loadError"
          type="error"
          :closable="false"
          show-icon
          title="无法连接后端服务"
          :description="loadError"
          class="mb16"
        />

        <!-- 厂商选择 -->
        <div class="provider-cards">
          <div
            v-for="p in providers"
            :key="p.key"
            class="provider-card"
            :class="{ active: currentProvider === p.key }"
            @click="selectProvider(p.key)"
          >
            <div class="provider-head">
              <span class="provider-name">{{ p.label }}</span>
              <el-tag v-if="savedKeys[p.key]" type="success" size="small" round>已配置</el-tag>
              <el-tag v-else type="info" size="small" round>未配置</el-tag>
            </div>
            <div class="provider-default">默认：{{ p.default_model }}</div>
          </div>
        </div>

        <!-- 当前厂商详情 -->
        <div v-if="currentSpec" class="provider-config">
          <div class="spec-head">
            <div class="spec-title">
              <strong>{{ currentSpec.label }}</strong>
              <span class="spec-protocol">{{ currentSpec.protocol === 'anthropic' ? '原生协议' : 'OpenAI 兼容' }}</span>
            </div>
            <div class="spec-caps">
              <el-tag v-for="c in capabilityTags" :key="c" size="small" effect="plain">{{ c }}</el-tag>
            </div>
          </div>

          <p v-if="currentSpec.notes" class="spec-notes">
            <el-icon><InfoFilled /></el-icon>
            {{ currentSpec.notes }}
          </p>

          <el-form label-position="top">
            <!-- API Key -->
            <el-form-item v-if="currentSpec.protocol !== 'local' && currentSpec.protocol !== 'demo'" label="API Key">
              <el-input
                v-model="form.apiKey"
                type="password"
                show-password
                :placeholder="savedKeys[currentProvider] ? `已保存（${keyMasked}），留空则不修改` : 'sk-...'"
                clearable
              >
                <template #append>
                  <el-button :disabled="!currentSpec.docs_url" @click="openUrl(currentSpec.docs_url)">
                    官方文档
                  </el-button>
                </template>
              </el-input>
              <span class="form-hint">
                密钥只保存在本机后端并加密存储，不会回显到页面，也不会写入浏览器缓存。
              </span>
            </el-form-item>

            <!-- 接口地址 -->
            <el-form-item v-if="currentSpec.protocol !== 'demo'" label="接口地址 (Base URL)">
              <el-input v-model="form.baseUrl" :placeholder="currentSpec.base_url || 'http://127.0.0.1:11434/v1'" clearable />
              <span class="form-hint">
                默认由注册表提供；<template v-if="currentSpec.allows_custom_base_url">可改为自建网关或中转地址。</template>
                <el-button link type="primary" size="small" @click="resetBaseUrl">恢复默认</el-button>
              </span>
            </el-form-item>

            <!-- 模型 -->
            <el-form-item v-if="currentSpec.protocol !== 'demo'" label="模型">
              <div class="model-row">
                <el-select
                  v-model="form.model"
                  filterable
                  allow-create
                  default-first-option
                  :reserve-keyword="false"
                  placeholder="输入模型名，或点击右侧拉取"
                  class="model-select"
                >
                  <el-option
                    v-for="m in modelList"
                    :key="m"
                    :label="m"
                    :value="m"
                  />
                </el-select>
                <el-button :loading="loadingModels" @click="fetchModels">
                  <el-icon><Refresh /></el-icon>
                  拉取模型列表
                </el-button>
              </div>
              <span class="form-hint">
                <template v-if="modelSource === 'live'">
                  已实时拉取 {{ modelList.length }} 个模型（厂商权威列表）。
                </template>
                <template v-else-if="modelSource === 'error'">
                  {{ modelError }} —— 可直接手动输入模型名。
                </template>
                <template v-else>
                  支持手动输入任意模型名；建议先填 Key 再点「拉取模型列表」。
                </template>
              </span>
            </el-form-item>

            <el-form-item label="温度 (Temperature)">
              <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.1" show-input />
              <span class="form-hint">越低越确定，越高越有创造性。教案 / 课件生成建议 0.3–0.7。</span>
            </el-form-item>
          </el-form>

          <div class="form-actions">
            <el-button
              :loading="testing"
              :disabled="currentSpec.protocol === 'demo'"
              @click="testConnection"
            >
              <el-icon><Connection /></el-icon>
              测试连接
            </el-button>
            <el-button type="primary" :loading="saving" @click="saveConfig">
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
            <el-button
              type="danger"
              :disabled="!savedKeys[currentProvider]"
              @click="deleteConfig"
            >
              <el-icon><Delete /></el-icon>
              清除密钥
            </el-button>
          </div>

          <!-- 结果反馈 -->
          <el-alert
            v-if="testResult"
            :type="testResult.success ? 'success' : 'error'"
            :closable="true"
            show-icon
            class="mt16"
            @close="testResult = null"
          >
            <template #title>
              {{ testResult.success ? '连接正常' : `连接失败${testResult.code ? '（' + testResult.code + '）' : ''}` }}
            </template>
            <div class="result-body">
              <div>{{ testResult.message }}</div>
              <div v-if="testResult.hint" class="result-hint">建议：{{ testResult.hint }}</div>
              <div v-if="testResult.detail" class="result-detail">厂商返回：{{ testResult.detail }}</div>
            </div>
          </el-alert>
        </div>
      </div>

      <!-- 运行状态（可观测性） -->
      <div class="settings-section glass-card">
        <h3>
          <el-icon><DataLine /></el-icon>
          运行状态
        </h3>
        <p class="section-desc">全链路量化指标：Agent / 模型 / 工具的调用次数、成功率、P95 延迟、Token 与成本。</p>

        <div class="metric-grid">
          <div class="metric-card">
            <span class="metric-label">LLM 调用</span>
            <span class="metric-value">{{ m.llm.count }}</span>
            <span class="metric-sub">成功率 {{ pct(m.llm.success_rate) }} · P95 {{ ms(m.llm.p95_ms) }}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">工具调用</span>
            <span class="metric-value">{{ m.tool.count }}</span>
            <span class="metric-sub">成功率 {{ pct(m.tool.success_rate) }} · P95 {{ ms(m.tool.p95_ms) }}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Agent 任务</span>
            <span class="metric-value">{{ m.agent.count }}</span>
            <span class="metric-sub">成功率 {{ pct(m.agent.success_rate) }} · P95 {{ ms(m.agent.p95_ms) }}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Token / 成本</span>
            <span class="metric-value">{{ m.total_tokens }}</span>
            <span class="metric-sub">约 ¥{{ m.total_cost_cny.toFixed(4) }}</span>
          </div>
        </div>

        <div class="metric-actions">
          <el-button size="small" @click="loadMetrics">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <span class="metric-note">重试 {{ m.retries }} 次 · 累计事件 {{ m.total_events }} 条</span>
        </div>
      </div>

      <!-- 知识库配置 -->
      <div class="settings-section glass-card">
        <h3>
          <el-icon><Collection /></el-icon>
          知识库配置
        </h3>
        <p class="section-desc">检索质量取决于嵌入模型是否匹配语料语言。</p>

        <el-form label-position="top">
          <el-form-item label="嵌入模型">
            <el-select v-model="form.embeddingModel" style="width: 100%">
              <el-option label="bge-small-zh-v1.5（中文，推荐，约 400MB）" value="bge-small-zh-v1.5" />
              <el-option label="text2vec-base-chinese（中文）" value="text2vec-base-chinese" />
              <el-option label="all-MiniLM-L6-v2（英文，不适合中文语料）" value="all-MiniLM-L6-v2" />
            </el-select>
            <span class="form-hint">
              <el-tag v-if="form.embeddingModel === 'all-MiniLM-L6-v2'" type="warning" size="small">
                当前为英文模型，中文检索会失效
              </el-tag>
              <template v-else>中文教学语料请使用中文嵌入模型。</template>
            </span>
          </el-form-item>

          <div class="two-col">
            <el-form-item label="文本块大小">
              <el-input-number v-model="form.chunkSize" :min="100" :max="1000" :step="50" />
              <span class="form-hint-inline">单块字符数</span>
            </el-form-item>
            <el-form-item label="检索返回数量">
              <el-input-number v-model="form.topK" :min="1" :max="20" />
              <span class="form-hint-inline">返回相关片段数</span>
            </el-form-item>
          </div>
        </el-form>
      </div>

      <!-- 关于 -->
      <div class="settings-section glass-card">
        <h3>
          <el-icon><InfoFilled /></el-icon>
          关于项目
        </h3>

        <div class="about-info">
          <div class="about-row">
            <span class="about-label">项目名称</span>
            <span class="about-value">EduForge · 教铸</span>
          </div>
          <div class="about-row">
            <span class="about-label">定位</span>
            <span class="about-value">面向真实备课场景的多模态 Agent 工作台</span>
          </div>
          <div class="about-row">
            <span class="about-label">开源协议</span>
            <span class="about-value">Apache-2.0</span>
          </div>
          <div class="about-row">
            <span class="about-label">版本</span>
            <span class="about-value">v2.0.0</span>
          </div>
        </div>

        <div class="opensource-section">
          <h4><el-icon><Link /></el-icon> 开源组件引用声明</h4>
          <p class="opensource-desc">本项目基于以下开源组件构建，遵循其对应的开源协议：</p>
          <div class="opensource-grid">
            <div v-for="lib in openSourceLibs" :key="lib.name" class="opensource-item">
              <div class="lib-header">
                <span class="lib-name">{{ lib.name }}</span>
                <el-tag size="small" :type="lib.licenseType">{{ lib.license }}</el-tag>
              </div>
              <span class="lib-usage">{{ lib.usage }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { installDataFlowInterceptor } from '@/api/dataFlow'
import {
  Cpu, Connection, Check, Delete, InfoFilled, Link, Refresh, DataLine, Collection
} from '@element-plus/icons-vue'

const api = axios.create({ baseURL: resolveApiBaseURL(), timeout: 60000 })

installDataFlowInterceptor(api)

const providers = ref([])
const currentProvider = ref('dashscope')
const savedKeys = reactive({})      // { provider: masked }
const savedModels = reactive({})
const loadError = ref('')

const form = reactive({
  apiKey: '',
  baseUrl: '',
  model: '',
  temperature: 0.7,
  embeddingModel: 'bge-small-zh-v1.5',
  chunkSize: 500,
  topK: 5
})

// 后端已保存的 base_url / 模型（按厂商维度）；密钥只存掩码
const savedBaseUrls = reactive({})

const modelList = ref([])
const modelSource = ref('')          // '' | 'live' | 'error'
const modelError = ref('')
const loadingModels = ref(false)
const testing = ref(false)
const saving = ref(false)
const testResult = ref(null)

const m = reactive({
  llm: { count: 0, success_rate: 0, p95_ms: 0 },
  tool: { count: 0, success_rate: 0, p95_ms: 0 },
  agent: { count: 0, success_rate: 0, p95_ms: 0 },
  request: { count: 0, success_rate: 0, p95_ms: 0 },
  total_tokens: 0,
  total_cost_cny: 0,
  retries: 0,
  total_events: 0
})

const providerCount = computed(() => providers.value.length)
const currentSpec = computed(() => providers.value.find(p => p.key === currentProvider.value) || null)
const keyMasked = computed(() => savedKeys[currentProvider.value] || '')

const capabilityTags = computed(() => {
  const c = currentSpec.value?.capabilities || {}
  const map = { vision: '视觉理解', tools: '工具调用', json_mode: 'JSON 输出', stream: '流式', embedding: '向量' }
  return Object.keys(map).filter(k => c[k]).map(k => map[k])
})

/** 统一的错误信息提取：后端返回结构化 {code,message,hint,detail} */
function extractError(e, fallback) {
  const d = e?.response?.data
  if (d && typeof d === 'object') {
    return {
      success: false,
      code: d.code || '',
      message: d.message || d.detail || fallback,
      hint: d.hint || '',
      detail: d.detail || ''
    }
  }
  return { success: false, code: '', message: e?.message || fallback, hint: '', detail: '' }
}

async function loadProviders() {
  const res = await api.get('/providers')
  providers.value = res.data.providers || []
}

async function loadSavedConfig() {
  const res = await api.get('/llm/config')
  const list = res.data.providers || []
  for (const p of list) {
    if (p.key_masked) savedKeys[p.provider] = p.key_masked
    else delete savedKeys[p.provider]
    if (p.model) savedModels[p.provider] = p.model
    if (p.base_url) savedBaseUrls[p.provider] = p.base_url
  }
  if (res.data.provider) currentProvider.value = res.data.provider
  if (typeof res.data.temperature === 'number') form.temperature = res.data.temperature
  syncFormToProvider()
}

/** 切换厂商时，把表单切到该厂商的已保存值（不回显明文密钥） */
function syncFormToProvider() {
  const p = currentProvider.value
  form.apiKey = ''
  const spec = currentSpec.value
  form.baseUrl = savedBaseUrls[p] || spec?.base_url || ''
  form.model = savedModels[p] || spec?.default_model || ''
  modelList.value = []
  modelSource.value = ''
  modelError.value = ''
  testResult.value = null
}

function selectProvider(id) {
  if (id === currentProvider.value) return
  currentProvider.value = id
  syncFormToProvider()
}

function resetBaseUrl() {
  form.baseUrl = currentSpec.value?.base_url || ''
}

async function fetchModels() {
  const spec = currentSpec.value
  if (!spec || spec.protocol === 'demo') return
  loadingModels.value = true
  modelError.value = ''
  try {
    const params = { provider: currentProvider.value }
    // 输入框里临时填的 Key 优先，用于"还没保存就想看有哪些模型"
    if (form.apiKey && form.apiKey.trim()) params.api_key = form.apiKey.trim()
    const res = await api.get('/models/live', { params })
    const d = res.data
    if (d.success) {
      modelList.value = (d.models || []).map(x => x.name || x).filter(Boolean)
      modelSource.value = 'live'
      if (!form.model && modelList.value.length) form.model = modelList.value[0]
      ElMessage.success(`已拉取 ${modelList.value.length} 个模型`)
    } else {
      modelSource.value = 'error'
      modelError.value = d.message || d.reason || '拉取失败'
    }
  } catch (e) {
    modelSource.value = 'error'
    modelError.value = extractError(e, '拉取模型列表失败').message
  } finally {
    loadingModels.value = false
  }
}

async function testConnection() {
  const spec = currentSpec.value
  if (!spec) return
  testing.value = true
  testResult.value = null
  try {
    const payload = {
      provider: currentProvider.value,
      // 留空则后端自动使用已保存的 Key
      api_key: form.apiKey ? form.apiKey.trim() : '',
      model: form.model || '',
      base_url: form.baseUrl || ''
    }
    const res = await api.post('/llm/test-connection', payload)
    const d = res.data
    testResult.value = {
      success: !!d.success,
      code: d.code || '',
      message: d.message || '',
      hint: d.hint || '',
      detail: d.detail || ''
    }
  } catch (e) {
    testResult.value = extractError(e, '连接测试失败')
  } finally {
    testing.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const payload = {
      provider: currentProvider.value,
      apiKeys: { [currentProvider.value]: form.apiKey ? form.apiKey.trim() : '' },
      models: { [currentProvider.value]: form.model || '' },
      temperature: form.temperature,
      embeddingModel: form.embeddingModel,
      chunkSize: form.chunkSize,
      topK: form.topK
    }
    // 自定义 base_url 单独存，避免污染其他厂商
    if (currentSpec.value?.protocol !== 'demo') {
      const keyName = currentProvider.value === 'local' ? 'localUrl' : `${currentProvider.value}Base`
      payload.apiKeys[keyName] = form.baseUrl || ''
    }

    const res = await api.post('/llm/save-full-config', payload)
    if (!res.data?.success) {
      throw new Error(res.data?.message || '保存失败')
    }
    // 保存成功后立即回读，拿到掩码与生效状态
    await loadSavedConfig()
    form.apiKey = ''
    ElMessage.success(
      res.data.has_api_key
        ? `已保存 · 当前模型 ${res.data.model || form.model}`
        : '已保存（该厂商尚未配置密钥）'
    )
  } catch (e) {
    const err = extractError(e, '保存失败')
    ElMessage.error(`${err.message}${err.hint ? ' · ' + err.hint : ''}`)
  } finally {
    saving.value = false
  }
}

async function deleteConfig() {
  try {
    await ElMessageBox.confirm(
      `将清除 ${currentSpec.value?.label} 已保存的 API Key，此操作不可撤销。`,
      '确认清除',
      { type: 'warning', confirmButtonText: '清除', cancelButtonText: '取消' }
    )
    await api.post('/llm/save-full-config', {
      provider: currentProvider.value,
      apiKeys: { [currentProvider.value]: null },  // null = 显式删除
      models: { [currentProvider.value]: form.model || '' }
    })
    form.apiKey = ''
    await loadSavedConfig()
    ElMessage.success('密钥已清除')
  } catch (e) {
    if (e !== 'cancel' && e !== 'Cancel') {
      ElMessage.error(extractError(e, '清除失败').message)
    }
  }
}

async function loadMetrics() {
  try {
    const res = await api.get('/metrics')
    const s = res.data?.summary || {}
    const empty = { count: 0, success_rate: 0, p95_ms: 0, avg_ms: 0 }
    // 后端 summary 的分组字段直接是 llm / tool / agent / request
    for (const k of ['llm', 'tool', 'agent', 'request']) {
      m[k] = { ...empty, ...(s[k] || {}) }
    }
    m.total_tokens = s.total_tokens || 0
    m.total_cost_cny = s.total_cost_cny || 0
    m.retries = s.retries || 0
    m.total_events = s.total_events || 0
  } catch {
    /* 指标面板失败不应影响设置页主流程 */
  }
}

const pct = v => `${((v ?? 0) * 100).toFixed(0)}%`
const ms = v => `${Math.round(v ?? 0)}ms`

function openUrl(url) {
  if (url) window.open(url, '_blank')
}

const openSourceLibs = [
  { name: 'Vue 3', license: 'MIT', licenseType: 'success', usage: '前端框架' },
  { name: 'FastAPI', license: 'MIT', licenseType: 'success', usage: '后端 API 框架' },
  { name: 'Element Plus', license: 'MIT', licenseType: 'success', usage: 'UI 组件库' },
  { name: 'Pinia', license: 'MIT', licenseType: 'success', usage: '状态管理' },
  { name: 'Vite', license: 'MIT', licenseType: 'success', usage: '构建工具' },
  { name: 'ChromaDB', license: 'Apache-2.0', licenseType: 'warning', usage: '向量数据库' },
  { name: 'sentence-transformers', license: 'Apache-2.0', licenseType: 'warning', usage: '文本向量化' },
  { name: 'python-docx', license: 'MIT', licenseType: 'success', usage: 'Word 生成' },
  { name: 'python-pptx', license: 'MIT', licenseType: 'success', usage: 'PPT 生成' },
  { name: 'pdfplumber', license: 'MIT', licenseType: 'success', usage: 'PDF 解析' },
  { name: 'Three.js', license: 'MIT', licenseType: 'success', usage: '3D 可视化' },
  { name: 'httpx', license: 'BSD-3', licenseType: 'success', usage: 'HTTP 客户端' }
]

onMounted(async () => {
  try {
    await loadProviders()
    await loadSavedConfig()
  } catch (e) {
    loadError.value = extractError(e, '请确认后端已启动').message
  }
  loadMetrics()
})
</script>

<style lang="scss" scoped>
.settings-view {
  padding: 24px;
  overflow-y: auto;
  height: calc(100vh - 112px);
  background: var(--bg-dark);
}

.settings-content {
  max-width: 960px;
  margin: 0 auto;

  h1 {
    font-size: 28px;
    margin-bottom: 32px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }
}

.settings-section {
  padding: 24px;
  margin-bottom: 24px;
  background: rgba(26, 31, 78, 0.95);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 16px;

  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 18px;
    margin-bottom: 8px;
    color: #fff;
  }

  .section-desc {
    font-size: 14px;
    color: #b0b8c4;
    margin-bottom: 20px;
  }

  :deep(.el-form-item__label) {
    color: #c8d0dc;
    font-weight: 500;
  }

  :deep(.el-input__wrapper) {
    background: rgba(10, 14, 39, 0.9) !important;
  }

  :deep(.el-input__inner) {
    color: #fff !important;
  }
}

.mb16 { margin-bottom: 16px; }
.mt16 { margin-top: 16px; }

/* 厂商卡片 */
.provider-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.provider-card {
  padding: 14px;
  background: rgba(10, 14, 39, 0.5);
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.25s ease;

  &:hover { background: rgba(0, 200, 255, 0.1); border-color: rgba(0, 200, 255, 0.35); }

  &.active {
    background: rgba(0, 200, 255, 0.15);
    border-color: var(--primary);
    box-shadow: 0 0 18px rgba(0, 200, 255, 0.2);
  }

  .provider-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
  }

  .provider-name { font-size: 14px; font-weight: 600; }
  .provider-default { font-size: 11px; color: var(--text-muted); }
}

/* 当前厂商详情 */
.provider-config {
  padding: 20px;
  background: rgba(10, 14, 39, 0.3);
  border-radius: 12px;
}

.spec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 8px;
}

.spec-protocol {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.spec-caps { display: flex; gap: 6px; flex-wrap: wrap; }

.spec-notes {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #ffd591;
  background: rgba(250, 173, 20, 0.08);
  border-left: 3px solid #faad14;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 16px;
}

.model-row { display: flex; gap: 8px; width: 100%; }
.model-select { flex: 1; }

.form-hint {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.form-hint-inline { margin-left: 12px; font-size: 12px; color: var(--text-muted); }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}

.result-body { font-size: 13px; line-height: 1.7; }
.result-hint { color: var(--primary); }
.result-detail { color: var(--text-muted); }

/* 指标面板 */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px;
  background: rgba(10, 14, 39, 0.5);
  border-radius: 10px;

  .metric-label { font-size: 12px; color: var(--text-muted); }
  .metric-value { font-size: 22px; font-weight: 700; color: var(--primary); }
  .metric-sub { font-size: 11px; color: var(--text-secondary); }
}

.metric-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.metric-note { font-size: 12px; color: var(--text-muted); }

/* 关于 */
.about-info { margin-bottom: 24px; }

.about-row {
  display: flex;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);

  &:last-child { border-bottom: none; }
  .about-label { width: 100px; color: var(--text-secondary); }
  .about-value { flex: 1; }
}

.opensource-section {
  h4 { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-secondary); margin-bottom: 8px; }
  .opensource-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 16px; }
}

.opensource-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }

.opensource-item {
  padding: 12px;
  background: rgba(10, 14, 39, 0.5);
  border-radius: 8px;

  .lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .lib-name { font-size: 13px; font-weight: 600; }
  .lib-usage { font-size: 11px; color: var(--text-muted); }
}

@media (max-width: 900px) {
  .provider-cards { grid-template-columns: repeat(2, 1fr); }
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .opensource-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
</style>
