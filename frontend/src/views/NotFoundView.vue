<template>
  <div class="wb-page">
    <EmptyState
      title="页面不存在"
      :description="`没有找到 ${path}。链接可能已失效，或者功能已经迁到别处。`"
      icon="Compass"
    >
      <template #action>
        <div class="wb-row">
          <el-button type="primary" @click="$router.push('/')">回到工作台</el-button>
          <el-button @click="$router.back()">返回上一页</el-button>
        </div>
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const path = computed(() => route.fullPath)
</script>
