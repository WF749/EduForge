<template>
  <div class="bar">
    <!--
      摘要行。刻意加一个「当前备课」标签：此前这一行只有一串灰字 +
      两个 text 按钮，整行读起来像页面标题栏，新用户根本不会去点它。
      现在它有身份标签、有描边按钮，主题没设时按钮还会变成主色。
    -->
    <div class="bar__row" :class="{ 'is-empty': showTopicError }">
      <span class="bar__tag">当前备课</span>

      <template v-if="store.topic.trim()">
        <span class="bar__topic wb-truncate">{{ store.topic }}</span>
        <span class="bar__meta">
          {{ store.subject || '未设学科' }} · {{ store.grade || '未设年级' }} ·
          {{ store.duration }} 分钟 · {{ store.difficultyLabel }}
        </span>
      </template>
      <span v-else class="bar__meta bar__meta--lead">
        还没开始 —— 在下面的对话里说一句就行，例如「生成一份浮力教案」
      </span>
      <!--
        学科矛盾提示**必须放在摘要行**：此前放在展开面板里，而面板默认收起，
        等于没有提示 —— 用户用默认的「综合课程」生成了半天，出来的却是别的学科。
      -->
      <span v-if="subjectWarning" class="bar__flag" role="alert" :title="subjectWarning.message">
        ⚠ 主题像{{ subjectWarning.subject }}，当前学科是「{{ store.subject }}」
        <el-button size="small" type="primary" link @click="adoptSubject">改为{{ subjectWarning.subject }}</el-button>
      </span>

      <div class="bar__actions">
        <el-button
          size="small"
          :type="showTopicError ? 'primary' : 'default'"
          :plain="!showTopicError"
          :icon="EditPen"
          @click="toggle"
        >
          {{ expanded ? '收起' : (store.topic.trim() ? '编辑课程信息' : '设置这节课') }}
        </el-button>
        <el-button size="small" text :icon="RefreshLeft" @click="onNew">新建</el-button>
      </div>
    </div>

    <!-- 详细字段：默认收起。主题为空时才自动展开，填完自动收回 -->
    <div v-show="expanded" class="bar__more">
      <!--
        主题与学科矛盾时提醒。
        为什么不自动改：学科是教师的教学决策，"数学×生物"跨学科课本身就合法，
        系统替他改等于把合法的跨学科课掰成单科。
      -->
      <div v-if="subjectWarning" class="bar__warn" role="alert">
        <span class="bar__warn-text">{{ subjectWarning.message }}</span>
        <el-button size="small" type="primary" link @click="adoptSubject">
          改为「{{ subjectWarning.subject }}」
        </el-button>
      </div>

      <label class="bar__field bar__field--topic">
        <span class="bar__label">
          教学主题
          <b class="bar__req" aria-label="必填">*</b>
        </span>
        <el-input
          v-model="store.topic"
          placeholder="例如：浮力 / 二次函数的应用"
          maxlength="60"
          clearable
          :class="{ 'is-invalid': showTopicError }"
          aria-describedby="topic-tip"
        />
      </label>

      <!-- 学科与年级改成可输入：教师嘴里是"初二下""高一必修一"，
           压成下拉枚举等于逼他把学情翻译成系统的词 -->
      <label class="bar__field">
        <span class="bar__label">学科</span>
        <el-select v-model="store.subject" filterable allow-create default-first-option style="width: 130px">
          <el-option v-for="s in SUBJECTS" :key="s" :label="s" :value="s" />
        </el-select>
      </label>

      <label class="bar__field">
        <span class="bar__label">年级 / 受众</span>
        <el-select v-model="store.grade" filterable allow-create default-first-option style="width: 140px">
          <el-option v-for="g in GRADES" :key="g" :label="g" :value="g" />
          <el-option label="大学生" value="大学生" />
        </el-select>
      </label>

      <label class="bar__field">
        <span class="bar__label">时长</span>
        <el-select v-model="store.duration" style="width: 100px">
          <el-option v-for="d in DURATIONS" :key="d" :label="`${d} 分钟`" :value="d" />
        </el-select>
      </label>

      <label class="bar__field">
        <span class="bar__label">难度</span>
        <el-select v-model="store.difficulty" style="width: 110px">
          <el-option v-for="d in DIFFICULTIES" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </label>

      <label class="bar__field bar__field--grow">
        <span class="bar__label">
          知识点 / 补充要求
          <span class="bar__opt">选填</span>
        </span>
        <el-input
          v-model="store.keyPoints"
          type="textarea"
          :rows="2"
          placeholder="一行一个知识点；也可以写「要多一些生活实例」这类要求"
        />
      </label>

      <label class="bar__field">
        <span class="bar__label">知识库范围</span>
        <el-select v-model="store.knowledgeScope" style="width: 150px">
          <el-option label="内置 + 我的资料" value="both" />
          <el-option label="仅内置知识库" value="system" />
          <el-option label="仅我的资料" value="personal" />
          <el-option label="不使用知识库" value="none" />
        </el-select>
      </label>

      <p v-if="showTopicError" id="topic-tip" class="bar__error" role="alert">
        填个主题就知道要备哪一课；也可以直接在对话里说，我会自己读出来。
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { EditPen, RefreshLeft } from '@element-plus/icons-vue'
import { useLessonStore, SUBJECTS, GRADES, DIFFICULTIES } from '@/store/lesson'
import { suggestSubject } from '@/utils/subjectGuard'

/**
 * 课程信息条。
 *
 * 三条刻意的取舍：
 *  1. **首屏只留一行摘要**。旧版把主题、难度、知识点、知识库范围全铺开，
 *     教师进来第一件事是"填一张配置表"，而本产品的核心是"直接告诉 AI 要备什么课"。
 *     现在除主题外的字段全部收起；主题为空时也不展开表单，只给一句人话引导。
 *  2. **填完自动收回**。此前 watch 只负责展开、从不收起，打完字还是占着 230px。
 *     现在按"有没有主题"双向收敛；教师手动点开过就尊重他的选择（manual 标记）。
 *  3. **学科 / 年级可输入**。下拉枚举把开放的学情压成了系统的词，
 *     而"七年级→初中"的映射藏在 levelForGrade 里，教师选的时候并不知道。
 */
/**
 * 展开状态由父级持有（`v-model:open`）。
 * 这样对话区的「设置这节课信息」按钮也能把它打开 —— 入口必须出现在
 * 用户一定会看的地方（对话流），而不是只挂在顶部这条容易被当成标题栏的线上。
 */
const props = defineProps({
  open: { type: Boolean, default: false }
})
const emit = defineEmits(['update:open'])

const store = useLessonStore()

// 主题像另一门课、但学科没跟着改 → 提醒（"细胞的结构"配"数学"会导致整份课件跑偏）
const subjectWarning = computed(() => suggestSubject(store.topic, store.subject))
function adoptSubject() {
  if (subjectWarning.value) store.subject = subjectWarning.value.subject
}

/** 教师手动点开后不再自动收起 —— 否则他一填完主题面板就自己关了 */
const manual = ref(false)

const DURATIONS = [15, 20, 30, 40, 45, 60, 90]

const expanded = computed(() => props.open)
const showTopicError = computed(() => !store.topic.trim())

function setOpen(v) {
  emit('update:open', v)
  manual.value = v
}

function toggle() {
  setOpen(!expanded.value)
}

function onNew() {
  store.resetLesson()
  manual.value = false
  emit('update:open', true)
}

// 没有主题 → 说明还没开始，把字段摊开让他填；填上了 → 收起，把空间还给对话。
// 注意区分"状态"与"状态变化"：只有在**从没有变成有**的那一刻才自动收起，
// 否则教师正在改难度（主题本来就有）时会被突然关掉面板。
watch(showTopicError, (empty, was) => {
  if (empty) {
    if (!manual.value) emit('update:open', true)
    return
  }
  if (was === empty) return
  // 刚填上主题：无论面板是自动展开的还是他手动点开的，都让位给对话
  manual.value = false
  emit('update:open', false)
}, { immediate: true })
</script>

<style scoped>
.bar {
  border-bottom: 1px solid var(--wb-border);
  background: var(--wb-surface);
  padding: var(--sp-2) var(--sp-4);
}

.bar__row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: 40px;
}

/* 身份标签：这一行是"当前备课"，不是页面标题 */
.bar__tag {
  flex: none;
  font-size: var(--fs-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
}

/* 还没设主题时给整条一点提示色，避免它彻底隐形 */
.bar__row.is-empty .bar__tag {
  background: var(--brand-soft);
  color: var(--brand-text);
}

.bar__topic {
  font-size: var(--fs-md);
  font-weight: 600;
  max-width: 280px;
  flex: none;
}

.bar__meta {
  font-size: var(--fs-sm);
  color: var(--wb-text-3);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 还没有备课时，这句引导比元信息更重要，给它正常色阶保证读得清 */
.bar__meta--lead {
  color: var(--wb-text-2);
  white-space: normal;
}

.bar__actions {
  display: flex;
  align-items: center;
  gap: 0;
  margin-left: auto;
  flex: none;
}

.bar__more {
  display: flex;
  gap: var(--sp-3);
  flex-wrap: wrap;
  align-items: flex-end;
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px dashed var(--wb-border);
}

.bar__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.bar__field--topic { flex: 1 1 260px; min-width: 220px; }
.bar__field--grow { flex: 1 1 100%; }

.bar__label {
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--wb-text-2);
  display: flex;
  align-items: center;
  gap: 4px;
}

.bar__req { color: var(--wb-risk-text); }

.bar__opt {
  font-weight: 400;
  color: var(--wb-text-3);
}

.bar__error {
  flex: 1 1 100%;
  margin: 0;
  font-size: var(--fs-xs);
  color: var(--wb-risk-text);
}

.bar :deep(.is-invalid .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger) inset !important;
}

@media (max-width: 768px) {
  .bar__meta { display: none; }
  .bar__row { flex-wrap: nowrap; }
}
.bar__warn {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-bottom: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--wb-warn-bg);
  border: 1px solid var(--wb-border-strong);
  font-size: var(--fs-sm);
  line-height: 1.5;
}
.bar__warn-text { color: var(--wb-warn-text); flex: 1 1 320px; }

.bar__flag {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  padding: 2px var(--sp-2);
  border-radius: var(--radius-sm);
  background: var(--wb-warn-bg);
  border: 1px solid var(--wb-border-strong);
  color: var(--wb-warn-text);
  font-size: var(--fs-sm);
  white-space: nowrap;
}

</style>
