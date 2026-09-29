<template>
  <div class="bp-panel">
    <header class="bp-head">
      <span class="bp-title">教学蓝图</span>
      <el-tag v-if="status === 'confirmed'" size="small" type="success" effect="plain">
        已确认
      </el-tag>
      <el-tag v-else-if="status === 'skipped'" size="small" type="info" effect="plain">
        已跳过
      </el-tag>
      <el-tag v-else size="small" type="warning" effect="plain">待确认</el-tag>
      <el-button
        v-if="hasBlueprint"
        link
        size="small"
        :disabled="busy"
        @click="emit('regenerate')"
      >
        重新设计
      </el-button>
    </header>

    <!-- 空状态：也要说清楚"现在能做什么"，不能只留一片空白 -->
    <div v-if="!hasBlueprint" class="bp-empty">
      <p>还没有蓝图。蓝图是生成前的环节安排 —— 先看一遍再决定要不要生成。</p>
      <el-button size="small" type="primary" :loading="busy" @click="emit('regenerate')">
        生成蓝图
      </el-button>
      <p class="bp-empty-skip">
        也可以
        <el-button link type="primary" size="small" :disabled="busy" @click="emit('skip')">
          跳过蓝图直接生成
        </el-button>
      </p>
    </div>

    <template v-else>
      <!-- 降级必须说清原因：否则教师会以为这份蓝图是模型精心设计的 -->
      <p v-if="degraded" class="bp-degraded">
        {{ error || '蓝图未能由模型生成，已用通用骨架代替' }} —— 可以直接生成，也可以重新设计。
      </p>

      <p v-if="blueprint.summary" class="bp-summary">{{ blueprint.summary }}</p>

      <ol class="bp-stages">
        <li v-for="(s, i) in stages" :key="s.id || i" class="bp-stage">
          <div class="bp-stage-head">
            <span class="bp-no">{{ i + 1 }}</span>
            <span class="bp-name">{{ s.name || '未命名环节' }}</span>
            <span v-if="s.minutes" class="bp-min">{{ s.minutes }} 分钟</span>
            <el-tag v-if="s.isKeyPoint" size="small" type="danger" effect="plain">重点</el-tag>
            <el-tag v-if="s.isHardPoint" size="small" type="warning" effect="plain">难点</el-tag>
          </div>
          <p v-if="s.purpose" class="bp-line">目的：{{ s.purpose }}</p>
          <p v-if="s.teacherActivity" class="bp-line">教师：{{ s.teacherActivity }}</p>
          <p v-if="s.studentActivity" class="bp-line">学生：{{ s.studentActivity }}</p>
          <p v-if="s.interaction" class="bp-line">互动：{{ s.interaction }}</p>
          <p v-if="s.knowledgeRefs?.length" class="bp-line">
            知识点：{{ s.knowledgeRefs.join('、') }}
          </p>
          <p v-if="s.risk" class="bp-line bp-risk">风险：{{ s.risk }}</p>
        </li>
      </ol>

      <p class="bp-total">环节总时长：{{ totalMinutes }} 分钟</p>

      <!-- 校验提示：只报告、不阻断 -->
      <ul v-if="warnings.length" class="bp-warns">
        <li v-for="(w, i) in warnings" :key="i">{{ w }}</li>
      </ul>

      <footer class="bp-actions">
        <el-button size="small" type="primary" :disabled="busy" @click="emit('confirm')">
          确认蓝图并生成
        </el-button>
        <el-button size="small" :disabled="busy" @click="emit('skip')">
          直接生成（跳过蓝图）
        </el-button>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useLessonStore } from '@/store/lesson'

const props = defineProps({
  busy: { type: Boolean, default: false }
})
const emit = defineEmits(['confirm', 'skip', 'regenerate'])

const store = useLessonStore()

const blueprint = computed(() => store.teachingBlueprint || null)
const stages = computed(() => blueprint.value?.stages || [])
const hasBlueprint = computed(() => stages.value.length > 0)
const status = computed(() => blueprint.value?.status || '')
const degraded = computed(() => blueprint.value?.source !== 'model')
const error = computed(() => blueprint.value?.error || '')
const warnings = computed(() => {
  const w = blueprint.value?.warnings
  return Array.isArray(w) ? w.slice(0, 5) : []
})
const totalMinutes = computed(() =>
  blueprint.value?.totalMinutes || stages.value.reduce((n, s) => n + (Number(s.minutes) || 0), 0))
</script>

<style scoped>
.bp-panel {
  padding: 12px 14px;
}
.bp-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bp-title {
  font-size: 14px;
  font-weight: 600;
  margin-right: auto;
}
.bp-empty {
  padding: 14px 0;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(0, 0, 0, 0.55);
}
.bp-empty-skip {
  margin: 6px 0 0;
}
.bp-degraded {
  margin: 0 0 10px;
  padding: 8px 10px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #8a5a00;
  background: rgba(230, 162, 60, 0.12);
  border-radius: 6px;
}
.bp-summary {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.75;
  color: rgba(0, 0, 0, 0.7);
}
.bp-stages {
  margin: 0 0 10px;
  padding: 0;
  list-style: none;
}
.bp-stage {
  padding: 8px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.bp-stage:first-child {
  border-top: none;
}
.bp-stage-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.bp-no {
  width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  font-size: 11px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.06);
}
.bp-name {
  font-size: 13.5px;
  font-weight: 600;
}
.bp-min {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.5);
}
.bp-line {
  margin: 3px 0 0 24px;
  font-size: 12.5px;
  line-height: 1.7;
  color: rgba(0, 0, 0, 0.6);
}
.bp-risk {
  color: #b06a00;
}
.bp-total {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: rgba(0, 0, 0, 0.5);
}
.bp-warns {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.8;
  color: #8a5a00;
}
.bp-actions {
  display: flex;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
</style>
