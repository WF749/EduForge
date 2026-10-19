<template>
  <div class="wb-page">
    <PageHeader
      title="设置"
      description="模型服务、检索参数与界面外观。改完点保存，不需要重启服务。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">重新载入</el-button>
      </template>
    </PageHeader>

    <div class="layout">
      <!-- 模型服务 -->
      <section class="wb-card wb-card-pad">
        <div class="wb-section-title">模型服务</div>
        <p class="wb-card-hint">
          密钥只回显掩码，不会从后端明文返回。输入框<b>留空表示不修改</b> ——
          所以只改模型不会把已配好的 Key 清掉。
        </p>

        <StateBlock
            :loading="loading"
            hint="正在读取模型配置…"
            :error="error"
            :rows="6"
            @retry="loadAll"
          >
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="当前厂商">
              <el-select v-model="form.provider" style="width: 240px" @change="onProviderChange">
                <el-option v-for="p in providers" :key="p.key" :label="p.label" :value="p.key">
                  <span>{{ p.label }}</span>
                  <span class="wb-muted" style="float: right; font-size: 11px">{{ p.protocol }}</span>
                </el-option>
              </el-select>
              <p v-if="activeSpec?.notes" class="wb-muted hint-line">{{ activeSpec.notes }}</p>
            </el-form-item>

            <el-form-item label="模型">
              <div class="wb-row" style="gap: var(--sp-2)">
                <el-select
                  v-model="form.model"
                  filterable
                  allow-create
                  placeholder="留空用厂商默认模型"
                  style="width: 280px"
                >
                  <el-option v-for="m in models" :key="m.name" :label="m.name" :value="m.name" />
                </el-select>
                <el-button :loading="loadingModels" @click="loadModels">拉取实时列表</el-button>
              </div>
              <p class="wb-muted hint-line">
                模型名以厂商实时返回为准；本项目不维护硬编码清单，避免出现"实际存在却判成不存在"。
              </p>
            </el-form-item>

            <el-form-item label="API Key">
              <el-input
                v-model="form.apiKey"
                type="password"
                show-password
                autocomplete="off"
                placeholder="留空表示不修改"
                style="max-width: 420px"
              />
              <p v-if="keyMasked" class="wb-muted hint-line">已保存：{{ keyMasked }}</p>
            </el-form-item>

            <el-form-item v-if="activeSpec?.allows_custom_base_url" label="接口地址">
              <el-input v-model="form.baseUrl" placeholder="留空用默认地址" style="max-width: 420px" />
            </el-form-item>

          </el-form>

          <!--
            开发者选项：默认折叠。
            普通教师不需要知道 temperature —— 系统按任务与阶段自动选择，
            这里只留给调试/评估用。刻意**不**把它改叫"创造力""教学质量"之类，
            那会让教师以为调它就能调内容质量。
          -->
          <el-collapse v-model="openDev" class="dev">
            <el-collapse-item name="dev" title="开发者选项（调参与调试）">
              <el-form label-position="top" @submit.prevent>
                <el-form-item>
                  <template #label>
                    采样模式
                    <el-tooltip content="自动：按任务用途与执行阶段选择；手动：固定用下面填写的值" placement="top">
                      <el-icon class="wb-muted"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                  <el-radio-group v-model="form.samplingMode">
                    <el-radio value="auto">自动（推荐）</el-radio>
                    <el-radio value="manual">手动</el-radio>
                  </el-radio-group>
                  <p class="wb-muted hint-line">
                    自动模式下，教案正文、知识问答、代码生成等不同用途会用不同的值；
                    下面填写的手动值在自动模式下<b>不生效</b>。
                  </p>
                </el-form-item>

                <el-form-item v-if="form.samplingMode === 'manual'">
                  <template #label>
                    温度
                    <el-tooltip content="采样温度：越低越确定、越高越发散。仅手动模式下发送" placement="top">
                      <el-icon class="wb-muted"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                  <el-input-number
                    v-model="form.temperature"
                    :min="samplingRange.min"
                    :max="samplingRange.max"
                    :step="0.1"
                    :precision="2"
                    :disabled="!samplingRange.supports"
                  />
                  <p class="wb-muted hint-line">
                    当前值 {{ form.temperature }}；可填范围 {{ samplingRange.min }} – {{ samplingRange.max }}
                    （随所选厂商/模型而定）。
                  </p>
                  <div class="wb-row wb-row--tight">
                    <StatusTag
                      :status="capabilityTag.status"
                      :label="capabilityTag.label"
                    />
                  </div>
                  <!-- 四种状态都要说清楚：支持 / 禁止 / 未知 / 兼容模式 -->
                  <p v-if="capabilityTag.key === 'supported'" class="hint-line hint-line--ok">
                    该模型已验证支持该参数，手动值会照常发送。
                  </p>
                  <p v-else-if="capabilityTag.key === 'unsupported'" class="hint-line hint-line--warn">
                    该模型不接受该参数，手动值<b>不会被发送</b>。
                  </p>
                  <p v-else class="hint-line hint-line--warn">
                    该模型不在已验证清单内，能力未知：仍会按兼容模式发送，
                    但<b>无法确认参数是否生效</b>。可在下面手动指定。
                  </p>
                </el-form-item>

                <el-form-item>
                  <template #label>
                    该模型的温度能力
                    <el-tooltip content="本地模型（Ollama/vLLM）和自建网关的模型名查不到内置清单，可在这里手动钉死" placement="top">
                      <el-icon class="wb-muted"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                  <el-radio-group v-model="form.temperatureOverride">
                    <el-radio value="auto">自动判断（推荐）</el-radio>
                    <el-radio value="supported">支持 temperature</el-radio>
                    <el-radio value="unsupported">不支持 temperature</el-radio>
                  </el-radio-group>
                  <p class="wb-muted hint-line">
                    内置清单只收录本项目实际演示过的模型；
                    <b>本地 / 自建 / 演示</b>模式下模型名是自定义的，清单必然查不到 ——
                    如果你确认过它收不收这个参数，在这里钉死即可，免得一直停在「能力未知」。
                  </p>
                  <p v-if="form.temperatureOverride !== 'auto'" class="hint-line hint-line--warn">
                    已手动指定为「{{ form.temperatureOverride === 'supported' ? '支持' : '不支持' }}」，
                    该结论会覆盖自动判断。
                  </p>
                </el-form-item>
              </el-form>
            </el-collapse-item>
          </el-collapse>

          <div class="wb-row">
            <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
            <el-button :loading="testing" @click="onTest">测试连接</el-button>
            <el-button v-if="hasKey" type="danger" plain @click="onDeleteKey">
              删除该厂商的 Key
            </el-button>
          </div>

          <p v-if="testResult" class="note" :class="testResult.success ? 'note--ok' : 'note--warn'">
            {{ testResult.message }}
            <span v-if="testResult.hint"><br>{{ testResult.hint }}</span>
          </p>
        </StateBlock>
      </section>

      <!-- 检索与上传 -->
      <section class="wb-card wb-card-pad">
        <div class="wb-section-title">检索与上传</div>
        <p class="wb-card-hint">影响知识库切分与检索返回的条数，改完即时生效。</p>

        <el-form label-position="top" @submit.prevent>
          <div class="wb-row" style="gap: var(--sp-3)">
            <el-form-item label="切分大小（字）" class="wb-grow">
              <el-input-number v-model="kn.chunkSize" :min="100" :max="1000" :step="50" />
            </el-form-item>
            <el-form-item label="返回条数" class="wb-grow">
              <el-input-number v-model="kn.topK" :min="1" :max="20" />
            </el-form-item>
          </div>
          <el-form-item label="Embedding 模型">
            <el-input v-model="kn.embeddingModel" placeholder="留空用默认" style="max-width: 420px" />
          </el-form-item>
          <div class="wb-row">
            <el-button :loading="savingKn" @click="onSaveKnowledge">保存检索设置</el-button>
          </div>
        </el-form>

        <el-divider />

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="单文件上限（MB）" class="wb-grow">
            <el-input-number v-model="fileCfg.maxFileSizeMb" :min="1" :max="200" />
          </el-form-item>
          <el-form-item label="允许的类型">
            <el-input v-model="fileCfg.allowedTypes" placeholder="pdf,docx,txt" style="max-width: 420px" />
          </el-form-item>
          <div class="wb-row">
            <el-button :loading="savingFile" @click="onSaveFile">保存上传设置</el-button>
          </div>
        </el-form>
      </section>

      <!-- 外观 -->
      <section class="wb-card wb-card-pad">
        <div class="wb-section-title">外观</div>
        <p class="wb-card-hint">跟随系统会随电脑的深浅色设置自动切换，不用手动改。</p>

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="主题">
            <el-radio-group :model-value="theme.mode" @change="onTheme">
              <el-radio value="light">浅色</el-radio>
              <el-radio value="dark">深色</el-radio>
              <el-radio value="system">跟随系统</el-radio>
            </el-radio-group>
            <p class="wb-muted hint-line">
              当前生效：{{ theme.isDark ? '深色' : '浅色' }}
              <span v-if="theme.mode === 'system'">（系统现在是{{ theme.systemDark ? '深色' : '浅色' }}）</span>
            </p>
          </el-form-item>
        </el-form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { QuestionFilled, Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { llmApi } from '@/api/llm'
import { fetchProviders } from '@/api/system'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'
import { useThemeStore } from '@/store/theme'
import { useAppStore } from '@/store/app'
import { confirmDanger, notifyError, notifySuccess, notifyWarn } from '@/utils/notify'

/**
 * 设置页。
 *
 * 最关键的一条语义：**留空 = 不修改**。
 * 后端不回显明文密钥，所以加载时输入框必然是空的；若整体覆盖 apiKeys，
 * 教师只改个模型再点保存，就会把所有 Key 清空 —— 那个故障的表现是
 * 「保存成功、对话立刻失效」，很难联想回来。
 */
const theme = useThemeStore()
const appStore = useAppStore()

const loading = ref(false)
const error = ref('')
const saving = ref(false)
const testing = ref(false)
const loadingModels = ref(false)
const providers = ref([])
const models = ref([])

const form = reactive({ provider: 'demo', model: '', apiKey: '', baseUrl: '', temperature: 0.7, samplingMode: 'auto', temperatureOverride: 'auto' })
const keyMasked = ref('')
const cfgSampling = ref(null)
const hasKey = ref(false)
const testResult = ref(null)

const kn = reactive({ chunkSize: 500, topK: 5, embeddingModel: '' })
const openDev = ref([])

/**
 * 手动输入的可编辑范围随厂商/模型而定，不统一假设所有模型一样。
 *
 * 能力分三态，界面必须如实呈现：
 *   supported  → 正常可编辑；
 *   unsupported→ 禁用并说明"不接受该参数，不会发送"；
 *   unknown    → 仍可编辑（兼容模式照常发送），但标记"能力未知"，
 *                绝不把"没验证过"显示成"已确认支持"。
 */
const samplingRange = computed(() => {
  const s = cfgSampling.value || {}
  // 本地改了覆盖值要**立刻**反映在界面上，不能等保存刷新后才对 ——
  // 否则教师选了「不支持」却仍看到"已验证支持"，比不显示更糟。
  const state = form.temperatureOverride !== 'auto'
    ? form.temperatureOverride
    : (s.state || 'unknown')
  return {
    state,
    supports: form.temperatureOverride === 'unsupported'
      ? false
      : s.supports_temperature !== false,
    unknown: state === 'unknown',
    min: Number.isFinite(s.min) ? s.min : 0,
    max: Number.isFinite(s.max) ? s.max : 2,
  }
})

/** 四种可呈现的结论：支持 / 禁止 / 未知 / 手动指定 */
const capabilityTag = computed(() => {
  const overridden = form.temperatureOverride !== 'auto'
  const base = {
    supported: { status: 'done', label: '已验证支持' },
    unsupported: { status: 'risk', label: '不接受该参数' },
    unknown: { status: 'warn', label: '能力未知 · 兼容模式' },
  }[samplingRange.value.state] || { status: 'warn', label: '能力未知 · 兼容模式' }
  return {
    ...base,
    key: samplingRange.value.state,
    label: overridden ? `${base.label}（手动指定）` : base.label,
  }
})

const savingKn = ref(false)
const fileCfg = reactive({ maxFileSizeMb: 20, allowedTypes: 'pdf,docx,doc,txt,md,pptx' })
const savingFile = ref(false)

const activeSpec = computed(() => providers.value.find(p => p.key === form.provider) || null)

async function loadProviders() {
  try {
    const d = await fetchProviders()
    providers.value = Array.isArray(d.providers) ? d.providers : []
  } catch { providers.value = [] }
}

async function loadConfig() {
  const cfg = await llmApi.getConfig()
  const list = Array.isArray(cfg.providers) ? cfg.providers : []
  form.provider = cfg.provider || 'demo'
  // 旧配置没有 samplingMode → 后端已按 auto 下发；这里保持一致，
  // 绝不能因为"有 temperature 数值"就推断成手动模式。
  form.samplingMode = cfg.samplingMode === 'manual' ? 'manual' : 'auto'
  const ov = String(cfg.temperatureOverride || 'auto').toLowerCase()
  form.temperatureOverride = ['supported', 'unsupported'].includes(ov) ? ov : 'auto'
  form.temperature = Number(cfg.temperature ?? 0.7)
  kn.chunkSize = Number(cfg.chunkSize ?? 500)
  kn.topK = Number(cfg.topK ?? 5)

  const active = list.find(p => p.provider === form.provider)
  keyMasked.value = active?.key_masked || ''
  hasKey.value = !!active?.has_api_key
  form.model = active?.model || ''
  cfgSampling.value = cfg.sampling || null
  form.baseUrl = active?.base_url || ''
  form.apiKey = ''
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    await loadProviders()
    await loadConfig()
  } catch (e) {
    error.value = e?.message || '配置读取失败'
  } finally {
    loading.value = false
  }
}

async function loadModels() {
  loadingModels.value = true
  try {
    const d = await llmApi.getModels(form.provider, form.apiKey || undefined, form.baseUrl || undefined)
    const list = Array.isArray(d.models) ? d.models : []
    models.value = list
    if (!list.length) notifyWarn(d.message || '拉不到模型列表，可以手动填写模型名')
  } catch (e) {
    notifyError(e?.message || '模型列表读取失败')
  } finally {
    loadingModels.value = false
  }
}

function onProviderChange() {
  const p = providers.value.find(x => x.key === form.provider)
  form.baseUrl = p?.base_url || ''
  models.value = []
  testResult.value = null
  // 换厂商后掩码要重新读，先清掉，避免显示上一家的
  keyMasked.value = ''
  hasKey.value = false
}

function onTheme(v) {
  theme.setMode(v)
}

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    await llmApi.saveFullConfig({
      provider: form.provider,
      apiKeys: { [form.provider]: form.apiKey || '' },
      models: { [form.provider]: form.model || '' },
      // 手动值照常保存（作为手动模式的初始值），但自动模式下后端不会用它
      temperature: form.temperature,
      samplingMode: form.samplingMode,
      temperatureOverride: form.temperatureOverride
    })
    if (form.baseUrl) {
      await llmApi.saveConfig({ provider: form.provider, base_url: form.baseUrl })
    }
    notifySuccess('已保存')
    form.apiKey = ''
    await loadConfig()
    await appStore.fetchConfig()
  } catch (e) {
    notifyError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onTest() {
  if (testing.value) return
  testing.value = true
  testResult.value = null
  try {
    const r = await llmApi.testConnection({
      provider: form.provider,
      api_key: form.apiKey || '',
      model: form.model || '',
      base_url: form.baseUrl || ''
    })
    testResult.value = { success: !!r.success, message: r.message || '', hint: r.hint || '' }
  } catch (e) {
    testResult.value = { success: false, message: e?.message || '连接测试失败' }
  } finally {
    testing.value = false
  }
}

async function onDeleteKey() {
  const ok = await confirmDanger({
    title: `删除 ${form.provider} 的 API Key？`,
    consequence: '删除后该厂商回到未配置状态，生成类功能将退回演示模式。',
    confirmText: '确认删除'
  })
  if (!ok) return
  try {
    await llmApi.deleteConfig(form.provider)
    notifySuccess('已删除')
    await loadConfig()
    await appStore.fetchConfig()
  } catch (e) {
    notifyError(e?.message || '删除失败')
  }
}

async function onSaveKnowledge() {
  if (savingKn.value) return
  savingKn.value = true
  try {
    const qs = new URLSearchParams({
      chunkSize: String(kn.chunkSize),
      topK: String(kn.topK),
      embeddingModel: kn.embeddingModel || ''
    })
    await trackedFetch(`${resolveApiBaseURL()}/config/knowledge?${qs.toString()}`, { method: 'POST' })
    notifySuccess('已保存')
  } catch (e) {
    notifyError(e?.message || '保存失败')
  } finally {
    savingKn.value = false
  }
}

async function onSaveFile() {
  if (savingFile.value) return
  savingFile.value = true
  try {
    const qs = new URLSearchParams({
      maxFileSize: String(fileCfg.maxFileSizeMb * 1024 * 1024),
      allowedTypes: fileCfg.allowedTypes
    })
    await trackedFetch(`${resolveApiBaseURL()}/config/file?${qs.toString()}`, { method: 'POST' })
    notifySuccess('已保存')
  } catch (e) {
    notifyError(e?.message || '保存失败')
  } finally {
    savingFile.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: var(--sp-4);
  align-items: start;
}

.hint-line {
  font-size: var(--fs-xs);
  margin: 4px 0 0;
}

.note {
  margin: var(--sp-3) 0 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  line-height: 1.7;
}

.note--ok { background: var(--success-bg); color: var(--wb-ok-text); }
.note--warn { background: var(--wb-warn-bg); color: var(--wb-warn-text); }

/* 开发者选项：默认折叠，展开后也不抢主设置的视觉重心 */
.dev {
  margin-top: var(--sp-2);
  border-top: 1px dashed var(--wb-border);
}

.dev :deep(.el-collapse-item__header) {
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
}

.hint-line--warn { color: var(--wb-warn-text); }
.hint-line--ok { color: var(--wb-ok-text); }

.wb-row--tight { gap: var(--sp-1); }

@media (max-width: 768px) {
  .layout { grid-template-columns: 1fr; }
}
</style>
