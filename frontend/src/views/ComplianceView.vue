<template>
  <div class="wb-page">
    <PageHeader
      title="合规中心"
      description="两套独立关卡：教学合规查「这份教案合不合规范」，数据出校查「这段内容能不能发到校外」。互不替代。"
    />

    <!--
      结论前置：此前这页一上来就是「L1–L5 / R1–R8 / warn」这些内部编号，
      教师看完不知道"我现在安不安全、要不要做什么"。这里先把结论说成人话。
    -->
    <div v-if="safety" class="wb-card wb-card-pad verdict" :class="safety.egress ? 'is-egress' : 'is-local'">
      <div class="verdict__main">
        <div class="verdict__line">
          <StatusTag :status="safety.egress ? 'risk' : 'pass'"
                     :label="safety.egress ? '内容会发到校外' : '内容不出校'" />
          <b>{{ safety.egress ? (safety.target?.provider_label || safety.target?.provider || '云端模型') : '本地 / 校内模型' }}</b>
          <span class="wb-muted">· {{ modeText(safety.mode) }}</span>
        </div>
        <p class="verdict__hint">{{ safetySummary }}</p>
      </div>
      <el-button type="primary" plain @click="goPrecheck">提交前先预检</el-button>
    </div>

    
    <el-tabs v-model="tab">
      <!-- 数据出校 -->
      <el-tab-pane label="数据会不会出校" name="safety">
        <div class="wb-card wb-card-pad wb-stack">
          <div class="wb-row wb-row-between">
            <b>当前策略</b>
            <el-button size="small" :icon="Refresh" :loading="loadingStatus" @click="loadStatus">
              刷新
            </el-button>
          </div>

          <StateBlock :loading="loadingStatus" hint="正在读取合规策略…" :error="statusError" :retryable="false">
            <div v-if="safety" class="wb-stack-sm">
              <div class="wb-row">
                <StatusTag :status="safety.egress ? 'L3' : 'L1'" :label="safety.egress ? '数据会出校' : '数据未出校'" />
                <StatusTag :status="'L3'" :label="`拦截门槛 ${safety.block_level || 'L3'}（中敏感）`" />
                <span class="wb-muted">当前处理：{{ modeText(safety.mode) }}</span>
              </div>
              <p class="note">{{ safety.note }}</p>
              <div class="kv">
                <span class="wb-muted">模型服务</span>
                <span>{{ safety.target?.provider_label || safety.target?.provider || '—' }}</span>
                <span class="wb-muted">地址</span>
                <span class="wb-mono">{{ safety.target?.base_url || '—' }}</span>
                <span class="wb-muted">校内 / 本机</span>
                <span>{{ safety.target?.private ? '是' : '否' }}</span>
              </div>
            </div>
          </StateBlock>
        </div>

        <div class="wb-card wb-card-pad wb-stack lp">
          <div>
            <b>提交前预检</b>
            <p class="wb-card-hint">
              把要生成的课题、补充要求或任意文本贴进来，本地判别它属于哪一级、会怎么处理。
              全程不联网、不调模型 —— 可以放心试。
            </p>
          </div>
          <el-input
            v-model="scanText"
            type="textarea"
            :rows="4"
            placeholder="例如：八年级（3）班学生成绩表，张三 13800138000，语文 92"
          />
          <div class="wb-row">
            <el-button type="primary" :loading="scanning" :disabled="!scanText.trim()" @click="onScan">
              预检
            </el-button>
            <el-checkbox v-model="previewRedact">同时显示脱敏后的文本</el-checkbox>
          </div>

          <StateBlock :error="scanError" :retryable="false">
            <div v-if="scan" class="wb-stack-sm">
              <div class="wb-row">
                <StatusTag :status="scan.level" />
                <StatusTag :status="scan.allowed ? 'pass' : 'risk'" :label="scan.allowed ? '允许发送' : '不允许发送'" />
                <span class="wb-muted">路由：{{ scan.route }} · 动作：{{ scan.action }}</span>
              </div>
              <p class="note">{{ scan.reason }}</p>

              <ul v-if="findings.length" class="findings">
                <li v-for="(f, i) in findings" :key="i" class="finding">
                  <b>{{ f.type || f.kind || '命中' }}</b>
                  <span class="wb-muted">{{ f.label || f.level || '' }}</span>
                  <span v-if="f.snippet || f.text" class="wb-mono">{{ f.snippet || f.text }}</span>
                </li>
              </ul>
              <p v-else class="wb-muted" style="font-size: var(--fs-sm)">未命中任何敏感项。</p>

              <div v-if="scan.redacted_text" class="wb-stack-sm">
                <b style="font-size: var(--fs-sm)">脱敏后（{{ scan.redacted_count }} 处）</b>
                <pre class="dump">{{ scan.redacted_text }}</pre>
              </div>
            </div>
          </StateBlock>
        </div>
      </el-tab-pane>

      <!-- 教学合规 -->
      <el-tab-pane label="教学内容合不合规" name="teaching">
        <div class="wb-card wb-card-pad wb-stack">
          <p class="wb-card-hint">
            纯规则离线扫描，零额度消耗。生成时会自动跑一遍并附在产物上；
            这里可以手动贴任意文本单独检查。
          </p>
          <div class="wb-row">
            <el-form-item label="产物类型" class="wb-grow">
              <el-select v-model="artifactType" style="width: 180px">
                <el-option v-for="t in ARTIFACT_TYPES" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="学段" class="wb-grow">
              <el-input v-model="meta.level" placeholder="例如：初中" style="width: 120px" />
            </el-form-item>
            <el-form-item label="学科" class="wb-grow">
              <el-input v-model="meta.subject" placeholder="例如：物理" style="width: 120px" />
            </el-form-item>
            <el-form-item label="课时" class="wb-grow">
              <el-input-number v-model="meta.duration" :min="15" :max="180" :step="5" />
            </el-form-item>
          </div>
          <el-input
            v-model="checkText"
            type="textarea"
            :rows="6"
            placeholder="粘贴教案 / 课件 / 游戏文本"
          />
          <div class="wb-row">
            <el-button type="primary" :loading="checking" :disabled="!checkText.trim()" @click="onCheck">
              开始扫描
            </el-button>
          </div>

          <StateBlock :error="checkError" :retryable="false">
            <div v-if="report" class="wb-stack-sm">
              <div class="wb-row">
                <StatusTag :status="report.passed ? 'pass' : 'risk'" />
                <span class="wb-muted">{{ report.issue_count ?? 0 }} 个问题 · {{ report.score ?? '—' }} 分</span>
              </div>
              <ul v-if="reportIssues.length" class="findings">
                <li v-for="(it, i) in reportIssues" :key="i" class="finding">
                  <b>{{ it.code }}</b>
                  <span>{{ it.message }}</span>
                  <span v-if="it.hint" class="wb-muted">{{ it.hint }}</span>
                </li>
              </ul>
              <div v-if="report.suggestions?.length" class="wb-stack-sm">
                <b style="font-size: var(--fs-sm)">建议</b>
                <ul class="suggest">
                  <li v-for="(s, i) in report.suggestions" :key="i">{{ s }}</li>
                </ul>
              </div>
            </div>
          </StateBlock>
        </div>

        <div class="wb-card wb-card-pad wb-stack lp">
          <div>
            <b>深度复查（可选 · 需模型）</b>
            <p class="wb-card-hint">
              规则查"有没有、合不合规范"，这个查"好不好、能不能落地" ——
              45 分钟做不完、目标没有活动支撑这类规则写不出来的问题。
              默认关闭，未开启时会如实显示，不会假装审查过。
            </p>
          </div>
          <div class="wb-row">
            <el-button :loading="reviewing" :disabled="!canReview" @click="onReview">
              复查当前教案
            </el-button>
            <span class="wb-muted" style="font-size: var(--fs-xs)">
              需要工作台已有一节课，并生成过教案
            </span>
          </div>

          <StateBlock :error="reviewError" :retryable="false">
            <div v-if="review" class="wb-stack-sm">
              <div v-if="!review.enabled" class="note note--warn">
                未执行：{{ review.reason || '深度复查未开启' }}
              </div>
              <template v-else>
                <p v-if="review.summary" class="wb-dim">{{ review.summary }}</p>
                <ul v-if="reviewFindings.length" class="findings">
                  <li v-for="(f, i) in reviewFindings" :key="i" class="finding">
                    <b>{{ f.code || f.title || '问题' }}</b>
                    <span>{{ f.message || f.detail || '' }}</span>
                  </li>
                </ul>
                <p v-else class="wb-muted" style="font-size: var(--fs-sm)">没有发现需要修改的问题。</p>
              </template>
            </div>
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
import { fetchSafetyStatus, scanSafety } from '@/api/safety'
import { checkCompliance, reviewArtifact } from '@/api/compliance'
import { useLessonStore } from '@/store/lesson'
import { notifyError } from '@/utils/notify'

/**
 * 合规中心。
 *
 * 两套关卡放在一起是为了让教师一次看全，但**不合并**：
 * 教学合规是"内容质量"，数据出校是"数据能不能离校"，判据与后果都不一样。
 */
const store = useLessonStore()
const tab = ref('safety')

const safety = ref(null)
const loadingStatus = ref(false)
const statusError = ref('')

const scanText = ref('')
const previewRedact = ref(false)
const scanning = ref(false)
// 内部模式名 → 人话。教师不需要知道 warn/sanitize/enforce 的区别，
// 只需要知道"会不会拦我"。
const MODE_TEXT = {
  off: '完全不检查',
  warn: '只提醒，不拦截',
  sanitize: '自动脱敏后再发送',
  enforce: '命中就拦下，不发出去',
}
function modeText(m) {
  return MODE_TEXT[m] || (m ? `当前策略：${m}` : '策略未知')
}

const scanError = ref('')
const scan = ref(null)

const ARTIFACT_TYPES = [
  { value: 'lesson_plan', label: '教案' },
  { value: 'ppt', label: 'PPT 课件' },
  { value: 'courseware', label: '课件' },
  { value: 'game', label: '互动游戏' },
  { value: 'animation', label: '动画演示' }
]

const artifactType = ref('lesson_plan')
const meta = ref({ level: '', subject: '', duration: 45 })
const checkText = ref('')
const checking = ref(false)
const checkError = ref('')
const report = ref(null)

const reviewing = ref(false)
const reviewError = ref('')
const review = ref(null)

// 一句话结论：这页最先要回答的是"我现在安不安全、要不要做什么"
const safetySummary = computed(() => {
  const s = safety.value
  if (!s) return ''
  const lvl = s.block_level || 'L3'
  if (!s.egress) {
    return '模型跑在本机或校内，内容不离开你的环境。生成、检索、合规检查都在本地完成。'
  }
  const mode = s.mode
  if (mode === 'off') {
    return '内容会发往校外模型，且当前不做任何拦截。如果教案里含学生姓名、成绩、联系方式，建议改成「先提醒」。'
  }
  if (mode === 'enforce') {
    return `命中 ${lvl} 及以上敏感信息（如姓名+成绩）会直接拦下、不发送。这是最严的一档。`
  }
  if (mode === 'sanitize') {
    return `命中 ${lvl} 及以上敏感信息会自动脱敏后再发送（如「张三」→「某生」），原文不会出校。`
  }
  return `命中 ${lvl} 及以上敏感信息（如姓名+成绩、手机号）会被提醒、但不会拦下。想更严可以到「设置」里改成自动脱敏或直接拦下。`
})


const findings = computed(() => Array.isArray(scan.value?.findings) ? scan.value.findings : [])
const reportIssues = computed(() => Array.isArray(report.value?.issues) ? report.value.issues : [])
const reviewFindings = computed(() => Array.isArray(review.value?.findings) ? review.value.findings : [])
const canReview = computed(() => !!store.taskId)

function goPrecheck() {
  tab.value = 'safety'
  // 等 tab 切完再滚动，否则目标元素还没渲染
  requestAnimationFrame(() => {
    const el = document.querySelector('.lp')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function loadStatus() {
  loadingStatus.value = true
  statusError.value = ''
  try { safety.value = await fetchSafetyStatus() } catch (e) { statusError.value = e?.message || '状态读取失败' } finally { loadingStatus.value = false }
}

async function onScan() {
  if (!scanText.value.trim() || scanning.value) return
  scanning.value = true
  scanError.value = ''
  scan.value = null
  try {
    scan.value = await scanSafety({ text: scanText.value.trim(), previewRedact: previewRedact.value })
  } catch (e) {
    scanError.value = e?.message || '预检失败'
  } finally {
    scanning.value = false
  }
}

async function onCheck() {
  if (!checkText.value.trim() || checking.value) return
  checking.value = true
  checkError.value = ''
  report.value = null
  try {
    const d = await checkCompliance({
      artifactType: artifactType.value,
      content: checkText.value.trim(),
      meta: { ...meta.value, topic: store.topic || '' }
    })
    report.value = d.report || null
  } catch (e) {
    checkError.value = e?.message || '扫描失败'
  } finally {
    checking.value = false
  }
}

async function onReview() {
  if (reviewing.value) return
  reviewing.value = true
  reviewError.value = ''
  review.value = null
  try {
    const d = await reviewArtifact({
      lessonId: store.taskId || undefined,
      kind: 'lesson_plan',
      meta: { level: meta.value.level || store.level, topic: store.topic, duration: store.duration }
    })
    review.value = d.review || null
  } catch (e) {
    reviewError.value = e?.message || '复查失败'
    notifyError(e?.message || '复查失败')
  } finally {
    reviewing.value = false
  }
}

onMounted(() => {
  loadStatus()
  meta.value.level = store.level || ''
  meta.value.subject = store.subject || ''
  meta.value.duration = store.duration || 45
})
</script>

<style scoped>
.kv {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 4px var(--sp-3);
  font-size: var(--fs-sm);
}

.note {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--wb-surface-2);
  font-size: var(--fs-sm);
  color: var(--wb-text-2);
  line-height: 1.7;
}

.note--warn { background: var(--wb-warn-bg); color: var(--wb-warn-text); }

.findings { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }

.finding {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--sp-2);
  border-radius: var(--radius-sm);
  background: var(--wb-surface-2);
  font-size: var(--fs-sm);
}

.suggest { margin: 0; padding-left: 18px; font-size: var(--fs-sm); color: var(--wb-text-2); }

.dump {
  margin: 0;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  background: var(--wb-code-bg);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  color: var(--wb-text-2);
}

.lp { margin-top: var(--sp-4); }
/* 一句话结论卡：让教师三秒内知道"我现在什么情况、下一步做什么" */
.verdict {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
  border-left: 3px solid var(--wb-border-strong);
}
.verdict.is-egress {
  border-left-color: var(--wb-warn-text);
  background: var(--wb-warn-bg);
}
.verdict.is-local {
  border-left-color: var(--wb-brand);
}
.verdict__main { min-width: 0; flex: 1 1 480px; }
.verdict__line {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.verdict__hint {
  margin: 6px 0 0;
  font-size: var(--fs-sm);
  line-height: 1.6;
  color: var(--wb-text-2);
}

</style>
