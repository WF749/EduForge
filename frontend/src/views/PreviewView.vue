<template>
  <div class="preview-view page-container">
    <div class="preview-content">
      <!-- 头部 -->
      <div class="preview-header">
        <div class="header-left">
          <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
          <h1>PPT内容预览</h1>
        </div>
        <div class="header-right">
          <el-button v-if="taskStatus === 'completed' && hasPptxFile" type="primary" @click="downloadFile('pptx')">
            <el-icon><Download /></el-icon>
            下载PPT
          </el-button>
          <el-button v-if="taskStatus === 'completed' && hasDocxFile" @click="downloadFile('docx')">
            <el-icon><Download /></el-icon>
            下载教案
          </el-button>
          <el-button v-if="taskStatus === 'completed' && hasAnimation" @click="downloadFile('animation')">
            <el-icon><VideoCamera /></el-icon>
            下载动画
          </el-button>
          <el-button v-if="taskStatus === 'completed' && hasGame" @click="downloadFile('game')">
            <el-icon><Connection /></el-icon>
            下载游戏
          </el-button>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>正在加载课件...</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-state">
        <el-icon><WarningFilled /></el-icon>
        <p>{{ error }}</p>
        <el-button @click="loadPreview">重试</el-button>
      </div>

      <!-- 预览内容 -->
      <div v-else-if="taskStatus === 'completed'" class="preview-main">
        <!-- 幻灯片列表 -->
        <aside class="slides-list glass-card">
          <h3>幻灯片列表</h3>
          <div class="slides-nav">
            <div 
              v-for="(slide, index) in slides" 
              :key="slide.slide_id"
              class="slide-thumb"
              :class="{ active: currentSlideIndex === index }"
              @click="currentSlideIndex = index"
            >
              <span class="slide-number">{{ index + 1 }}</span>
              <span class="slide-title">{{ slide.title || '无标题' }}</span>
            </div>
          </div>
        </aside>

        <!-- 当前幻灯片预览 -->
        <main class="slide-preview glass-card">
          <div class="preview-container">
            <div class="preview-slide" :key="currentSlideIndex" :class="getSlideClass(currentSlide.type)">
  <div class="slide-type-badge">{{ getSlideTypeName(currentSlide.type) }}</div>
  <h2 class="slide-title" :class="{ 'cover-title': currentSlide.type === 'cover' }">{{ currentSlide.title }}</h2>
  <div class="slide-content" :class="{ 'cover-content': currentSlide.type === 'cover' }" v-html="formatContent(currentSlide.content)"></div>
</div>
          </div>

          <!-- 导航按钮 -->
          <div class="preview-nav">
            <el-button 
              :disabled="currentSlideIndex === 0" 
              @click="prevSlide"
            >
              <el-icon><ArrowLeft /></el-icon>
              上一页
            </el-button>
            <span class="slide-indicator">
              {{ currentSlideIndex + 1 }} / {{ slides.length }}
            </span>
            <el-button 
              :disabled="currentSlideIndex === slides.length - 1" 
              @click="nextSlide"
            >
              下一页
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </main>

        <!-- 附加内容 -->
        <aside class="extras-panel glass-card">
          <!-- 动画创意 -->
          <div v-if="animationIdeas?.length > 0" class="extra-section">
            <h4>
              <el-icon><VideoCamera /></el-icon>
              动画创意
            </h4>
            <div class="animation-list">
              <div 
                v-for="(idea, index) in animationIdeas" 
                :key="index"
                class="animation-item"
              >
                <div class="animation-point">{{ idea.point }}</div>
                <div class="animation-type">{{ idea.animation_type }}</div>
                <div class="animation-desc">{{ idea.description }}</div>
              </div>
            </div>
          </div>

          <!-- 互动游戏 -->
          <div v-if="gameContent" class="extra-section">
            <h4>
              <el-icon><Connection /></el-icon>
              互动游戏
            </h4>
            <div class="game-card">
              <div class="game-name">{{ gameContent.game_name }}</div>
              <div class="game-type">{{ gameContent.game_type }}</div>
              <p class="game-desc">{{ gameContent.description }}</p>
              <el-button 
                type="primary" 
                size="small" 
                @click="downloadFile('html')"
              >
                下载游戏
              </el-button>
            </div>
          </div>

          <!-- 修改建议 -->
          <div class="extra-section">
            <h4>
              <el-icon><ChatDotRound /></el-icon>
              修改建议
            </h4>
            
            <!-- 修改类型选择 -->
            <el-select v-model="modificationType" placeholder="选择修改类型" style="width: 100%; margin-bottom: 12px;">
              <el-option label="调整内容" value="content" />
              <el-option label="调整顺序" value="order" />
              <el-option label="添加内容" value="add" />
              <el-option label="删除内容" value="delete" />
              <el-option label="修改风格" value="style" />
              <el-option label="其他修改" value="other" />
            </el-select>
            
            <!-- 具体修改内容 -->
            <el-input
              v-model="modificationText"
              type="textarea"
              :rows="3"
              placeholder="详细描述修改要求，如：调整第3页的内容顺序，简化第5页的文字，增加案例说明"
            />
            
            <!-- 目标幻灯片 -->
            <el-select v-model="targetSlideIndex" placeholder="选择目标幻灯片" style="width: 100%; margin-top: 12px; margin-bottom: 12px;">
              <el-option 
                v-for="(slide, index) in slides" 
                :key="index" 
                :label="`第${index + 1}页: ${slide.title || '无标题'}`" 
                :value="index" 
              />
            </el-select>
            
            <el-button 
              type="primary" 
              :loading="modifying"
              @click="submitModification"
              style="width: 100%;"
            >
              提交修改
            </el-button>
          </div>
          
          <!-- 版本历史 -->
          <div class="extra-section">
            <h4>
              <el-icon><Clock /></el-icon>
              版本历史
            </h4>
            <div class="version-list">
              <div 
                v-for="(version, index) in versionHistory" 
                :key="index"
                class="version-item"
                :class="{ active: index === 0 }"
              >
                <div class="version-number">版本 {{ version.version || (versionHistory.length - index) }}</div>
                <div class="version-date">{{ version.date }}</div>
                <div class="version-desc">{{ version.description }}</div>
                <el-button 
                  type="text" 
                  size="small" 
                  @click="revertToVersion(index)"
                  :disabled="index === 0 || !version.version"
                >
                  恢复
                </el-button>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <!-- 生成中状态 -->
      <div v-else-if="!['completed', 'failed'].includes(taskStatus)" class="generating-state">
        <div class="generating-animation">
          <div class="pulse-ring"></div>
          <div class="pulse-ring delay"></div>
          <div class="pulse-ring delay2"></div>
        </div>
        <h2>正在生成课件...</h2>
        <p>{{ progressMessage }}</p>
        <el-progress 
          :percentage="progress" 
          :stroke-width="10"
          :color="progressColors"
          style="width: 400px; margin-top: 24px;"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/store/app'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Download, Loading, 
  WarningFilled, VideoCamera, Connection, ChatDotRound, Clock
} from '@element-plus/icons-vue'
import axios from 'axios'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { installDataFlowInterceptor } from '@/api/dataFlow'
import { renderMathInText } from '@/utils/mathRender'
import 'katex/dist/katex.min.css'

const pptApi = axios.create({
  baseURL: resolveApiBaseURL(),
  timeout: 120000
})

installDataFlowInterceptor(pptApi)

const route = useRoute()
const router = useRouter()
const store = useAppStore()

// 状态
const loading = ref(true)
const error = ref(null)
const taskStatus = ref('pending')
const progress = ref(0)
const progressMessage = ref('准备中...')
const currentSlideIndex = ref(0)
const modificationText = ref('')
const modificationType = ref('')
const targetSlideIndex = ref(null)
const modifying = ref(false)

// 版本历史
const versionHistory = ref([
  {
    date: new Date().toLocaleString(),
    description: '初始版本'
  }
])

// 课件数据
const title = ref('')
const subtitle = ref('')
const slides = ref([])
const animationIdeas = ref([])
const gameContent = ref(null)
const animationResult = ref(null)
const gameResult = ref(null)
const coursewareData = ref(null)

// 计算属性
const hasAnimation = computed(() => {
  return animationResult.value || (animationIdeas.value && animationIdeas.value.length > 0)
})

const hasGame = computed(() => {
  return gameResult.value || gameContent.value
})

const hasDocxFile = computed(() => !!coursewareData.value?.files?.docx)
const hasPptxFile = computed(() => {
  const data = coursewareData.value || {}
  return !!(data.files?.pptx || data.pptx_path)
})

// 进度颜色
const progressColors = [
  { color: '#00c8ff', percentage: 30 },
  { color: '#00ff88', percentage: 70 },
  { color: '#7c3aed', percentage: 100 }
]

// 当前幻灯片
const currentSlide = computed(() => slides.value[currentSlideIndex.value] || {})

// 获取幻灯片类型名称
function getSlideTypeName(type) {
  const names = {
    cover: '封面',
    title: '标题',
    content: '内容',
    summary: '总结',
    toc: '目录',
    knowledge: '知识点',
    exercise: '互动练习'
  }
  return names[type] || '内容'
}

// 获取幻灯片类名
function getSlideClass(type) {
  const classes = {
    cover: 'cover-slide',
    toc: 'toc-slide',
    knowledge: 'knowledge-slide',
    exercise: 'exercise-slide',
    summary: 'summary-slide'
  }
  return classes[type] || 'content-slide'
}

// 格式化内容（支持数学公式渲染）
function formatContent(content) {
  if (!content) return ''
  let s = renderMathInText(content)
  s = s.replace(/\n/g, '<br>')
  s = s.replace(/- /g, '&bull; ')
  return s
}

// 加载预览
async function loadPreview() {
  loading.value = true
  error.value = null

  try {
    // 检查URL查询参数中是否包含课件数据
    if (route.query.courseware) {
      try {
        console.log('开始解析课件数据...')
        console.log('URL query:', route.query)
        
        if (!route.query.courseware) {
          throw new Error('没有找到课件数据')
        }
        
        const courseware = JSON.parse(route.query.courseware)
        console.log('解析后的courseware:', courseware)
        
        // 解析PPT内容
        if (courseware.ppt_content) {
          console.log('找到ppt_content:', courseware.ppt_content)
          // 改进的解析逻辑
          const pptContent = courseware.ppt_content
          const parsedSlides = []
          
          // 尝试解析不同格式的PPT内容
          // 格式3: 新的JSON格式（包含detailed_content）
          if (typeof pptContent === 'object' && pptContent.detailed_content) {
            console.log('使用detailed_content解析...')
            const detailedContent = pptContent.detailed_content
            console.log('detailed_content长度:', detailedContent.length)
            
            for (let i = 0; i < detailedContent.length; i++) {
              const slide = detailedContent[i]
              console.log('处理幻灯片', i + 1, ':', slide.core_topic || slide.title || '无标题')
              let slideContent = ''
              
              // 构建幻灯片内容
              if (slide.main_title) {
                slideContent += slide.main_title + '\n'
              }
              if (slide.subtitle) {
                slideContent += slide.subtitle + '\n'
              }
              if (slide.instructor_info) {
                slideContent += slide.instructor_info + '\n'
              }
              if (slide.key_points && slide.key_points.length > 0) {
                slideContent += '\n重点内容:\n'
                slide.key_points.forEach(point => {
                  slideContent += `- ${point}\n`
                })
              }
              if (slide.toc_items && slide.toc_items.length > 0) {
                slideContent += '\n目录:\n'
                slide.toc_items.forEach(item => {
                  slideContent += `- ${item}\n`
                })
              }
              if (slide.knowledge_review && slide.knowledge_review.length > 0) {
                slideContent += '\n知识回顾:\n'
                slide.knowledge_review.forEach(item => {
                  slideContent += `- ${item}\n`
                })
              }
              if (slide.goals_achievement) {
                slideContent += '\n学习目标达成:\n' + slide.goals_achievement + '\n'
              }
              if (slide.homework) {
                slideContent += '\n作业:\n' + slide.homework + '\n'
              }
              if (slide.exercises && slide.exercises.length > 0) {
                slideContent += '\n互动练习:\n'
                slide.exercises.forEach((exercise, idx) => {
                  slideContent += `${idx + 1}. ${exercise.question || '问题'}\n`
                  if (exercise.options && exercise.options.length > 0) {
                    exercise.options.forEach((option, optIdx) => {
                      slideContent += `   ${String.fromCharCode(65 + optIdx)}. ${option}\n`
                    })
                  }
                  if (exercise.answer) {
                    slideContent += `   答案: ${exercise.answer}\n`
                  }
                  if (exercise.explanation) {
                    slideContent += `   解析: ${exercise.explanation}\n`
                  }
                })
              }
              // 处理其他可能的内容字段
              if (slide.content) {
                slideContent += '\n' + slide.content + '\n'
              }
              if (slide.body) {
                slideContent += '\n' + slide.body + '\n'
              }
              
              parsedSlides.push({
                slide_id: `slide_${i}`,
                slide_number: i + 1,
                type: slide.page_type || slide.type || (i === 0 ? 'cover' : 'content'),
                title: slide.core_topic || slide.main_title || slide.title || `幻灯片 ${i + 1}`,
                content: slideContent.trim() || '无内容'
              })
            }
          }
          // 格式1: 按页面标题分隔
          else if (typeof pptContent === 'string' && pptContent.includes('页面标题：')) {
            console.log('使用页面标题分隔解析...')
            const slideSections = pptContent.split('页面标题：')
            for (let i = 1; i < slideSections.length; i++) {
              const section = slideSections[i]
              const lines = section.split('\n')
              const slideTitle = lines[0]?.trim() || '无标题'
              let slideContent = ''
              
              for (let j = 1; j < lines.length; j++) {
                const line = lines[j]
                if (line.trim()) {
                  slideContent += line + '\n'
                }
              }
              
              parsedSlides.push({
                slide_id: `slide_${i-1}`,
                slide_number: i,
                type: i === 1 ? 'cover' : 'content',
                title: slideTitle,
                content: slideContent.trim() || '无内容'
              })
            }
          } 
          // 格式2: 按章节分隔
          else if (typeof pptContent === 'string' && pptContent.includes('\n\n')) {
            console.log('使用章节分隔解析...')
            const slideSections = pptContent.split('\n\n')
            for (let i = 0; i < slideSections.length; i++) {
              const section = slideSections[i].trim()
              if (section) {
                const lines = section.split('\n')
                const slideTitle = lines[0] || '无标题'
                let slideContent = ''
                
                for (let j = 1; j < lines.length; j++) {
                  slideContent += lines[j] + '\n'
                }
                
                parsedSlides.push({
                  slide_id: `slide_${i}`,
                  slide_number: i + 1,
                  type: i === 0 ? 'cover' : 'content',
                  title: slideTitle,
                  content: slideContent.trim() || '无内容'
                })
              }
            }
          }
          // 格式4: 直接是幻灯片数组
          else if (Array.isArray(pptContent)) {
            console.log('使用幻灯片数组解析...')
            pptContent.forEach((slide, i) => {
              parsedSlides.push({
                slide_id: `slide_${i}`,
                slide_number: i + 1,
                type: slide.type || (i === 0 ? 'cover' : 'content'),
                title: slide.title || slide.core_topic || `幻灯片 ${i + 1}`,
                content: slide.content || slide.body || '无内容'
              })
            })
          }
          // 格式5: 简化的JSON格式
          else if (typeof pptContent === 'object') {
            console.log('使用简化JSON格式解析...')
            // 尝试从对象中提取幻灯片信息
            if (pptContent.slides) {
              pptContent.slides.forEach((slide, i) => {
                parsedSlides.push({
                  slide_id: `slide_${i}`,
                  slide_number: i + 1,
                  type: slide.type || (i === 0 ? 'cover' : 'content'),
                  title: slide.title || slide.core_topic || `幻灯片 ${i + 1}`,
                  content: slide.content || slide.body || '无内容'
                })
              })
            } else {
              throw new Error('PPT内容中没有可展示的幻灯片')
            }
          }
          else {
            throw new Error('PPT内容格式无法解析')
          }

          if (parsedSlides.length === 0) {
            throw new Error('PPT内容中没有可展示的幻灯片')
          }
          
          console.log('解析完成，共', parsedSlides.length, '张幻灯片')
          slides.value = parsedSlides
          // 从多个可能的位置获取标题
          title.value = courseware.ppt_content.metadata?.topic || courseware.ppt_content.topic || courseware.topic || '课件'
          // 从多个可能的位置获取受众信息
          const audience = courseware.ppt_content.metadata?.audience || courseware.ppt_content.audience || courseware.audience || '未知受众'
          // 从多个可能的位置获取学科信息
          const subject = courseware.ppt_content.metadata?.subject || courseware.ppt_content.subject || courseware.subject || '通用'
          subtitle.value = `面向${audience}的${subject}课程`
          
          // 解析动画创意
          if (courseware.animation_ideas) {
            const aniText = typeof courseware.animation_ideas === 'string' ? courseware.animation_ideas : JSON.stringify(courseware.animation_ideas)
            animationIdeas.value = [{
              point: '动画创意',
              animation_type: '教育动画',
              description: aniText.substring(0, 200) + (aniText.length > 200 ? '...' : '')
            }]
          }

          // 解析动画结果（新版）
          if (courseware.animation_result) {
            animationResult.value = courseware.animation_result
          }

          // 解析互动游戏
          if (courseware.interactive_games) {
            const gameText = typeof courseware.interactive_games === 'string' ? courseware.interactive_games : JSON.stringify(courseware.interactive_games)
            gameContent.value = {
              game_name: '互动游戏',
              game_type: '教育游戏',
              description: gameText.substring(0, 200) + (gameText.length > 200 ? '...' : '')
            }
          }

          // 解析游戏结果（新版）
          if (courseware.game_result) {
            gameResult.value = courseware.game_result
          }

          // 保存课件数据供下载使用
          coursewareData.value = courseware

          taskStatus.value = 'completed'
          console.log('解析完成，状态设置为completed')
        } else {
          if (courseware.task_id) {
            coursewareData.value = courseware
            taskStatus.value = 'pending'
            progressMessage.value = '正在生成课件，请稍候…'
            slides.value = []
            title.value = '生成中'
            subtitle.value = '请等待后端完成 PPT 任务'
            console.log('仅有 task_id，等待轮询 /ppt/status')
          } else {
            throw new Error('没有找到可预览的PPT内容')
          }
        }
      } catch (e) {
        console.error('解析课件数据失败:', e)
        console.error('错误堆栈:', e.stack)
        error.value = '解析课件数据失败: ' + e.message
      }
    } else {
      // 从后端获取预览数据
      const response = await pptApi.get(`/ppt/preview/${route.params.taskId}`)
      const pptContent = response.data?.ppt_data
      if (!response.data?.success || !pptContent) throw new Error('没有找到该PPT任务')
      coursewareData.value = { task_id: route.params.taskId, ppt_content: pptContent }
      const metadata = pptContent.metadata || {}
      title.value = metadata.topic || '课件'
      subtitle.value = `面向${metadata.audience || '学生'}的${metadata.subject || '通用'}课程`
      const directSlides = pptContent.detailed_content || pptContent.slides || []
      if (!Array.isArray(directSlides) || directSlides.length === 0) {
        throw new Error('PPT内容中没有可展示的幻灯片')
      }
      updateSlidesFromContent(directSlides)
      taskStatus.value = 'completed'
    }
  } catch (e) {
    error.value = '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// 加载任务状态
async function loadTaskStatus() {
  try {
    const status = await store.getGenerationStatus(route.params.taskId)
    
    if (status) {
      taskStatus.value = status.status
      progress.value = status.progress || 0
      progressMessage.value = status.current_step || status.message || '处理中...'

      if (status.result) {
        if (status.result.animation_ideas) {
          animationIdeas.value = status.result.animation_ideas
        }
        if (status.result.game_content) {
          gameContent.value = status.result.game_content
        }
        const ppt = status.result.ppt_content
        if (ppt?.detailed_content?.length) {
          title.value = ppt.title || status.result.topic || ''
          updateSlidesFromContent(ppt.detailed_content)
        } else if (ppt?.slides?.length) {
          title.value = ppt.title || ''
          slides.value = ppt.slides.map((s, i) => ({
            ...s,
            slide_id: `slide_${i}`,
            slide_number: i + 1
          }))
        }
        if (status.status === 'completed' && status.result) {
          coursewareData.value = {
            ...status.result,
            task_id: status.result.task_id || route.params.taskId
          }
        }
      }
    }
  } catch (e) {
    console.error('获取状态失败:', e)
  }
}

// 下载文件
async function downloadFile(format) {
  const cwData = coursewareData.value || route.query.courseware
  if (!cwData) {
    ElMessage.error('没有找到课件数据')
    return
  }

  try {
    const courseware = typeof cwData === 'string' ? JSON.parse(cwData) : cwData

    // 处理动画下载
    if (format === 'animation') {
      if (animationResult.value?.task_id) {
        window.open(`${resolveApiBaseURL()}/courseware/animation/download?task_id=${encodeURIComponent(animationResult.value.task_id)}`, '_blank')
        ElMessage.success('动画文件下载中...')
      } else if (animationResult.value?.html_path) {
        window.open(`${resolveApiBaseURL()}/courseware/animation/download?task_dir=${encodeURIComponent(animationResult.value.task_dir)}`, '_blank')
        ElMessage.success('动画文件下载中...')
      } else {
        ElMessage.warning('动画文件尚未生成')
      }
      return
    }

    // 处理游戏下载
    if (format === 'game') {
      if (gameResult.value?.task_id) {
        window.open(`${resolveApiBaseURL()}/courseware/game/download?task_id=${encodeURIComponent(gameResult.value.task_id)}`, '_blank')
        ElMessage.success('游戏文件下载中...')
      } else if (gameResult.value?.html_path) {
        window.open(`${resolveApiBaseURL()}/courseware/game/download?task_dir=${encodeURIComponent(gameResult.value.task_dir)}`, '_blank')
        ElMessage.success('游戏文件下载中...')
      } else {
        ElMessage.warning('游戏文件尚未生成')
      }
      return
    }

    // 处理PPT下载：使用真实任务 ID，避免让浏览器提交本机文件路径
    if (format === 'pptx') {
      const taskId = courseware.task_id || route.params.taskId
      if (taskId) {
        window.open(`${resolveApiBaseURL()}/ppt/download/${encodeURIComponent(taskId)}`, '_blank')
        ElMessage.success('PPT文件下载中...')
        return
      }
    }
    
    // 处理DOCX下载：优先使用教案导出接口返回的精确地址
    if (format === 'docx') {
      if (courseware.files?.docx && /^(https?:|\/)/.test(courseware.files.docx)) {
        window.open(courseware.files.docx, '_blank')
        ElMessage.success('教案文件下载中...')
        return
      } else if (courseware.task_dir) {
        const topicParam = encodeURIComponent(courseware.topic || '')
        const taskDirParam = encodeURIComponent(courseware.task_dir)
        window.open(`/api/courseware/download/docx?task_dir=${taskDirParam}&topic=${topicParam}`, '_blank')
        ElMessage.success('教案文件下载中...')
        return
      } else if (courseware.files && courseware.files[format]) {
        await store.downloadCoursewareFile(format, courseware.task_dir, courseware.topic)
        ElMessage.success('文件下载中...')
        return
      }
    }

    ElMessage.warning(`当前任务没有可下载的${format === 'pptx' ? 'PPTX' : 'DOCX'}文件`)
  } catch (e) {
    console.error('下载文件失败:', e)
    ElMessage.error('下载文件失败')
  }
}

// 生成幻灯片HTML
function generateSlidesHTML(courseware) {
  const slides = []
  
  // 解析PPT内容
  if (courseware.ppt_content) {
    const pptContent = courseware.ppt_content
    
    // 尝试解析不同格式的PPT内容
    if (typeof pptContent === 'string' && pptContent.includes('页面标题：')) {
      const slideSections = pptContent.split('页面标题：')
      for (let i = 1; i < slideSections.length; i++) {
        const section = slideSections[i]
        const lines = section.split('\n')
        const title = lines[0]?.trim() || '无标题'
        let content = ''
        
        for (let j = 1; j < lines.length; j++) {
          const line = lines[j]
          if (line.trim()) {
            content += line + '\n'
          }
        }
        
        slides.push({ title, content: content.trim() })
      }
    } else if (typeof pptContent === 'string' && pptContent.includes('\n\n')) {
      const slideSections = pptContent.split('\n\n')
      for (const section of slideSections) {
        const lines = section.trim().split('\n')
        if (lines.length > 0) {
          const title = lines[0] || '无标题'
          let content = ''
          
          for (let j = 1; j < lines.length; j++) {
            content += lines[j] + '\n'
          }
          
          slides.push({ title, content: content.trim() })
        }
      }
    } else {
      // 默认创建封面和内容幻灯片
      slides.push({ 
        title: courseware.topic || '课件', 
        content: `面向${courseware.audience}的课程\n时长: ${courseware.duration}分钟` 
      })
      slides.push({ 
        title: '课程内容', 
        content: pptContent 
      })
      slides.push({ 
        title: '课程总结', 
        content: '本课程涵盖了相关知识点，希望对您有所帮助！' 
      })
    }
  } else {
    // 默认创建幻灯片
    slides.push({ 
      title: courseware.topic || '课件', 
      content: `面向${courseware.audience}的课程\n时长: ${courseware.duration || 45}分钟` 
    })
    slides.push({ 
      title: '课程内容', 
      content: '课程内容将在这里显示' 
    })
    slides.push({ 
      title: '课程总结', 
      content: '本课程涵盖了相关知识点，希望对您有所帮助！' 
    })
  }
  
  // 生成HTML
  const html = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${courseware.topic || '课件'}</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: 'Microsoft YaHei', Arial, sans-serif;
      line-height: 1.6;
      color: #333;
    }
    
    .slides-container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 20px;
    }
    
    .slide {
      background: white;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 40px;
      margin-bottom: 40px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .slide h2 {
      font-size: 32px;
      color: #2c3e50;
      margin-bottom: 30px;
      text-align: center;
      padding-bottom: 10px;
      border-bottom: 2px solid #3498db;
    }
    
    .slide-content {
      font-size: 18px;
      line-height: 1.8;
    }
    
    .slide-content p {
      margin-bottom: 15px;
    }
    
    .slide-content ul,
    .slide-content ol {
      margin-left: 30px;
      margin-bottom: 15px;
    }
    
    .slide-content li {
      margin-bottom: 8px;
    }
    
    .cover-slide {
      text-align: center;
      padding: 80px 40px;
      background: linear-gradient(135deg, #3498db, #2980b9);
      color: white;
      border: none;
    }
    
    .cover-slide h2 {
      font-size: 48px;
      color: white;
      border-bottom: none;
      margin-bottom: 40px;
    }
    
    .cover-slide .subtitle {
      font-size: 24px;
      margin-bottom: 60px;
    }
    
    .summary-slide {
      background: #f8f9fa;
    }
    
    @media print {
      .slide {
        page-break-after: always;
        margin-bottom: 0;
      }
    }
  </style>
</head>
<body>
  <div class="slides-container">
    ${slides.map((slide, index) => {
      const isCover = index === 0
      const isSummary = index === slides.length - 1
      const slideClass = isCover ? 'slide cover-slide' : isSummary ? 'slide summary-slide' : 'slide'
      
      return `
        <div class="${slideClass}">
          <h2>${slide.title}</h2>
          <div class="slide-content">
            ${slide.content.split('\n').map(line => {
              if (line.trim()) {
                return `<p>${line}</p>`
              }
              return ''
            }).join('')}
          </div>
        </div>
      `
    }).join('')}
  </div>
</body>
</html>
  `
  
  return html
}

// 生成教案HTML - 支持JSON对象和字符串两种格式
function generateLessonPlanHTML(courseware) {
  const lessonPlan = courseware.lesson_plan || '教案内容'
  
  // 将教案内容转为HTML
  function renderContent(data, depth = 0) {
    if (!data) return ''
    if (typeof data === 'string') {
      return data.split('\n').map(line => {
        if (line.trim()) return `<p>${line}</p>`
        return ''
      }).join('')
    }
    if (Array.isArray(data)) {
      return '<ol>' + data.map(item => {
        if (typeof item === 'object' && item !== null) {
          return '<li>' + Object.entries(item).map(([k, v]) => {
            return `<strong>${k}：</strong>${typeof v === 'object' ? renderContent(v, depth + 1) : v}`
          }).join('<br>') + '</li>'
        }
        return `<li>${item}</li>`
      }).join('') + '</ol>'
    }
    if (typeof data === 'object') {
      const tag = depth === 0 ? 'h2' : 'h3'
      return Object.entries(data).map(([key, value]) => {
        let content = ''
        if (typeof value === 'string') {
          content = `<p>${value}</p>`
        } else if (Array.isArray(value)) {
          content = renderContent(value, depth + 1)
        } else if (typeof value === 'object' && value !== null) {
          content = renderContent(value, depth + 1)
        } else {
          content = `<p>${value}</p>`
        }
        return `<${tag}>${key}</${tag}>${content}`
      }).join('')
    }
    return `<p>${data}</p>`
  }

  const contentHTML = renderContent(lessonPlan)
  
  const html = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${courseware.topic || '课件'} - 教案</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Microsoft YaHei', Arial, sans-serif;
      line-height: 1.6; color: #333; background: #f5f5f5;
    }
    .container {
      max-width: 800px; margin: 0 auto; padding: 40px;
      background: white; box-shadow: 0 0 20px rgba(0,0,0,0.1);
    }
    h1 {
      font-size: 28px; color: #1a5ca8; margin-bottom: 30px;
      text-align: center; padding-bottom: 15px;
      border-bottom: 3px solid #1a5ca8;
    }
    h2 {
      font-size: 20px; color: #1a5ca8; margin-top: 25px; margin-bottom: 15px;
      padding: 8px 12px; background: #e8eef7; border-left: 4px solid #1a5ca8;
    }
    h3 {
      font-size: 16px; color: #555; margin-top: 15px; margin-bottom: 10px;
      padding-left: 10px; border-left: 3px solid #ccc;
    }
    p { margin-bottom: 10px; text-align: justify; }
    ul, ol { margin-left: 25px; margin-bottom: 15px; }
    li { margin-bottom: 6px; }
    .info-box {
      background: #f0f5ff; padding: 20px; border-radius: 8px;
      margin-bottom: 20px; border: 1px solid #d0e0f0;
    }
    .info-box h3 { color: #1a5ca8; margin-top: 0; border: none; padding: 0; }
    strong { color: #333; }
  </style>
</head>
<body>
  <div class="container">
    <h1>${courseware.topic || '课件'} - 教案</h1>
    <div class="info-box">
      <h3>课程信息</h3>
      <p><strong>目标受众：</strong>${courseware.audience || courseware.target_audience || '未知'}</p>
      <p><strong>课程时长：</strong>${courseware.duration || 45}分钟</p>
      <p><strong>学科：</strong>${courseware.subject || courseware.topic || '通用'}</p>
    </div>
    <div class="lesson-plan-content">
      ${contentHTML}
    </div>
  </div>
</body>
</html>
  `
  
  return html
}

// 生成游戏HTML
function generateGameHTML(courseware) {
  const gameContent = courseware.interactive_games || '游戏内容'
  
  const html = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${courseware.topic || '课件'} - 互动游戏</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: 'Microsoft YaHei', Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      background: #f0f4f8;
    }
    
    .container {
      max-width: 900px;
      margin: 0 auto;
      padding: 40px;
      background: white;
      box-shadow: 0 0 20px rgba(0,0,0,0.1);
    }
    
    h1 {
      font-size: 32px;
      color: #2c3e50;
      margin-bottom: 30px;
      text-align: center;
      padding-bottom: 15px;
      border-bottom: 3px solid #e74c3c;
    }
    
    .game-info {
      background: #ecf0f1;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 30px;
    }
    
    .game-info h2 {
      font-size: 24px;
      color: #34495e;
      margin-bottom: 15px;
    }
    
    .game-content {
      margin-bottom: 30px;
    }
    
    .game-content h3 {
      font-size: 18px;
      color: #7f8c8d;
      margin-top: 20px;
      margin-bottom: 15px;
    }
    
    p {
      margin-bottom: 15px;
      text-align: justify;
    }
    
    ul,
    ol {
      margin-left: 30px;
      margin-bottom: 15px;
    }
    
    li {
      margin-bottom: 8px;
    }
    
    .play-button {
      display: block;
      width: 200px;
      height: 60px;
      background: linear-gradient(135deg, #e74c3c, #c0392b);
      color: white;
      text-align: center;
      line-height: 60px;
      font-size: 20px;
      font-weight: bold;
      border-radius: 30px;
      text-decoration: none;
      margin: 40px auto;
      transition: all 0.3s ease;
    }
    
    .play-button:hover {
      transform: scale(1.05);
      box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
    }
    
    .game-area {
      background: #f9f9f9;
      padding: 30px;
      border-radius: 8px;
      margin-top: 30px;
      min-height: 300px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px dashed #ddd;
    }
    
    .game-area p {
      color: #999;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>${courseware.topic || '课件'} - 互动游戏</h1>
    
    <div class="game-info">
      <h2>游戏信息</h2>
      <p><strong>课程主题：</strong>${courseware.topic || '未知'}</p>
      <p><strong>目标受众：</strong>${courseware.audience || '未知'}</p>
    </div>
    
    <div class="game-content">
      ${gameContent.split('\n').map(line => {
        if (line.startsWith('1.') || line.startsWith('2.') || line.startsWith('3.') || line.startsWith('4.') || line.startsWith('5.') || line.startsWith('6.') || line.startsWith('7.') || line.startsWith('8.') || line.startsWith('9.') || line.startsWith('10.')) {
          return `<h3>${line}</h3>`
        } else if (line.trim()) {
          return `<p>${line}</p>`
        }
        return ''
      }).join('')}
    </div>
    
    <a href="#" class="play-button">开始游戏</a>
    
    <div class="game-area">
      <p>游戏区域 - 实际游戏内容将在这里显示</p>
    </div>
  </div>
</body>
</html>
  `
  
  return html
}

// 获取当前任务ID
function getTaskId() {
  const cw = coursewareData.value
  if (cw && cw.task_id) return cw.task_id
  return route.params.taskId || null
}

// 提交修改 - 调用后端LLM驱动的PPT优化
async function submitModification() {
  if (!modificationText.value.trim()) {
    ElMessage.warning('请输入修改要求')
    return
  }

  const taskId = getTaskId()
  if (!taskId) {
    ElMessage.error('无法获取任务ID，请重新打开预览页面')
    return
  }

  modifying.value = true

  try {
    const res = await pptApi.post(`/ppt/refine/${taskId}`, {
      feedback: modificationText.value.trim(),
      modification_type: modificationType.value || 'content',
      target_page: targetSlideIndex.value
    })

    if (res.data.success) {
      ElMessage.success(res.data.message || 'PPT内容已优化')

      // 用后端返回的新内容更新幻灯片
      if (res.data.detailed_content) {
        updateSlidesFromContent(res.data.detailed_content)
      }

      // 记录版本历史
      versionHistory.value.unshift({
        version: res.data.version_number,
        date: new Date().toLocaleString(),
        description: `${modificationType.value || '其他修改'}: ${modificationText.value.substring(0, 50)}${modificationText.value.length > 50 ? '...' : ''}`
      })

      // 清空修改内容
      modificationText.value = ''
      modificationType.value = ''
      targetSlideIndex.value = null
    } else {
      ElMessage.error(res.data.message || '修改失败')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '修改失败'
    ElMessage.error(`修改失败: ${msg}`)
  } finally {
    modifying.value = false
  }
}

// 从detailed_content更新幻灯片显示
function updateSlidesFromContent(detailedContent) {
  const newSlides = detailedContent.map((page, i) => {
    let slideContent = ''
    if (page.bullet_points) {
      slideContent += String(page.bullet_points)
    }
    if (page.key_points && page.key_points.length > 0) {
      slideContent += page.key_points.map(p => `- ${p}`).join('\n')
    }
    if (page.toc_items && page.toc_items.length > 0) {
      slideContent += '\n' + page.toc_items.map(item => `- ${item}`).join('\n')
    }
    if (page.knowledge_review && page.knowledge_review.length > 0) {
      slideContent += '\n知识回顾:\n' + page.knowledge_review.map(item => `- ${item}`).join('\n')
    }
    if (page.goals_achievement) {
      slideContent += '\n学习目标达成:\n' + page.goals_achievement
    }
    if (page.homework) {
      slideContent += '\n作业:\n' + page.homework
    }
    if (page.subtitle) {
      slideContent = page.subtitle + '\n' + slideContent
    }
    if (page.instructor_info) {
      slideContent = page.instructor_info + '\n' + slideContent
    }
    return {
      slide_id: `slide_${i}`,
      slide_number: i + 1,
      type: page.page_type || 'content',
      title: page.core_topic || page.main_title || `第${i + 1}页`,
      content: slideContent.trim()
    }
  })
  slides.value = newSlides
}

// 恢复到指定版本
async function revertToVersion(index) {
  const version = versionHistory.value[index]
  if (!version || !version.version) {
    ElMessage.warning('该版本无法恢复')
    return
  }

  const taskId = getTaskId()
  if (!taskId) {
    ElMessage.error('无法获取任务ID')
    return
  }

  try {
    const res = await pptApi.post(`/ppt/revert/${taskId}`, {
      version: version.version
    })

    if (res.data.success) {
      ElMessage.success(res.data.message || `已恢复到版本 ${version.version}`)

      // 用恢复的内容更新幻灯片
      if (res.data.detailed_content) {
        updateSlidesFromContent(res.data.detailed_content)
      }
    } else {
      ElMessage.error(res.data.message || '恢复失败')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '恢复失败'
    ElMessage.error(`版本恢复失败: ${msg}`)
  }
}

// 加载版本历史
async function loadVersionHistory() {
  const taskId = getTaskId()
  if (!taskId) return

  try {
    const res = await pptApi.get(`/ppt/versions/${taskId}`)
    if (res.data.success && res.data.versions.length > 0) {
      versionHistory.value = res.data.versions.map(v => ({
        version: v.version,
        date: v.timestamp,
        description: v.description
      }))
    }
  } catch (e) {
    // 无版本历史时保持默认
  }
}

// 导航
function prevSlide() {
  if (currentSlideIndex.value > 0) {
    currentSlideIndex.value--
  }
}

function nextSlide() {
  if (currentSlideIndex.value < slides.value.length - 1) {
    currentSlideIndex.value++
  }
}

function goBack() {
  router.back()
}

// 轮询任务状态
let pollInterval = null

onMounted(async () => {
  await loadPreview()
  loadVersionHistory()
  
  // 如果任务还在处理中，轮询状态
  if (taskStatus.value !== 'completed') {
    loadTaskStatus()
    pollInterval = setInterval(() => {
      loadTaskStatus()
      // 任务完成后自动停止轮询
      if (taskStatus.value === 'completed' || taskStatus.value === 'failed') {
        clearInterval(pollInterval)
        pollInterval = null
      }
    }, 3000)
  }
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})
</script>

<style lang="scss" scoped>
.preview-view {
  padding: 0;
  height: calc(100vh - 104px);
  overflow: hidden;
}

.preview-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

// 头部
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    h1 {
      font-size: 20px;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
  }
}

// 加载/错误状态
.loading-state,
.error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;

  .el-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  p {
    color: var(--text-secondary);
    margin-bottom: 16px;
  }
}

// 主预览区
.preview-main {
  flex: 1;
  display: grid;
  grid-template-columns: 200px 1fr 280px;
  gap: 16px;
  min-height: 0;
}

// 幻灯片列表
.slides-list {
  padding: 16px;
  overflow-y: auto;

  h3 {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  .slides-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .slide-thumb {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: var(--transition);

    &:hover {
      background: var(--bg-hover);
    }

    &.active {
      background: var(--brand-soft-2);
      color: var(--primary);
    }

    .slide-number {
      width: 20px;
      height: 20px;
      background: var(--bg-card);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      flex-shrink: 0;
    }

    .slide-title {
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

// 幻灯片预览
.slide-preview {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.preview-slide {
  width: 100%;
  max-width: 800px;
  min-height: 450px;
  position: relative;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  background: white;

  &.cover-slide {
    background: linear-gradient(135deg, var(--brand-500), var(--brand-600));
    color: white;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  &.toc-slide {
    background: var(--wb-surface-2);
  }

  &.knowledge-slide {
    background: white;
  }

  &.exercise-slide {
    background: var(--wb-surface-3);
  }

  &.summary-slide {
    background: var(--wb-surface-2);
  }

  .slide-type-badge {
    display: inline-block;
    padding: 4px 12px;
    background: var(--primary);
    color: white;
    font-size: 11px;
    border-radius: 4px;
    margin-bottom: 16px;
  }

  .slide-title {
    font-size: 32px;
    color: var(--wb-text);
    margin-bottom: 24px;
    font-weight: 600;
    line-height: 1.2;

    &.cover-title {
      font-size: 48px;
      color: white;
      margin-bottom: 32px;
    }
  }

  .slide-content {
    font-size: 18px;
    color: var(--wb-text-2);
    line-height: 1.8;

    &.cover-content {
      font-size: 24px;
      color: rgba(255, 255, 255, 0.9);
    }

    ul, ol {
      margin-left: 20px;
      margin-bottom: 16px;
    }

    li {
      margin-bottom: 8px;
    }

    strong {
      color: var(--wb-text);
      font-weight: 600;
    }
  }
}

.preview-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
  padding: 16px;
  border-top: 1px solid var(--border-color);

  .slide-indicator {
    color: var(--text-secondary);
    font-size: 14px;
  }
}

// 附加面板
.extras-panel {
  padding: 16px;
  overflow-y: auto;

  .extra-section {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 0;
    }

    h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }
  }

  .animation-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .animation-item {
    padding: 12px;
    background: var(--wb-mask);
    border-radius: 8px;

    .animation-point {
      font-size: 13px;
      font-weight: 500;
      margin-bottom: 4px;
    }

    .animation-type {
      font-size: 11px;
      color: var(--primary);
      margin-bottom: 4px;
    }

    .animation-desc {
      font-size: 12px;
      color: var(--text-muted);
    }
  }

  .game-card {
    padding: 16px;
    background: var(--wb-mask);
    border-radius: 8px;

    .game-name {
      font-size: 14px;
      font-weight: 500;
      margin-bottom: 4px;
    }

    .game-type {
      font-size: 11px;
      color: var(--primary);
      margin-bottom: 8px;
    }

    .game-desc {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 12px;
    }
  }

  .version-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .version-item {
    padding: 12px;
    background: var(--wb-mask);
    border-radius: 8px;
    border-left: 3px solid transparent;
    transition: var(--transition);

    &:hover {
      background: var(--wb-mask);
    }

    &.active {
      border-left-color: var(--primary);
      background: var(--brand-soft);
    }

    .version-number {
      font-size: 11px;
      color: var(--primary);
      font-weight: 500;
      margin-bottom: 4px;
    }

    .version-date {
      font-size: 10px;
      color: var(--text-muted);
      margin-bottom: 4px;
    }

    .version-desc {
      font-size: 12px;
      margin-bottom: 8px;
    }
  }
}

// 生成中状态
.generating-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  h2 {
    margin-top: 32px;
    margin-bottom: 8px;
  }

  p {
    color: var(--text-secondary);
  }
}

.generating-animation {
  position: relative;
  width: 120px;
  height: 120px;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 3px solid var(--primary);
  border-radius: 50%;
  animation: pulse-out 2s ease-out infinite;

  &.delay {
    animation-delay: 0.5s;
  }

  &.delay2 {
    animation-delay: 1s;
  }
}

@keyframes pulse-out {
  0% {
    transform: scale(0.5);
    opacity: 1;
  }
  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}
</style>
