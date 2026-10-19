<template>
  <div class="wb">
    <LessonBar v-model:open="barOpen" />

    <div class="wb__body">
      <!-- 左侧「我的备课」：恒为浮层，默认收起，不挤压对话 -->
      <aside class="wb__aside" :class="{ 'is-open': asideOpen }" aria-label="我的备课">
        <div class="wb__aside-head">
          <b>我的备课</b>
          <button class="icon-btn" type="button" aria-label="关闭我的备课" @click="asideOpen = false">
            <el-icon :size="16"><Close /></el-icon>
          </button>
        </div>

        <div class="wb__aside-ops">
          <el-button size="small" :icon="Plus" @click="onNewTask">新建备课</el-button>
          <router-link to="/lessons" class="wb__aside-all">查看全部</router-link>
        </div>

        <StateBlock
          :loading="loadingCourses"
          hint="正在读取备课记录…"
          :error="courseError"
          :empty="!store.recentTasks.length"
          empty-title="还没有备课"
          empty-description="在对话里说出你要备的课，这里就会多出一条记录。"
          :rows="4"
          @retry="loadCourses"
        >
          <ul class="course-list">
            <li v-for="t in store.recentTasks" :key="t.id">
              <button
                class="course-item"
                type="button"
                :class="{ 'is-active': t.id === store.taskId }"
                @click="onSwitch(t.id)"
              >
                <span class="course-item__topic">{{ t.topic || '未命名备课' }}</span>
                <span class="course-item__meta">
                  {{ t.subject || '—' }} · {{ t.grade || '—' }} · {{ t.duration || 45 }} 分钟
                </span>
                <span class="course-item__badge">{{ t.artifactCount }}/4</span>
              </button>
            </li>
          </ul>
        </StateBlock>
      </aside>

      <!-- 中间对话：主舞台 -->
      <section class="wb__chat">
        <button
          class="wb__aside-toggle"
          type="button"
          aria-label="打开我的备课"
          @click="asideOpen = true"
        >
          <el-icon><ArrowRight /></el-icon>
          <span>备课</span>
        </button>

        <div class="wb__chat-inner">
          <!--
            模式切换：**当前备课** 走 /lesson-chat/ask（带这一节课的学科、年级、
            主题、蓝图与产物），**通用问答** 走 /chat/*（不带任何备课语境）。
            两条是各自独立的后端链路，这里只是"挂载哪个组件"的切换，
            不把两套消息塞进同一个数组 —— 那会让两边的上下文互相污染。
          -->
          <div class="chat-mode">
            <el-radio-group v-model="chatMode" size="small">
              <el-radio-button value="lesson">当前备课</el-radio-button>
              <el-radio-button value="general">通用问答</el-radio-button>
            </el-radio-group>
            <span class="chat-mode__hint">{{ chatModeHint }}</span>
            <router-link v-if="chatMode === 'general'" to="/assistant" class="chat-mode__more">
              会话与历史
            </router-link>
          </div>

          <LessonChat
            v-if="chatMode === 'lesson'"
            class="chat-pane"
            :active-kind="activeKind"
            :revise-kinds="['lesson_plan']"
            :busy="busy"
            @generate="onGenerate"
            @revise="onRevise"
            @switch-kind="activeKind = $event"
            @open-context="barOpen = true"
          />
          <GeneralChat v-else class="chat-pane" :conv-id="generalConvId" />
        </div>
      </section>

      <!-- 右侧成品列 -->
      <section class="wb__side" :class="{ 'is-open': sideOpen }" aria-label="成品">
        <div class="wb__side-head">
          <el-tabs v-model="sideTab" class="wb__tabs">
            <el-tab-pane label="成品" name="artifacts" />
            <el-tab-pane label="蓝图" name="blueprint" />
            <el-tab-pane label="引用" name="citations" />
            <el-tab-pane label="版本" name="versions" />
          </el-tabs>
          <button class="icon-btn wb__side-close" type="button" aria-label="收起成品列" @click="sideOpen = false">
            <el-icon :size="16"><Close /></el-icon>
          </button>
        </div>

        <div class="wb__side-body">
          <!-- 成品 -->
          <div v-show="sideTab === 'artifacts'" class="wb-stack-sm">
            <!-- 提示只说一次。之前四张卡片各写一句"先填写教学主题"，重复且像在埋怨用户 -->
            <p v-if="!store.topic.trim()" class="wb-card-hint">
              在左侧对话里说出这节课备什么，四类产物就能生成。
            </p>

            <ArtifactCard
              v-for="a in ARTIFACTS"
              :key="a.id"
              :kind="a.id"
              :progress="pptProgress"
              :step-hint="pptStep"
              @generate="onGenerate"
            />

            <!-- 高级生成设置：默认入口就在上面四张卡片，这里是"我要单独调参数"的次级入口。
                 不再作为一级导航 —— 新手不该先判断该去哪个页面生成。 -->
            <div class="adv">
              <p class="wb-card-hint">
                默认就在上面生成，产物自动归入这一节备课。要单独调参数（页数、主题色、
                动画风格、游戏题型）时，用高级生成设置。
              </p>
              <el-button size="small" text @click="onAdvancedGenerate">
                高级生成设置
              </el-button>
            </div>
          </div>

          <!-- 蓝图 -->
          <div v-show="sideTab === 'blueprint'" class="wb-stack-sm">
            <p class="wb-card-hint">
              蓝图是生成前的课堂环节安排，用来和你想的上法对齐。确认过的蓝图才会参与生成；
              直接生成也不会被拦。
            </p>
            <div class="wb-row">
              <el-button
                size="small"
                type="primary"
                :loading="store.blueprintLoading"
                :disabled="!store.topic.trim()"
                @click="onBlueprint"
              >
                生成蓝图
              </el-button>
              <el-button
                v-if="store.hasBlueprint"
                size="small"
                :disabled="store.blueprintStatus === 'confirmed'"
                @click="store.confirmBlueprint()"
              >
                确认并用于生成
              </el-button>
            </div>

            <p v-if="blueprintError" class="wb-note wb-note--warn">{{ blueprintError }}</p>

            <div v-if="store.hasBlueprint" class="wb-stack-sm">
              <div class="wb-row">
                <StatusTag :status="store.blueprintStatus === 'confirmed' ? 'done' : 'pending'" />
                <span class="wb-muted">共 {{ totalMinutes }} 分钟 · {{ stageCount }} 个环节</span>
              </div>
              <ol class="stages">
                <li v-for="(s, i) in stages" :key="i" class="stage">
                  <div class="stage__row">
                    <b>{{ s.name || s.title || `环节 ${i + 1}` }}</b>
                    <span class="wb-muted">{{ s.minutes ?? s.duration ?? 0 }} 分钟</span>
                  </div>
                  <p v-if="s.goal || s.description" class="stage__desc">
                    {{ s.goal || s.description }}
                  </p>
                </li>
              </ol>
              <el-button size="small" text @click="store.discardBlueprint()">放弃这份蓝图</el-button>
            </div>
          </div>

          <!-- 引用 -->
          <div v-show="sideTab === 'citations'" class="wb-stack-sm">
            <p class="wb-card-hint">
              四路生成共用同一份知识快照，所以这里列出的依据对教案 / PPT / 动画 / 游戏是一致的。
            </p>
            <EmptyState
              v-if="!citations.length"
              title="这次生成没有用到知识库"
              description="可能是知识库里没有相关内容，或者生成时选择了不使用知识库。"
              icon="Document"
            />
            <ul v-else class="cite-list">
              <li v-for="(c, i) in citations" :key="i" class="cite">
                <span class="cite__src">{{ c.source || c.title || '资料' }}</span>
                <span v-if="c.heading_path" class="cite__path">{{ c.heading_path }}</span>
                <p class="cite__text">{{ c.content || c.text || '' }}</p>
              </li>
            </ul>
          </div>

          <!-- 版本 -->
          <div v-show="sideTab === 'versions'" class="wb-stack-sm">
            <p class="wb-card-hint">
              教案的每一次修改都会记成一个新版本，回退不会删除历史。
            </p>
            <EmptyState
              v-if="!store.taskId"
              title="还没有备课"
              description="开始一节课并生成教案后，这里会出现版本记录。"
              icon="Files"
            />
            <StateBlock v-else :loading="loadingVersions" :error="versionError" :rows="3" @retry="loadVersions">
              <EmptyState
                v-if="!versions.length"
                title="还没有版本"
                description="生成一份教案后，这里会记下第一版。"
                icon="Files"
              />
              <ul v-else class="ver-list">
                <li v-for="v in versions" :key="v.version" class="ver">
                  <div class="ver__row">
                    <b>v{{ v.version }}</b>
                    <StatusTag v-if="v.version === currentVersion" status="done" label="当前" />
                  </div>
                  <p class="ver__note">{{ v.note || v.message || '—' }}</p>
                  <el-button
                    v-if="v.version !== currentVersion"
                    size="small"
                    text
                    @click="onRevert(v.version)"
                  >
                    回退到这一版
                  </el-button>
                </li>
              </ul>
            </StateBlock>
          </div>
        </div>
      </section>
    </div>

    <!-- 成品列收起后留一个竖标签 -->
    <button v-if="!sideOpen" class="wb__side-tab" type="button" @click="sideOpen = true">
      <span>成品</span>
      <span class="wb__side-badge">{{ store.doneCount }}/4</span>
    </button>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Close, Plus } from '@element-plus/icons-vue'
import LessonBar from '@/components/workbench/LessonBar.vue'
import ArtifactCard from '@/components/workbench/ArtifactCard.vue'
import LessonChat from '@/components/lesson/LessonChat.vue'
import GeneralChat from '@/components/assistant/GeneralChat.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { ARTIFACTS, useLessonStore } from '@/store/lesson'
import {
  contextPayload, assertContext,
  generateLessonPlan, generatePpt, generateAnimation, generateGame,
  reviseLessonPlan, listVersions, revertVersion
} from '@/api/lessonArtifacts'
import { notifyError, notifySuccess, notifyWarn } from '@/utils/notify'

/**
 * 备课工作台。
 *
 * 布局：对话是主舞台（占满剩余宽度），成品是可收起的辅列，左侧「我的备课」默认收起。
 * 旧版把对话夹在 200px 侧栏和成品区之间，对话反而是最窄的一列 —— 而这里
 * 教师 90% 的时间都在打字，本末倒置。
 */
const router = useRouter()
const store = useLessonStore()

/** 工作台产物类型 → 生成中心的路由参数（两者用的是同一套后端生成接口） */
const GENERATE_TYPE = {
  lesson_plan: 'lesson-plan',
  ppt: 'ppt',
  animation: 'animation',
  game: 'game'
}

const asideOpen = ref(false)
const sideOpen = ref(true)
const sideTab = ref('artifacts')
/** 课程信息条的展开状态：对话区的「设置这节课信息」也要求它，所以提到这里 */
const barOpen = ref(!store.topic.trim())
const activeKind = ref('lesson_plan')
const busy = ref(false)

/** 对话模式：当前备课（带课程语境） / 通用问答（不带） */
const chatMode = ref('lesson')
const generalConvId = ref(`c_${Date.now().toString(36)}`)

const chatModeHint = computed(() => (chatMode.value === 'lesson'
  ? '这句话会带上这一节备课的学科、年级与蓝图'
  : '不带任何备课语境，适合临时问概念、查资料'))

function onAdvancedGenerate() {
  router.push(`/generate/${GENERATE_TYPE[activeKind.value] || 'lesson-plan'}`)
}

function onNewTask() {
  store.resetLesson()
  asideOpen.value = false
}

const pptProgress = ref(0)
const pptStep = ref('')
const blueprintError = ref('')

const loadingCourses = ref(false)
const courseError = ref('')
const loadingVersions = ref(false)
const versionError = ref('')
const versions = ref([])
const currentVersion = ref(0)

const stages = computed(() => {
  const bp = store.teachingBlueprint
  return Array.isArray(bp?.stages) ? bp.stages : []
})
const totalMinutes = computed(() => store.teachingBlueprint?.totalMinutes
  || stages.value.reduce((n, s) => n + (Number(s.minutes ?? s.duration) || 0), 0))
const stageCount = computed(() => stages.value.length)

/** 四路共用同一份知识快照，所以取到第一份有内容的就够了 */
const citations = computed(() => {
  for (const a of ARTIFACTS) {
    const list = store.artifacts[a.id]?.citations
    if (Array.isArray(list) && list.length) return list.slice(0, 8)
  }
  return []
})

async function loadCourses() {
  loadingCourses.value = true
  courseError.value = ''
  try {
    await store.loadRecent(30)
  } catch (e) {
    courseError.value = e?.message || '备课列表加载失败'
  } finally {
    loadingCourses.value = false
  }
}

async function loadVersions() {
  if (!store.taskId) return
  loadingVersions.value = true
  versionError.value = ''
  try {
    const d = await listVersions(store.taskId, 'lesson_plan')
    versions.value = d.versions || []
    currentVersion.value = d.current || 0
  } catch (e) {
    versionError.value = e?.message || '版本历史加载失败'
  } finally {
    loadingVersions.value = false
  }
}

async function onSwitch(id) {
  const ok = await store.switchTask(id)
  if (!ok) notifyError('这门课没能加载出来，请重试')
  else asideOpen.value = false
}

// ---- 生成 -----------------------------------------------------------------

function markRunning(kind) {
  store.setArtifact(kind, { status: 'running', error: '', summary: '', at: Date.now() })
}

function markFailed(kind, err) {
  store.setArtifact(kind, {
    status: 'failed',
    error: err?.message || '生成失败',
    at: Date.now()
  })
  store.pushArtifact(kind)
  notifyError(err?.message || '生成失败')
}

async function onGenerate(kind) {
  if (busy.value) return
  try {
    assertContext(store)
  } catch (e) {
    notifyWarn(e.message)
    return
  }
  busy.value = true
  markRunning(kind)
  activeKind.value = kind
  const ctx = contextPayload(store)
  try {
    let patch
    if (kind === 'lesson_plan') {
      patch = await generateLessonPlan(ctx)
    } else if (kind === 'ppt') {
      pptProgress.value = 0
      pptStep.value = '正在创建任务'
      patch = await generatePpt(ctx, {
        themeColor: store.pptTheme,
        onProgress: (p, step) => { pptProgress.value = p; pptStep.value = step }
      })
    } else if (kind === 'animation') {
      patch = await generateAnimation(ctx, { minutes: store.animationMinutes })
    } else {
      patch = await generateGame(ctx, { gameType: store.gameType })
    }
    store.setArtifact(kind, { status: 'done', error: '', at: Date.now(), ...patch })
    store.pushArtifact(kind)
    notifySuccess('生成完成')
    if (kind === 'lesson_plan') loadVersions()
  } catch (e) {
    markFailed(kind, e)
  } finally {
    busy.value = false
    pptProgress.value = 0
    pptStep.value = ''
  }
}

async function onRevise({ instruction }) {
  if (!store.taskId) {
    notifyWarn('这门课还没有生成过教案，先生成一份再改')
    return
  }
  busy.value = true
  markRunning('lesson_plan')
  try {
    const ctx = contextPayload(store)
    const patch = await reviseLessonPlan({ lessonId: store.taskId, instruction, ctx })
    store.setArtifact('lesson_plan', { status: 'done', error: '', at: Date.now(), ...patch })
    store.pushArtifact('lesson_plan')
    notifySuccess('已按指令修改并记为新版本')
    loadVersions()
  } catch (e) {
    markFailed('lesson_plan', e)
  } finally {
    busy.value = false
  }
}

async function onRevert(version) {
  busy.value = true
  try {
    const ctx = contextPayload(store)
    const patch = await revertVersion({
      lessonId: store.taskId, kind: 'lesson_plan', version, ctx
    })
    store.setArtifact('lesson_plan', { status: 'done', error: '', at: Date.now(), ...patch })
    notifySuccess(`已回退到 v${version}`)
    loadVersions()
  } catch (e) {
    notifyError(e?.message || '回退失败')
  } finally {
    busy.value = false
  }
}

async function onBlueprint() {
  blueprintError.value = ''
  const r = await store.requestLessonBlueprint()
  if (!r.ok) {
    blueprintError.value = r.error || '蓝图没生成出来，可以直接生成，不影响结果'
    return
  }
  if (r.degraded) notifyWarn(r.error || '蓝图用了离线骨架，仍可直接使用')
}

onMounted(() => {
  loadCourses()
  loadVersions()
})

watch(() => store.taskId, () => loadVersions())
</script>

<style scoped>
.wb {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 560px;
  position: relative;
  background: var(--wb-bg);
}

.wb__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-3);
}

/* ---------------- 左侧「我的备课」---------------- */
/*
 * 「我的备课」恒为浮层，不占首屏的固定列宽。
 * 旧版它是 240px 的常驻列，加上成品列和顶部参数区，
 * 对话被挤到中间最窄的一列 —— 而教师 90% 的时间都在打字。
 */
.wb__aside {
  position: absolute;
  left: var(--sp-3);
  top: 56px;
  bottom: var(--sp-3);
  width: 260px;
  z-index: 12;
  display: none;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-md);
  padding: var(--sp-3);
  overflow-y: auto;
  box-shadow: var(--wb-shadow-lg);
}

.wb__aside.is-open { display: block; }

.wb__aside-ops {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}

.wb__aside-all {
  font-size: var(--fs-xs);
  color: var(--brand-text);
}

.wb__aside-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}

.course-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }

.course-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  padding: var(--sp-2);
  cursor: pointer;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px var(--sp-2);
  color: var(--wb-text);
}

.course-item:hover { background: var(--wb-hover); }

.course-item.is-active {
  background: var(--wb-active);
  border-color: var(--brand-border);
}

.course-item__topic { font-weight: 600; font-size: var(--fs-sm); }
.course-item__meta { grid-column: 1; font-size: var(--fs-xs); color: var(--wb-text-3); }

.course-item__badge {
  grid-row: 1 / span 2;
  align-self: center;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: var(--wb-surface-3);
  color: var(--wb-text-2);
}

/* ---------------- 中间对话 ---------------- */
.wb__chat {
  flex: 1 1 auto;
  min-width: 0;
  position: relative;
  display: flex;
}

.wb__chat-inner {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

/* 对话模式切换：一行，不喧宾夺主 */
.chat-mode {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.chat-mode__hint {
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  flex: 1 1 auto;
  min-width: 0;
}

.chat-mode__more {
  font-size: var(--fs-xs);
  color: var(--brand-text);
  flex: none;
}

.chat-pane { flex: 1 1 auto; min-height: 0; }

/* 次级入口：高级生成设置 */
.adv {
  margin-top: var(--sp-1);
  padding: var(--sp-3);
  border: 1px dashed var(--wb-border);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  align-items: flex-start;
}

.wb__aside-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--sp-2) 6px;
  border: 1px solid var(--wb-border);
  border-left: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--wb-surface);
  color: var(--wb-text-2);
  font-size: 11px;
  cursor: pointer;
}

/* ---------------- 右侧成品 ---------------- */
.wb__side {
  flex: 0 0 340px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--wb-surface);
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.wb__side-head {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--wb-border);
  padding-right: var(--sp-2);
}

.wb__tabs { flex: 1 1 auto; }
.wb__tabs :deep(.el-tabs__header) { margin: 0; }
.wb__tabs :deep(.el-tabs__nav-wrap)::after { display: none; }
.wb__tabs :deep(.el-tabs__item) { padding: 0 var(--sp-3); height: 44px; }

.wb__side-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-3);
}

.wb__side-close { display: none; }

/* 收起后的竖标签 */
.wb__side-tab {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) 6px;
  border: 1px solid var(--wb-border);
  border-right: none;
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  background: var(--wb-surface);
  color: var(--wb-text-2);
  font-size: var(--fs-xs);
  cursor: pointer;
}

.wb__side-badge {
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: var(--brand-soft-2);
  color: var(--brand-text);
  font-size: 11px;
}


/* ---------------- 蓝图 / 引用 / 版本 ---------------- */
.stages { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }

.stage {
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  background: var(--wb-surface-2);
}

.stage__row { display: flex; justify-content: space-between; gap: var(--sp-2); font-size: var(--fs-sm); }
.stage__desc { margin: 4px 0 0; font-size: var(--fs-xs); color: var(--wb-text-3); line-height: 1.6; }

.cite-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }

.cite {
  border-left: 2px solid var(--brand-border);
  padding-left: var(--sp-2);
}

.cite__src { font-size: var(--fs-sm); font-weight: 600; }
.cite__path { font-size: var(--fs-xs); color: var(--wb-text-3); margin-left: var(--sp-2); }
.cite__text { margin: 2px 0 0; font-size: var(--fs-xs); color: var(--wb-text-2); line-height: 1.6; }

.ver-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }

.ver {
  border: 1px solid var(--wb-border);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  background: var(--wb-surface-2);
}

.ver__row { display: flex; align-items: center; gap: var(--sp-2); }
.ver__note { margin: 2px 0 0; font-size: var(--fs-xs); color: var(--wb-text-3); }

.wb-note {
  margin: 0;
  font-size: var(--fs-xs);
  padding: var(--sp-2);
  border-radius: var(--radius-sm);
  background: var(--wb-surface-2);
  color: var(--wb-text-2);
}

.wb-note--warn {
  background: var(--wb-warn-bg);
  color: var(--wb-warn-text);
}

/* ---------------- 响应式 ---------------- */
@media (max-width: 1024px) {
  .wb__side {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 10;
    width: min(360px, 92vw);
    display: none;
    box-shadow: var(--wb-shadow-lg);
  }

  .wb__side.is-open { display: flex; }
  .wb__side-close { display: inline-flex; }
}
</style>
