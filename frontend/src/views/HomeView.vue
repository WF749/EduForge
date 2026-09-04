<template>
  <div class="home-view">
    <div class="home-container">
      <!-- Hero Section -->
      <section class="hero-section">
        <div class="hero-bg-effects">
          <div class="effect-orb orb-1"></div>
          <div class="effect-orb orb-2"></div>
          <div class="effect-orb orb-3"></div>
        </div>



        <h1 class="hero-title">
          <span class="title-line">EduForge</span>
          <span class="title-line gradient">本地化备课智能体工作台</span>
        </h1>

        <p class="hero-description">
          基于大模型的多模态互动式教学辅助系统，融合意图理解、知识库RAG、课件智能生成等核心能力，
          支持多阶段多学科教学场景，助力教师高效完成教学准备工作
        </p>

        <div class="hero-cta">
          <router-link to="/chat" class="btn-primary">
            <el-icon :size="20"><VideoPlay /></el-icon>
            <span>开始使用</span>
          </router-link>
          <router-link to="/knowledge" class="btn-secondary">
            <el-icon :size="20"><Collection /></el-icon>
            <span>知识库管理</span>
          </router-link>
        </div>

        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-value">7+</span>
            <span class="stat-label">核心功能</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">10+</span>
            <span class="stat-label">文件格式</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">3</span>
            <span class="stat-label">LLM服务商</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">K12+</span>
            <span class="stat-label">多阶段支持</span>
          </div>
        </div>
      </section>

      <!-- Features Section -->
      <section class="features-section">
        <div class="section-header">
          <h2 class="section-title">核心功能</h2>
          <p class="section-subtitle">五大核心能力，全方位辅助教学</p>
        </div>

        <div class="features-grid">
          <div
            v-for="(feature, index) in features"
            :key="index"
            class="feature-card"
            :style="{ '--card-index': index }"
            @click="goToFeature(feature.path)"
          >
            <div class="card-glow-effect"></div>
            <div class="card-header">
              <div class="feature-icon" :style="{ background: feature.gradient }">
                <el-icon :size="28"><component :is="feature.icon" /></el-icon>
              </div>
              <span class="feature-number">0{{ index + 1 }}</span>
            </div>
            <h3 class="feature-title">{{ feature.title }}</h3>
            <p class="feature-description">{{ feature.description }}</p>
            <div class="card-tags">
              <span v-for="tag in feature.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
            <div class="card-arrow">
              <el-icon :size="20"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </section>

      <!-- Multi-Stage Support Section -->
      <section class="stage-section">
        <div class="section-header">
          <h2 class="section-title">多阶段多学科支持</h2>
          <p class="section-subtitle">覆盖K12至高教的全学段教学场景</p>
        </div>

        <div class="stage-timeline">
          <div class="stage-item" v-for="(stage, index) in educationStages" :key="index">
            <div class="stage-marker">
              <div class="marker-dot"></div>
              <div class="marker-line"></div>
            </div>
            <div class="stage-content">
              <h4>{{ stage.name }}</h4>
              <p>{{ stage.description }}</p>
              <div class="stage-subjects">
                <span v-for="subject in stage.subjects" :key="subject" class="subject-tag">
                  {{ subject }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Workflow Section -->
      <section class="workflow-section">
        <div class="section-header">
          <h2 class="section-title">智能工作流</h2>
          <p class="section-subtitle">从需求到课件，一站式智能生成</p>
        </div>

        <div class="workflow-steps">
          <div
            v-for="(step, index) in workflowSteps"
            :key="index"
            class="workflow-step"
            :class="{ active: currentWorkflowStep >= index }"
          >
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-content">
              <el-icon :size="24" class="step-icon"><component :is="step.icon" /></el-icon>
              <h4>{{ step.title }}</h4>
              <p>{{ step.description }}</p>
            </div>
            <div class="step-connector" v-if="index < workflowSteps.length - 1">
              <el-icon :size="16"><d-arrow-right /></el-icon>
            </div>
          </div>
        </div>
      </section>

      <!-- Tech Stack Section -->
      <section class="tech-section">
        <div class="section-header">
          <h2 class="section-title">技术架构</h2>
          <p class="section-subtitle">现代化技术栈，稳定可靠</p>
        </div>

        <div class="tech-layers">
          <div class="tech-layer" v-for="layer in techLayers" :key="layer.name">
            <div class="layer-label">{{ layer.name }}</div>
            <div class="layer-items">
              <div
                v-for="tech in layer.techs"
                :key="tech.name"
                class="tech-item"
                :style="{ '--tech-color': tech.color }"
              >
                <span class="tech-icon">{{ tech.icon }}</span>
                <span class="tech-name">{{ tech.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Open Source Section -->
      <section class="opensource-section">
        <div class="opensource-card">
          <div class="opensource-header">
            <el-icon :size="24"><Link /></el-icon>
            <h3>开源组件声明</h3>
          </div>
          <p class="opensource-desc">本项目基于以下优秀开源组件构建</p>
          <div class="opensource-grid">
            <div v-for="lib in openSourceLibs" :key="lib.name" class="opensource-item">
              <span class="lib-name">{{ lib.name }}</span>
              <span class="lib-license">{{ lib.license }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChatDotRound,
  Document,
  Collection,
  DataAnalysis,
  Microphone,
  Star,
  VideoPlay,
  ArrowRight,
  Link,
  Upload,
  Cpu,
  Connection,
  Files,
  View,
  DArrowRight,
  VideoCamera,
  TrophyBase
} from '@element-plus/icons-vue'

defineOptions({ name: 'HomeView' })

const router = useRouter()
const currentWorkflowStep = ref(-1)
let stepInterval = null

// Features
const features = [
  {
    title: '智能对话理解',
    description: '多轮对话深入理解教师教学意图，主动询问澄清需求，精准把握教学要点，支持语音输入',
    icon: ChatDotRound,
    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    tags: ['意图识别', '多轮对话', '语音输入'],
    path: '/chat'
  },
  {
    title: '多模态资料处理',
    description: '支持PDF、Word、PPT、图片、视频等多种格式文档的智能解析与内容提取',
    icon: Files,
    gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    tags: ['PDF解析', 'Word解析', 'PPT解析'],
    path: '/knowledge'
  },
  {
    title: '本地知识库RAG',
    description: '专业知识检索增强生成技术，智能融合参考资料与教学需求，提升生成质量',
    icon: DataAnalysis,
    gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    tags: ['向量检索', '知识融合', '上下文增强'],
    path: '/knowledge'
  },
  {
    title: '多模态课件生成',
    description: '自动生成精美PPT课件和完整Word教案，支持自定义动画和互动小游戏',
    icon: Document,
    gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    tags: ['PPT生成', 'Word教案', '动画创意'],
    path: '/courseware'
  },
  {
    title: '迭代优化预览',
    description: '实时预览生成结果，支持多轮迭代优化，确保课件质量符合预期',
    icon: View,
    gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    tags: ['实时预览', '迭代优化', '格式导出'],
    path: '/preview/demo'
  },
  {
    title: '教学动画创意',
    description: '智能生成教学动画方案，包含分镜脚本、角色设计、制作指南，支持HTML5预览',
    icon: VideoCamera,
    gradient: 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)',
    tags: ['分镜脚本', '角色设计', 'HTML5预览'],
    path: '/animation'
  },
  {
    title: '互动游戏生成',
    description: '自动生成教学互动小游戏，支持选择题、填空题、匹配题等多种类型，可直接在浏览器中体验',
    icon: TrophyBase,
    gradient: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
    tags: ['选择题', '闯关游戏', 'HTML5可玩'],
    path: '/game'
  }
]

// Education Stages
const educationStages = [
  {
    name: 'K12基础教育',
    description: '覆盖小学、初中、高中各学科教学需求',
    subjects: ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理']
  },
  {
    name: '高等教育',
    description: '支持大学、职高的专业课程教学',
    subjects: ['计算机', '医学', '工程', '经管', '法学', '艺术']
  },
  {
    name: '职业教育',
    description: '企业培训、职业技能提升场景',
    subjects: ['技能培训', '认证课程', '企业内部培训']
  }
]

// Workflow Steps
const workflowSteps = [
  { title: '需求输入', description: '文字/语音描述教学需求', icon: Microphone },
  { title: '意图理解', description: 'AI智能分析教学目标', icon: Connection },
  { title: '资料上传', description: '添加参考教材和教案', icon: Upload },
  { title: '知识融合', description: 'RAG检索增强生成', icon: Cpu },
  { title: '课件生成', description: 'PPT+教案一键生成', icon: Document },
  { title: '迭代优化', description: '预览调整直至满意', icon: Star }
]

// Tech Layers
const techLayers = [
  {
    name: '表现层',
    techs: [
      { name: 'Vue 3', icon: 'V', color: '#42b883' },
      { name: 'Element Plus', icon: 'E', color: '#409eff' },
      { name: 'Three.js', icon: '3', color: '#000' }
    ]
  },
  {
    name: '业务层',
    techs: [
      { name: 'FastAPI', icon: 'F', color: '#009688' },
      { name: 'Python', icon: 'Py', color: '#3776ab' },
      { name: 'ChromaDB', icon: 'C', color: '#da5a53' }
    ]
  },
  {
    name: 'AI服务层',
    techs: [
      { name: '通义千问', icon: 'Q', color: '#ff6a00' },
      { name: 'RAG', icon: 'R', color: '#9333ea' },
      { name: 'Embedding', icon: 'E', color: '#0891b2' }
    ]
  }
]

// Open Source Libs
const openSourceLibs = [
  { name: 'Vue 3', license: 'MIT' },
  { name: 'FastAPI', license: 'MIT' },
  { name: 'Element Plus', license: 'MIT' },
  { name: 'ChromaDB', license: 'Apache 2.0' },
  { name: 'pdfplumber', license: 'MIT' },
  { name: 'python-docx', license: 'MIT' },
  { name: 'python-pptx', license: 'MIT' }
]

function goToFeature(path) {
  router.push(path)
}

onMounted(() => {
  // Animate workflow steps
  let step = 0
  stepInterval = setInterval(() => {
    currentWorkflowStep.value = step
    step++
    if (step >= workflowSteps.length) {
      clearInterval(stepInterval)
      stepInterval = null
    }
  }, 400)
})

onBeforeUnmount(() => {
  if (stepInterval) {
    clearInterval(stepInterval)
    stepInterval = null
  }
})
</script>

<style lang="scss" scoped>
.home-view {
  height: calc(100vh - 112px);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 200, 255, 0.3);
    border-radius: 3px;
  }
}

.home-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px;
}

// Section common styles
.section-header {
  text-align: center;
  margin-bottom: 48px;

  .section-title {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 12px;
    background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }

  .section-subtitle {
    font-size: 16px;
    color: var(--text-secondary);
  }
}

// Hero Section
.hero-section {
  position: relative;
  text-align: center;
  padding: 60px 0 80px;
  overflow: hidden;

  .hero-bg-effects {
    position: absolute;
    inset: 0;
    pointer-events: none;

    .effect-orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(80px);
      opacity: 0.4;

      &.orb-1 {
        width: 500px;
        height: 500px;
        background: var(--primary);
        top: -200px;
        right: -150px;
        animation: float-orb 20s ease-in-out infinite;
      }

      &.orb-2 {
        width: 400px;
        height: 400px;
        background: var(--accent);
        bottom: -150px;
        left: -100px;
        animation: float-orb 25s ease-in-out infinite reverse;
      }

      &.orb-3 {
        width: 300px;
        height: 300px;
        background: #764ba2;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        animation: float-orb 15s ease-in-out infinite;
      }
    }
  }
}

@keyframes float-orb {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(0, -60px) scale(1); }
  75% { transform: translate(-30px, -30px) scale(0.95); }
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 24px;
  background: rgba(0, 200, 255, 0.08);
  border: 1px solid rgba(0, 200, 255, 0.25);
  border-radius: 30px;
  font-size: 13px;
  color: var(--primary);
  margin-bottom: 32px;
  position: relative;
  z-index: 1;

  .badge-pulse {
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.hero-title {
  position: relative;
  z-index: 1;
  font-size: 52px;
  font-weight: 900;
  line-height: 1.2;
  margin-bottom: 24px;

  .title-line {
    display: block;
  }

  .gradient {
    background: linear-gradient(135deg, #00c8ff 0%, #00ff88 50%, #764ba2 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    background-size: 200% auto;
    animation: gradient-shift 4s ease-in-out infinite;
  }
}

@keyframes gradient-shift {
  0%, 100% { background-position: 0% center; }
  50% { background-position: 100% center; }
}

.hero-description {
  position: relative;
  z-index: 1;
  font-size: 18px;
  color: #c8d0dc;
  max-width: 720px;
  margin: 0 auto 40px;
  line-height: 1.8;
}

.hero-cta {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 60px;

  .btn-primary, .btn-secondary {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 32px;
    font-size: 16px;
    font-weight: 600;
    text-decoration: none;
    border-radius: 12px;
    transition: all 0.3s ease;
  }

  .btn-primary {
    background: linear-gradient(135deg, var(--primary), #0099cc);
    color: white;
    box-shadow: 0 4px 24px rgba(0, 200, 255, 0.35);

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 32px rgba(0, 200, 255, 0.5);
    }
  }

  .btn-secondary {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--text-primary);

    &:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: var(--primary);
    }
  }
}

.hero-stats {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;

  .stat-item {
    text-align: center;

    .stat-value {
      display: block;
      font-size: 36px;
      font-weight: 800;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      color: transparent;
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-muted);
    }
  }

  .stat-divider {
    width: 1px;
    height: 40px;
    background: rgba(255, 255, 255, 0.1);
  }
}

// Features Section
.features-section {
  padding: 80px 0;

  .features-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;

    @media (max-width: 1024px) {
      grid-template-columns: repeat(2, 1fr);
    }

    @media (max-width: 640px) {
      grid-template-columns: 1fr;
    }
  }

  .feature-card {
    position: relative;
    padding: 28px;
    background: rgba(10, 14, 39, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    cursor: pointer;
    overflow: hidden;
    transition: all 0.4s ease;

    &:hover {
      transform: translateY(-6px);
      border-color: rgba(0, 200, 255, 0.4);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);

      .card-glow-effect {
        opacity: 1;
      }

      .card-arrow {
        opacity: 1;
        transform: translateX(0);
      }
    }

    .card-glow-effect {
      position: absolute;
      top: -100%;
      left: -100%;
      width: 300%;
      height: 300%;
      background: radial-gradient(circle, rgba(0, 200, 255, 0.08) 0%, transparent 60%);
      opacity: 0;
      transition: opacity 0.4s ease;
      pointer-events: none;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;

      .feature-icon {
        width: 56px;
        height: 56px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      }

      .feature-number {
        font-size: 14px;
        font-weight: 700;
        color: var(--text-muted);
        opacity: 0.5;
      }
    }

    .feature-title {
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 12px;
    }

    .feature-description {
      font-size: 14px;
      color: #b0b8c4;
      line-height: 1.7;
      margin-bottom: 16px;
    }

    .card-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .tag {
        padding: 4px 10px;
        font-size: 11px;
        background: rgba(0, 200, 255, 0.08);
        border: 1px solid rgba(0, 200, 255, 0.15);
        border-radius: 6px;
        color: var(--primary);
      }
    }

    .card-arrow {
      position: absolute;
      bottom: 20px;
      right: 20px;
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 200, 255, 0.1);
      border-radius: 50%;
      color: var(--primary);
      opacity: 0;
      transform: translateX(-10px);
      transition: all 0.3s ease;
    }
  }
}

// Stage Section
.stage-section {
  padding: 80px 0;

  .stage-timeline {
    max-width: 800px;
    margin: 0 auto;
    position: relative;
  }

  .stage-item {
    display: flex;
    gap: 24px;
    padding-bottom: 40px;
    position: relative;

    &:last-child {
      padding-bottom: 0;

      .marker-line {
        display: none;
      }
    }

    .stage-marker {
      position: relative;

      .marker-dot {
        width: 16px;
        height: 16px;
        background: linear-gradient(135deg, var(--primary), var(--accent));
        border-radius: 50%;
        box-shadow: 0 0 20px rgba(0, 200, 255, 0.5);
      }

      .marker-line {
        position: absolute;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 2px;
        height: calc(100% + 20px);
        background: linear-gradient(to bottom, var(--primary), transparent);
      }
    }

    .stage-content {
      flex: 1;
      padding: 20px 24px;
      background: rgba(10, 14, 39, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 16px;

      h4 {
        font-size: 18px;
        margin-bottom: 8px;
        color: var(--text-primary);
      }

      p {
        font-size: 14px;
        color: #b0b8c4;
        margin-bottom: 12px;
      }

      .stage-subjects {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;

        .subject-tag {
          padding: 4px 12px;
          font-size: 12px;
          background: rgba(124, 58, 237, 0.15);
          border: 1px solid rgba(124, 58, 237, 0.25);
          border-radius: 20px;
          color: #a855f7;
        }
      }
    }
  }
}

// Workflow Section
.workflow-section {
  padding: 80px 0;

  .workflow-steps {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    position: relative;
    gap: 8px;

    &::before {
      content: '';
      position: absolute;
      top: 24px;
      left: 60px;
      right: 60px;
      height: 3px;
      background: linear-gradient(90deg, var(--primary), var(--accent), var(--primary));
      border-radius: 2px;
      opacity: 0.3;
    }
  }

  .workflow-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    position: relative;
    flex: 1;
    opacity: 0.4;
    transition: all 0.4s ease;

    &.active {
      opacity: 1;

      .step-number {
        background: linear-gradient(135deg, var(--primary), var(--accent));
        box-shadow: 0 0 30px rgba(0, 200, 255, 0.5);
      }

      .marker-dot {
        animation: pulse-ring 1.5s ease-out infinite;
      }
    }

    .step-number {
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 200, 255, 0.2);
      border: 2px solid var(--primary);
      border-radius: 50%;
      font-size: 18px;
      font-weight: 700;
      color: white;
      margin-bottom: 16px;
      transition: all 0.3s ease;
    }

    .step-content {
      .step-icon {
        color: var(--primary);
        margin-bottom: 8px;
      }

      h4 {
        font-size: 14px;
        margin-bottom: 4px;
      }

      p {
        font-size: 12px;
        color: #8b95a5;
      }
    }

    .step-connector {
      position: absolute;
      right: -20px;
      top: 20px;
      color: var(--primary);
      opacity: 0.3;
    }
  }
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(0, 200, 255, 0.5); }
  100% { box-shadow: 0 0 0 15px rgba(0, 200, 255, 0); }
}

// Tech Section
.tech-section {
  padding: 80px 0;

  .tech-layers {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
  }

  .tech-layer {
    width: 100%;
    max-width: 700px;

    .layer-label {
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-bottom: 12px;
      text-align: center;
    }

    .layer-items {
      display: flex;
      justify-content: center;
      gap: 16px;
      flex-wrap: wrap;
    }

    .tech-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 24px;
      background: rgba(10, 14, 39, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      transition: all 0.3s ease;

      &:hover {
        border-color: var(--tech-color);
        background: rgba(255, 255, 255, 0.03);
      }

      .tech-icon {
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--tech-color);
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        color: white;
      }

      .tech-name {
        font-size: 14px;
        font-weight: 500;
      }
    }
  }
}

// Open Source Section
.opensource-section {
  padding: 60px 0 40px;

  .opensource-card {
    padding: 32px;
    background: rgba(10, 14, 39, 0.5);
    border: 1px solid rgba(0, 200, 255, 0.1);
    border-radius: 20px;
    text-align: center;

    .opensource-header {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 12px;
      color: var(--primary);

      h3 {
        font-size: 18px;
      }
    }

    .opensource-desc {
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 24px;
    }

    .opensource-grid {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 12px;

      .opensource-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 8px;

        .lib-name {
          font-size: 13px;
          font-weight: 500;
        }

        .lib-license {
          font-size: 11px;
          padding: 2px 8px;
          background: rgba(0, 200, 255, 0.1);
          border-radius: 4px;
          color: var(--primary);
        }
      }
    }
  }
}
</style>
