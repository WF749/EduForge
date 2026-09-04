<template>
  <div class="ppt-preview" :class="{ 'fullscreen': isFullscreen }">
    <!-- 工具栏 -->
    <div class="preview-toolbar">
      <div class="page-info">
        <span>第 {{ currentPage }} 页</span>
        <span class="separator">/</span>
        <span>共 {{ pages.length || 1 }} 页</span>
      </div>
      
      <div class="toolbar-actions">
        <el-button-group size="small">
          <el-button @click="prevPage" :disabled="currentPage <= 1">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <el-button @click="nextPage" :disabled="currentPage >= pages.length">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </el-button-group>
        
        <el-button size="small" @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </el-button>
        
        <el-slider 
          v-model="scale" 
          :min="50" 
          :max="150" 
          :step="10"
          :show-tooltip="false"
          class="scale-slider"
        />
        <span class="scale-label">{{ scale }}%</span>
      </div>
    </div>
    
    <!-- 预览区域 -->
    <div class="preview-container" ref="containerRef">
      <div 
        class="slide-wrapper" 
        :style="{ 
          transform: `scale(${scale / 100})`,
          backgroundColor: currentSlideData?.theme?.primary_color || '#3498db'
        }"
      >
        <!-- 封面页 -->
        <div v-if="currentSlideData?.page_type === 'cover'" class="slide cover-slide">
          <div class="cover-main">
            <h1 class="cover-title">{{ currentSlideData.main_title }}</h1>
            <p class="cover-subtitle">{{ currentSlideData.subtitle }}</p>
          </div>
          <div class="cover-footer">
            <span>{{ currentSlideData.instructor_info }}</span>
            <span>{{ currentSlideData.date }}</span>
          </div>
        </div>
        
        <!-- 目录页 -->
        <div v-else-if="currentSlideData?.page_type === 'toc'" class="slide toc-slide">
          <div class="slide-header-bar" :style="{ backgroundColor: currentSlideData?.theme?.primary_color }"></div>
          <h2 class="slide-title">{{ currentSlideData.core_topic }}</h2>
          <div class="toc-list">
            <div 
              v-for="(item, index) in currentSlideData.toc_items" 
              :key="index"
              class="toc-item"
            >
              <span class="toc-num">{{ index + 1 }}</span>
              <span class="toc-text">{{ item }}</span>
            </div>
          </div>
        </div>
        
        <!-- 知识点页 -->
        <div v-else-if="currentSlideData?.page_type === 'knowledge'" class="slide content-slide">
          <div class="slide-header-bar" :style="{ backgroundColor: currentSlideData?.theme?.primary_color }"></div>
          <div class="slide-left-bar" :style="{ backgroundColor: currentSlideData?.theme?.secondary_color }"></div>
          <h2 class="slide-title">{{ currentSlideData.core_topic }}</h2>
          <ul class="key-points">
            <li v-for="(point, index) in currentSlideData.key_points" :key="index">
              <span class="point-bullet" :style="{ backgroundColor: currentSlideData?.theme?.accent_color || '#2ecc71' }"></span>
              <span class="point-text">{{ point }}</span>
            </li>
          </ul>
          <div v-if="currentSlideData.case_study" class="case-study">
            <h4>📋 案例分析</h4>
            <p>{{ currentSlideData.case_study }}</p>
          </div>
        </div>
        
        <!-- 习题页 -->
        <div v-else-if="currentSlideData?.page_type === 'exercise'" class="slide exercise-slide">
          <div class="slide-header-bar" :style="{ backgroundColor: currentSlideData?.theme?.accent_color || '#2ecc71' }"></div>
          <h2 class="slide-title">{{ currentSlideData.core_topic }}</h2>
          <div class="exercise-list">
            <div v-for="(exercise, eIndex) in currentSlideData.exercises" :key="eIndex" class="exercise-item">
              <p class="exercise-question">{{ exercise.question }}</p>
              <div class="exercise-options">
                <p v-for="(opt, oIndex) in exercise.options" :key="oIndex" class="exercise-option">
                  {{ opt }}
                </p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 总结页 -->
        <div v-else-if="currentSlideData?.page_type === 'summary'" class="slide summary-slide">
          <h2 class="slide-title">{{ currentSlideData.core_topic }}</h2>
          <ul class="summary-list">
            <li v-for="(item, index) in currentSlideData.knowledge_review" :key="index">
              <span class="summary-check">✓</span>
              <span>{{ item }}</span>
            </li>
          </ul>
          <div v-if="currentSlideData.homework" class="homework">
            📝 课后作业: {{ currentSlideData.homework }}
          </div>
        </div>
        
        <!-- 默认页 -->
        <div v-else class="slide default-slide">
          <div class="slide-header-bar" :style="{ backgroundColor: currentSlideData?.theme?.primary_color }"></div>
          <h2 class="slide-title">{{ currentSlideData?.core_topic || '加载中...' }}</h2>
          <ul class="key-points" v-if="currentSlideData?.key_points">
            <li v-for="(point, index) in currentSlideData.key_points" :key="index">
              <span class="point-bullet" :style="{ backgroundColor: '#2ecc71' }"></span>
              <span class="point-text">{{ point }}</span>
            </li>
          </ul>
          <div v-else class="loading-placeholder">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>正在生成...</span>
          </div>
        </div>
        
        <!-- 页码 -->
        <div class="page-number">{{ currentPage }} / {{ pages.length || 1 }}</div>
      </div>
    </div>
    
    <!-- 缩略图列表 -->
    <div class="thumbnail-list" v-if="pages.length > 1">
      <div 
        v-for="(page, index) in pages" 
        :key="index"
        class="thumbnail-item"
        :class="{ active: currentPage === index + 1 }"
        @click="goToPage(index + 1)"
      >
        <div class="thumbnail-preview" :style="getThumbnailStyle(page)">
          <span v-if="!page" class="thumb-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
          </span>
          <span v-else class="thumb-title">{{ page.core_topic?.slice(0, 10) || '页面' + (index + 1) }}</span>
        </div>
        <span class="thumb-number">{{ index + 1 }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ArrowLeft, ArrowRight, FullScreen, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  // 页面数据数组
  pages: {
    type: Array,
    default: () => []
  },
  // 当前页码
  currentPage: {
    type: Number,
    default: 1
  },
  // 是否全屏
  fullscreen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:currentPage', 'update:fullscreen'])

// 本地状态
const scale = ref(80)
const containerRef = ref(null)
const isFullscreen = ref(false)

// 计算当前页数据
const currentSlideData = computed(() => {
  const idx = props.currentPage - 1
  return props.pages[idx] || null
})

// 上一页
function prevPage() {
  if (props.currentPage > 1) {
    emit('update:currentPage', props.currentPage - 1)
  }
}

// 下一页
function nextPage() {
  if (props.currentPage < props.pages.length) {
    emit('update:currentPage', props.currentPage + 1)
  }
}

// 跳转到指定页
function goToPage(page) {
  emit('update:currentPage', page)
}

// 切换全屏
function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  emit('update:fullscreen', isFullscreen.value)
}

// 获取缩略图样式
function getThumbnailStyle(page) {
  if (!page) return {}
  
  return {
    backgroundColor: page.theme?.primary_color || '#3498db'
  }
}

// 键盘导航
function handleKeydown(e) {
  if (e.key === 'ArrowLeft') {
    prevPage()
  } else if (e.key === 'ArrowRight') {
    nextPage()
  } else if (e.key === 'Escape' && isFullscreen.value) {
    toggleFullscreen()
  }
}

// 监听键盘事件
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', handleKeydown)
}
</script>

<style scoped>
.ppt-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1f4e;
  border-radius: 8px;
  overflow: hidden;
}

.ppt-preview.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  border-radius: 0;
}

/* 工具栏 */
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(26, 31, 78, 0.95);
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
}

.page-info {
  color: #b0b8c4;
  font-size: 14px;
}

.page-info .separator {
  margin: 0 8px;
  color: #5a6578;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.scale-slider {
  width: 100px;
}

.scale-label {
  color: #b0b8c4;
  font-size: 12px;
  min-width: 40px;
}

/* 预览容器 */
.preview-container {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  overflow: auto;
}

.slide-wrapper {
  width: 960px;
  height: 540px;
  transform-origin: center center;
  transition: transform 0.3s ease;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

/* 幻灯片基础样式 */
.slide {
  width: 100%;
  height: 100%;
  padding: 40px;
  background: white;
  color: #2c3e50;
  position: relative;
  display: flex;
  flex-direction: column;
}

.slide-header-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 8px;
}

.slide-left-bar {
  position: absolute;
  top: 8px;
  left: 0;
  bottom: 0;
  width: 6px;
}

.slide-title {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 24px;
  color: #2c3e50;
  font-family: '微软雅黑', Arial, sans-serif;
}

/* 封面页 */
.cover-slide {
  background: linear-gradient(135deg, #3498db, #2980b9);
  color: white;
  text-align: center;
  justify-content: center;
  align-items: center;
}

.cover-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.cover-title {
  font-size: 56px;
  font-weight: bold;
  margin-bottom: 20px;
  font-family: '微软雅黑', Arial, sans-serif;
}

.cover-subtitle {
  font-size: 24px;
  opacity: 0.9;
}

.cover-footer {
  display: flex;
  justify-content: center;
  gap: 40px;
  font-size: 18px;
  opacity: 0.8;
}

/* 目录页 */
.toc-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 20px;
}

.toc-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toc-num {
  width: 36px;
  height: 36px;
  background: #3498db;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
}

.toc-text {
  font-size: 22px;
  font-family: '微软雅黑', Arial, sans-serif;
}

/* 知识点页 */
.key-points {
  list-style: none;
  padding: 0;
  margin: 0;
}

.key-points li {
  display: flex;
  align-items:flex-start;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 20px;
  line-height: 1.6;
}

.point-bullet {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-top: 8px;
  flex-shrink: 0;
}

.point-text {
  font-family: '微软雅黑', Arial, sans-serif;
}

.case-study {
  margin-top: 24px;
  padding: 16px;
  background: rgba(52, 152, 219, 0.1);
  border-radius: 8px;
  font-size: 16px;
}

.case-study h4 {
  color: #3498db;
  margin-bottom: 8px;
}

/* 习题页 */
.exercise-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.exercise-question {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 12px;
}

.exercise-option {
  font-size: 18px;
  margin: 8px 0;
  padding-left: 16px;
}

/* 总结页 */
.summary-slide {
  background: #3498db;
  color: white;
}

.summary-list {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.summary-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 22px;
}

.summary-check {
  width: 32px;
  height: 32px;
  background: #2ecc71;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.homework {
  margin-top: auto;
  font-size: 18px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 8px;
}

/* 加载占位 */
.loading-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #7f8c8d;
}

/* 页码 */
.page-number {
  position: absolute;
  bottom: 12px;
  right: 20px;
  font-size: 14px;
  color: #7f8c8d;
}

/* 缩略图列表 */
.thumbnail-list {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(26, 31, 78, 0.95);
  border-top: 1px solid rgba(0, 200, 255, 0.2);
  overflow-x: auto;
}

.thumbnail-item {
  flex-shrink: 0;
  cursor: pointer;
  text-align: center;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.thumbnail-item:hover,
.thumbnail-item.active {
  opacity: 1;
}

.thumbnail-item.active .thumbnail-preview {
  border-color: #00c8ff;
  box-shadow: 0 0 8px rgba(0, 200, 255, 0.5);
}

.thumbnail-preview {
  width: 120px;
  height: 68px;
  border-radius: 4px;
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  font-size: 10px;
  color: white;
  background: #3498db;
}

.thumb-title {
  padding: 4px;
  text-align: center;
  word-break: break-all;
}

.thumb-loading {
  color: white;
}

.thumb-number {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #7f8c8d;
}

/* Element Plus 图标 */
:deep(.el-icon) {
  vertical-align: middle;
}
</style>
