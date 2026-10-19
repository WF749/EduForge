<template>
  <div class="wb-page">
    <PageHeader
      title="通用问答"
      description="不绑定任何备课任务，适合临时问概念、查资料、做通用讨论。要备一整节课请回工作台 —— 那里的对话知道你在备哪一门课。"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" @click="$router.push('/')">回工作台</el-button>
      </template>
    </PageHeader>

    <div class="layout">
      <aside class="wb-card wb-card-pad aside">
        <div class="wb-row wb-row-between" style="margin-bottom: var(--sp-2)">
          <b>会话</b>
          <el-button size="small" :icon="Plus" @click="onNew" aria-label="新建会话">新建</el-button>
        </div>

        <StateBlock :loading="loadingConvs" :empty="!conversations.length" empty-title="还没有会话" :rows="3" :retryable="false">
          <ul class="convs">
            <li v-for="c in conversations" :key="c.id">
              <button
                class="conv"
                type="button"
                :class="{ 'is-active': c.id === convId }"
                @click="convId = c.id"
              >
                <span class="conv__title wb-truncate">{{ c.title || '对话' }}</span>
                <el-icon
                  class="conv__del"
                  :size="14"
                  role="button"
                  aria-label="删除会话"
                  @click.stop="onRemove(c.id)"
                >
                  <Delete />
                </el-icon>
              </button>
            </li>
          </ul>
        </StateBlock>

        <p class="aside__foot">
          这是工作台之外的独立对话区。工作台里的对话会带上这一节课的学科、年级与蓝图，
          这里不会。
        </p>
      </aside>

      <div class="wb-card chat-shell">
        <GeneralChat :conv-id="convId" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ArrowLeft, Delete, Plus } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import GeneralChat from '@/components/assistant/GeneralChat.vue'
import { listConversations, deleteConversation } from '@/api/chat'

/**
 * 通用问答（次级入口）。
 *
 * 一级导航里已经没有它了 —— 入口在工作台对话区的「通用问答」模式，
 * 以及这里这个可直接访问的页面（`/assistant` 路由保留，旧链接不失效）。
 *
 * 对话实现放在 `components/assistant/GeneralChat.vue`，
 * 工作台切到「通用问答」时挂载的是**同一个组件**，不是复制一份聊天状态。
 */
const conversations = ref([])
const loadingConvs = ref(false)
const convId = ref('')

async function loadConversations() {
  loadingConvs.value = true
  try { conversations.value = await listConversations() } catch { conversations.value = [] } finally { loadingConvs.value = false }
}

function onNew() {
  convId.value = `c_${Date.now().toString(36)}`
}

async function onRemove(id) {
  await deleteConversation(id)
  if (convId.value === id) onNew()
  await loadConversations()
}

onMounted(async () => {
  await loadConversations()
  convId.value = conversations.value.length ? conversations.value[0].id : `c_${Date.now().toString(36)}`
})
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: var(--sp-4);
  align-items: stretch;
}

.aside { display: flex; flex-direction: column; }

.aside__foot {
  margin: var(--sp-3) 0 0;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--wb-border);
  font-size: var(--fs-xs);
  color: var(--wb-text-3);
  line-height: 1.7;
}

.convs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }

.conv {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--wb-text);
  font-size: var(--fs-sm);
  cursor: pointer;
  text-align: left;
}

.conv:hover { background: var(--wb-hover); }
.conv.is-active { background: var(--wb-active); border-color: var(--brand-border); }
.conv__title { flex: 1 1 auto; }
.conv__del { flex: 0 0 auto; color: var(--wb-text-3); }
.conv__del:hover { color: var(--wb-risk-text); }

.chat-shell {
  height: calc(100vh - 250px);
  min-height: 420px;
  overflow: hidden;
}

@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .aside { display: none; }
  .chat-shell { height: calc(100vh - 200px); }
}
</style>
