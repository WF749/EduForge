<template>
  <div class="wb-page">
    <PageHeader
      title="系统监控"
      description="调用指标、Agent 能力与多模态分析。这一页是运维向能力，日常备课用不到。"
      badge="运维"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loadingMetrics" @click="loadMetrics">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 健康 -->
    <div class="wb-card wb-card-pad status-bar">
      <div class="status-bar__item">
        <span class="wb-muted">后端健康</span>
        <StatusTag :status="health?.ok ? 'done' : 'failed'" :label="health?.ok ? '正常' : '不可达'" />
      </div>
      <span class="wb-muted" style="font-size: var(--fs-xs)">
        {{ health?.ok ? `HTTP ${health.status}` : (health?.error || '尚未探测') }}
      </span>
    </div>

    <el-tabs v-model="tab">
      <!-- 指标 -->
      <el-tab-pane label="运行指标" name="metrics">
        <div class="wb-card wb-card-pad wb-stack">
          <div class="wb-row">
            <el-button size="small" :icon="Refresh" :loading="loadingMetrics" @click="loadMetrics">
              刷新指标
            </el-button>
            <el-checkbox v-model="withRecent">同时取最近调用明细</el-checkbox>
          </div>

          <StateBlock :loading="loadingMetrics" :error="metricError" :empty="!summary" empty-title="暂无指标" :rows="4" @retry="loadMetrics">
            <div v-if="summary" class="wb-stack-sm">
              <div class="metrics">
                <div v-for="(v, k) in flatMetrics" :key="k" class="metric">
                  <span class="wb-muted">{{ METRIC_LABELS[k] || k }}</span>
                  <b>{{ v }}</b>
                </div>
              </div>

              <div v-if="events.length" class="wb-stack-sm">
                <b style="font-size: var(--fs-sm)">最近调用</b>
                <el-table :data="events" size="small" max-height="320" stripe>
                  <el-table-column prop="kind" label="类型" width="90" />
                  <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
                  <el-table-column label="耗时" width="100">
                    <template #default="{ row }">
                      {{ row.duration_ms != null ? `${Math.round(row.duration_ms)} ms` : '—' }}
                    </template>
                  </el-table-column>
                  <el-table-column label="结果" width="90">
                    <template #default="{ row }">
                      <StatusTag :status="row.ok ? 'done' : 'failed'" :label="row.ok ? '成功' : '失败'" :dot="false" />
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </StateBlock>
        </div>
      </el-tab-pane>

      <!-- Agent -->
      <el-tab-pane label="Agent" name="agent">
        <div class="wb-card wb-card-pad wb-stack">
          <p class="wb-card-hint">
            先规划再执行：看它打算怎么做，确认无误再跑。高风险工具默认不放行，
            必须在这里显式勾选才会被批准。
          </p>
          <el-input v-model="goal" type="textarea" :rows="2" placeholder="例如：整理一份八年级物理浮力的常见误区清单" />
          <div class="wb-row">
            <el-button :loading="planning" :disabled="!goal.trim()" @click="onPlan">只看计划</el-button>
            <el-button type="primary" :loading="running" :disabled="!goal.trim()" @click="onRun">执行</el-button>
          </div>

          <StateBlock :error="agentError" :retryable="false">
            <div v-if="steps.length" class="wb-stack-sm">
              <b style="font-size: var(--fs-sm)">计划步骤</b>
              <ol class="steps">
                <li v-for="(s, i) in steps" :key="i">
                  <span class="wb-mono">{{ s.tool || s.action || 'step' }}</span>
                  <span>{{ s.description || s.reason || '' }}</span>
                </li>
              </ol>
            </div>

            <div v-if="riskyTools.length" class="note note--warn">
              以下工具属于高风险，默认不执行：{{ riskyTools.join('、') }}。
              勾选下方后才会放行。
              <div class="wb-row" style="margin-top: 8px">
                <el-checkbox-group v-model="approvals">
                  <el-checkbox v-for="t in riskyTools" :key="t" :value="t">{{ t }}</el-checkbox>
                </el-checkbox-group>
              </div>
            </div>

            <pre v-if="agentResult" class="dump">{{ agentResult }}</pre>
          </StateBlock>
        </div>

        <div class="wb-card wb-card-pad wb-stack lp">
          <div class="wb-row wb-row-between">
            <b>已注册工具</b>
            <el-button size="small" :icon="Refresh" :loading="loadingTools" @click="loadTools">刷新</el-button>
          </div>
          <StateBlock :loading="loadingTools" :error="toolError" :empty="!tools.length" empty-title="没有注册工具" @retry="loadTools">
            <el-table :data="tools" size="small" max-height="360" stripe>
              <el-table-column prop="name" label="名称" width="160" />
              <el-table-column prop="category" label="分类" width="110" />
              <el-table-column label="风险" width="90">
                <template #default="{ row }">
                  <StatusTag
                    :status="row.risk === 'high' ? 'risk' : row.risk === 'medium' ? 'warn' : 'pass'"
                    :label="row.risk"
                    :dot="false"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
            </el-table>
          </StateBlock>
        </div>
      </el-tab-pane>

      <!-- 多模态 -->
      <el-tab-pane label="多模态" name="multimodal">
        <div class="wb-card wb-card-pad wb-stack">
          <p class="wb-card-hint">对一段文本做语义分析、提取关键概念，或生成跨模态描述。</p>
          <el-input v-model="mmText" type="textarea" :rows="4" placeholder="粘贴一段教学内容" />
          <div class="wb-row">
            <el-button :loading="mmLoading" :disabled="!mmText.trim()" @click="onAnalyze">语义分析</el-button>
            <el-select v-model="mmTarget" style="width: 150px" aria-label="目标模态">
              <el-option label="转 PPT 描述" value="ppt" />
              <el-option label="转教案描述" value="lesson_plan" />
              <el-option label="转图像描述" value="image" />
              <el-option label="转视频描述" value="video" />
            </el-select>
            <el-button :loading="mmLoading" :disabled="!mmText.trim()" @click="onCrossModal">跨模态转换</el-button>
          </div>

          <StateBlock :error="mmError" :retryable="false">
            <pre v-if="mmResult" class="dump">{{ mmResult }}</pre>
          </StateBlock>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { fetchHealth, fetchMetrics, fetchMetricEvents } from '@/api/system'
import { fetchAgentTools, planAgent, runAgent } from '@/api/agent'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'
import { notifyError, notifyWarn } from '@/utils/notify'

/**
 * 系统监控（运维向）。
 *
 * Agent 的高风险工具默认**不批准** —— 这是红线：前端不能替教师点"同意"。
 * 只有在这里显式勾选，请求里才会带上 approvals。
 */
const tab = ref('metrics')

const health = ref(null)

const summary = ref(null)
const events = ref([])
const loadingMetrics = ref(false)
const metricError = ref('')
const withRecent = ref(true)

const goal = ref('')
const steps = ref([])
const planning = ref(false)
const running = ref(false)
const agentError = ref('')
const agentResult = ref('')

const tools = ref([])
const loadingTools = ref(false)
const toolError = ref('')
const approvals = ref([])

const mmText = ref('')
const mmTarget = ref('ppt')
const mmResult = ref('')
const mmLoading = ref(false)
const mmError = ref('')

const METRIC_LABELS = {
  total_calls: '总调用',
  success_rate: '成功率',
  p95_ms: 'P95 延迟',
  total_tokens: 'Token 总量',
  cost: '估算成本',
  llm_calls: '模型调用',
  tool_calls: '工具调用',
  error_count: '失败次数'
}

/** 指标只有一层数值才有展示意义，嵌套对象不摊平会渲染成 [object Object] */
const flatMetrics = computed(() => {
  const out = {}
  for (const [k, v] of Object.entries(summary.value || {})) {
    if (typeof v === 'number' || typeof v === 'string') out[k] = v
  }
  return out
})

const riskyTools = computed(() =>
  tools.value.filter(t => t.requires_approval || t.risk === 'high').map(t => t.name))

async function loadHealth() {
  health.value = await fetchHealth()
}

async function loadMetrics() {
  loadingMetrics.value = true
  metricError.value = ''
  try {
    const d = await fetchMetrics({ recent: withRecent.value ? 50 : 0 })
    summary.value = d.summary || null
    if (withRecent.value) {
      const e = await fetchMetricEvents({ limit: 50 })
      events.value = Array.isArray(e.events) ? e.events : []
    } else {
      events.value = []
    }
  } catch (err) {
    metricError.value = err?.message || '指标读取失败'
  } finally {
    loadingMetrics.value = false
  }
}

async function loadTools() {
  loadingTools.value = true
  toolError.value = ''
  try {
    const d = await fetchAgentTools()
    tools.value = Array.isArray(d.tools) ? d.tools : []
  } catch (e) {
    toolError.value = e?.message || '工具清单读取失败'
  } finally {
    loadingTools.value = false
  }
}

async function onPlan() {
  if (planning.value) return
  planning.value = true
  agentError.value = ''
  agentResult.value = ''
  try {
    const d = await planAgent(goal.value.trim())
    steps.value = Array.isArray(d.steps) ? d.steps : []
  } catch (e) {
    agentError.value = e?.message || '规划失败'
  } finally {
    planning.value = false
  }
}

async function onRun() {
  if (running.value) return
  running.value = true
  agentError.value = ''
  agentResult.value = ''
  try {
    const d = await runAgent({
      goal: goal.value.trim(),
      approvals: approvals.value.slice(),   // 只放行显式勾选的
      maxSteps: 6,
      verify: true
    })
    agentResult.value = JSON.stringify(d, null, 2)
  } catch (e) {
    agentError.value = e?.message || '运行失败'
    notifyError(e?.message || '运行失败')
  } finally {
    running.value = false
  }
}

async function onAnalyze() {
  if (mmLoading.value) return
  mmLoading.value = true
  mmError.value = ''
  mmResult.value = ''
  try {
    const res = await trackedFetch(`${resolveApiBaseURL()}/multimodal/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: mmText.value.trim() })
    })
    const d = await res.json()
    if (!res.ok) throw new Error(d?.detail || d?.message || '分析失败')
    mmResult.value = JSON.stringify({ semantics: d.semantics, concepts: d.concepts }, null, 2)
  } catch (e) {
    mmError.value = e?.message || '分析失败'
  } finally {
    mmLoading.value = false
  }
}

async function onCrossModal() {
  if (mmLoading.value) return
  mmLoading.value = true
  mmError.value = ''
  mmResult.value = ''
  try {
    const res = await trackedFetch(`${resolveApiBaseURL()}/multimodal/cross-modal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: mmText.value.trim(), target_type: mmTarget.value })
    })
    const d = await res.json()
    if (!res.ok) throw new Error(d?.detail || d?.message || '转换失败')
    mmResult.value = JSON.stringify(d.result, null, 2)
  } catch (e) {
    mmError.value = e?.message || '转换失败'
    notifyWarn(e?.message || '转换失败')
  } finally {
    mmLoading.value = false
  }
}

onMounted(() => {
  loadHealth()
  loadMetrics()
  loadTools()
})
</script>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-5);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}

.status-bar__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--fs-sm);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--sp-3);
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--wb-surface-2);
  font-size: var(--fs-sm);
}

.metric b { font-size: var(--fs-lg); }

.steps { margin: 0; padding-left: 20px; font-size: var(--fs-sm); }
.steps li { padding: 2px 0; }

.note {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  line-height: 1.7;
}

.note--warn { background: var(--wb-warn-bg); color: var(--wb-warn-text); }

.dump {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  background: var(--wb-code-bg);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  color: var(--wb-text-2);
}

.lp { margin-top: var(--sp-4); }
</style>
