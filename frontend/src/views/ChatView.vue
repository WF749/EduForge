﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="chat-view">
    <div class="chat-layout">

      <!-- ========== 左侧会话列表 ========== -->
      <aside class="chat-sidebar">
        <div class="sidebar-top">
          <div class="sidebar-logo">
            <svg width="28" height="28" viewBox="0 0 28 28">
              <circle cx="14" cy="14" r="13" fill="none" stroke="#00c8ff" stroke-width="1.5"/>
              <circle cx="14" cy="14" r="7" fill="#00c8ff" opacity="0.3"/>
              <circle cx="14" cy="14" r="3.5" fill="#00c8ff"/>
            </svg>
            <span>EduForge</span>
          </div>
          <el-button :icon="Plus" circle size="small" @click="createNewChat" title="新建对话" />
        </div>

        <div class="conversation-list">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="conv-item"
            :class="{ active: conv.id === currentConversationId }"
            @click="selectConversation(conv.id)"
          >
            <el-icon :size="16"><ChatLineRound /></el-icon>
            <span class="conv-title">{{ conv.title || '新对话' }}</span>
            <el-button
              :icon="Delete"
              text size="small" class="conv-del"
              @click.stop="deleteConversation(conv.id)"
            />
          </div>
          <div v-if="conversations.length === 0" class="empty-convs">
            <el-icon :size="32" color="#555"><ChatDotRound /></el-icon>
            <p>暂无历史对话</p>
          </div>
        </div>

        <div class="sidebar-footer">
          <el-button text size="small" @click="goSettings">
            <el-icon><Setting /></el-icon>
            设置
          </el-button>
        </div>
      </aside>

      <!-- ========== 主聊天区 ========== -->
      <main class="chat-main">

        <!-- 顶部栏：数字人 + 模型状态 -->
        <div class="chat-topbar">
          <div class="dh-widget">
            <!-- 数字人头像 -->
            <div class="dh-avatar" :class="{ thinking: isLoading, speaking: isSpeaking }">
              <svg viewBox="0 0 80 80" width="80" height="80" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <radialGradient id="faceBg" cx="50%" cy="38%" r="55%">
                    <stop offset="0%" stop-color="#d8eeff"/>
                    <stop offset="100%" stop-color="#72b3f0"/>
                  </radialGradient>
                  <linearGradient id="clothBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#00c8ff"/>
                    <stop offset="100%" stop-color="#0044cc"/>
                  </linearGradient>
                </defs>
                <!-- 身体 -->
                <ellipse cx="40" cy="72" rx="18" ry="8" fill="url(#clothBg)" opacity="0.8"/>
                <rect x="30" y="58" width="20" height="16" rx="4" fill="url(#clothBg)"/>
                <!-- 衣领 -->
                <path d="M33 58 L40 67 L47 58" fill="#003399" opacity="0.8"/>
                <!-- 脖子 -->
                <rect x="36" y="50" width="8" height="10" rx="3" fill="#c8ddf0"/>
                <!-- 头部 -->
                <circle cx="40" cy="35" r="22" fill="url(#faceBg)"/>
                <!-- 头发 -->
                <ellipse cx="40" cy="18" rx="20" ry="10" fill="#1a3560"/>
                <rect x="20" y="16" width="40" height="8" rx="4" fill="#1a3560"/>
                <!-- 眼睛 -->
                <ellipse class="eye-l" cx="33" cy="34" rx="4" ry="3" fill="#1a2060"/>
                <ellipse class="eye-r" cx="47" cy="34" rx="4" ry="3" fill="#1a2060"/>
                <circle cx="34.5" cy="32.8" r="1.2" fill="white"/>
                <circle cx="48.5" cy="32.8" r="1.2" fill="white"/>
                <!-- 眉毛 -->
                <path d="M29 29 Q33 27 37 29" stroke="#1a3560" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <path d="M43 29 Q47 27 51 29" stroke="#1a3560" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <!-- 鼻子 -->
                <path d="M39 37 Q40 41 41 37" stroke="#8baac8" stroke-width="1.2" fill="none"/>
                <!-- 微笑 -->
                <path class="smile" d="M33 44 Q40 51 47 44" stroke="#1a4080" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <!-- 腮红 -->
                <ellipse cx="28" cy="40" rx="5" ry="3" fill="#ffb3c6" opacity="0.35"/>
                <ellipse cx="52" cy="40" rx="5" ry="3" fill="#ffb3c6" opacity="0.35"/>
                <!-- 胸前AI徽章 -->
                <circle cx="32" cy="65" r="5" fill="rgba(0,200,255,0.25)" stroke="#00c8ff" stroke-width="1"/>
                <text x="32" y="68" text-anchor="middle" font-size="5" fill="#00c8ff" font-weight="bold">AI</text>
              </svg>
              <!-- 脉冲光环 -->
              <div class="pulse-ring" v-if="isLoading || isSpeaking"></div>
              <!-- 状态灯 -->
              <div class="status-lamp" :class="isLoading ? 'lamp-think' : isSpeaking ? 'lamp-speak' : 'lamp-idle'"></div>
            </div>

            <!-- 数字人信息 -->
            <el-tooltip placement="bottom" effect="light">
              <template #content>
                <div style="max-width: 260px; line-height: 1.6;">
                  <b>🤖 EduForge 数字人</b><br/><br/>
                  <b>作用说明：</b><br/>
                  1. <b>状态可视化</b>：实时显示AI思考/朗读状态<br/>
                  2. <b>语音朗读</b>：开启后自动朗读AI回答内容<br/>
                  3. <b>情感交互</b>：根据问题内容展现不同表情<br/>
                  4. <b>教学陪伴</b>：像真实教师一样陪伴学习<br/><br/>
                  <b>使用技巧：</b><br/>
                  • 点击 🔊 开启自动朗读<br/>
                  • 点击"深度思考"获得更详细分析<br/>
                  • 点击"教师模式"获取专业教学建议
                </div>
              </template>
              <div class="dh-info">
                <div class="dh-name-row">
                  <span class="dh-name">EduForge</span>
                  <el-tag size="small" :type="providerStatusType" effect="dark">
                    {{ providerStatusText }}
                  </el-tag>
                </div>
                <div class="dh-status">
                  <span v-if="isLoading" class="status-thinking">
                    <span class="blink-dot"></span> AI 思考中...
                  </span>
                  <span v-else-if="isSpeaking" class="status-speaking">
                    🔊 朗读中
                  </span>
                  <span v-else class="status-ready">● 就绪</span>
                </div>
                <!-- 功能模式标签 -->
                <div class="mode-tags">
                  <span v-if="deepThinkingEnabled" class="mode-tag deep">深度思考</span>
                  <span v-if="smartSearchEnabled" class="mode-tag search">智能搜索</span>

                  <span v-if="useKnowledgeBase" class="mode-tag kb">知识库</span>
                </div>
              </div>
            </el-tooltip>

            <!-- 语音控制 -->
            <div class="voice-ctrl">
              <el-tooltip :content="autoSpeak ? '关闭自动朗读' : '开启自动朗读'">
                <el-button
                  circle
                  size="small"
                  :type="autoSpeak ? 'primary' : 'default'"
                  @click="toggleAutoSpeak"
                >
                  {{ autoSpeak ? '🔊' : '🔇' }}
                </el-button>
              </el-tooltip>
              <el-button
                v-if="isSpeaking"
                circle size="small" type="danger"
                @click="stopSpeaking"
              >停止</el-button>
            </div>
          </div>

          <!-- 右侧操作 -->
          <div class="topbar-right">
            <el-button
              v-if="messages.length > 0"
              text size="small"
              @click="clearCurrentChat"
            >
              <el-icon><Delete /></el-icon>
              清空
            </el-button>
          </div>
        </div>

        <!-- ========== 消息区域 ========== -->
        <div class="messages-container" ref="messagesRef">

          <!-- 欢迎页 -->
          <div v-if="messages.length === 0" class="welcome-panel">
            <div class="welcome-avatar-wrap">
              <svg viewBox="0 0 80 80" width="80" height="80" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <radialGradient id="wFace2" cx="50%" cy="38%" r="55%">
                    <stop offset="0%" stop-color="#d8eeff"/>
                    <stop offset="100%" stop-color="#72b3f0"/>
                  </radialGradient>
                  <linearGradient id="wCloth2" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#00c8ff"/>
                    <stop offset="100%" stop-color="#0044cc"/>
                  </linearGradient>
                </defs>
                <ellipse cx="40" cy="72" rx="18" ry="8" fill="url(#wCloth2)" opacity="0.8"/>
                <rect x="30" y="58" width="20" height="16" rx="4" fill="url(#wCloth2)"/>
                <path d="M33 58 L40 67 L47 58" fill="#003399" opacity="0.8"/>
                <rect x="36" y="50" width="8" height="10" rx="3" fill="#c8ddf0"/>
                <circle cx="40" cy="35" r="22" fill="url(#wFace2)"/>
                <ellipse cx="40" cy="18" rx="20" ry="10" fill="#1a3560"/>
                <rect x="20" y="16" width="40" height="8" rx="4" fill="#1a3560"/>
                <ellipse cx="33" cy="34" rx="4" ry="3" fill="#1a2060"/>
                <ellipse cx="47" cy="34" rx="4" ry="3" fill="#1a2060"/>
                <circle cx="34.5" cy="32.8" r="1.2" fill="white"/>
                <circle cx="48.5" cy="32.8" r="1.2" fill="white"/>
                <path d="M29 29 Q33 27 37 29" stroke="#1a3560" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <path d="M43 29 Q47 27 51 29" stroke="#1a3560" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <path d="M39 37 Q40 41 41 37" stroke="#8baac8" stroke-width="1.2" fill="none"/>
                <path d="M33 44 Q40 51 47 44" stroke="#1a4080" stroke-width="1.8" fill="none" stroke-linecap="round"/>
                <ellipse cx="28" cy="40" rx="5" ry="3" fill="#ffb3c6" opacity="0.35"/>
                <ellipse cx="52" cy="40" rx="5" ry="3" fill="#ffb3c6" opacity="0.35"/>
                <circle cx="32" cy="65" r="5" fill="rgba(0,200,255,0.25)" stroke="#00c8ff" stroke-width="1"/>
                <text x="32" y="68" text-anchor="middle" font-size="5" fill="#00c8ff" font-weight="bold">AI</text>
              </svg>
              <div class="welcome-ring"></div>
            </div>

            <h2>你好，我是 EduForge</h2>
            <p class="welcome-desc">我可以帮你设计课件、生成教案、创建互动内容、解答教学问题</p>

            <!-- 快捷功能入口 -->
            <div class="quick-grid">
              <button v-for="q in quickActions" :key="q.label" class="quick-card" @click="handleQuickAction(q)">
                <span class="qc-icon">{{ q.icon }}</span>
                <span class="qc-label">{{ q.label }}</span>
                <span class="qc-desc">{{ q.desc }}</span>
              </button>
            </div>

            <!-- 快捷输入提示 -->
            <div class="welcome-hints">
              <span v-for="h in quickHints" :key="h" class="hint-chip" @click="useQuickPrompt(h)">{{ h }}</span>
            </div>
          </div>

          <!-- 消息列表 -->
          <div class="messages-list" v-else>
            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              class="msg-wrapper"
              :class="msg.role"
            >
              <!-- 用户头像 -->
              <div class="msg-avatar user-av" v-if="msg.role === 'user'">
                <div class="avatar-circle user-circle">
                  <el-icon :size="18"><UserFilled /></el-icon>
                </div>
              </div>

              <!-- AI头像 -->
              <div class="msg-avatar ai-av" v-else>
                <div class="avatar-circle ai-circle">
                  <svg viewBox="0 0 24 24" width="18" height="18">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#00c8ff" stroke-width="1.5"/>
                    <circle cx="12" cy="12" r="4" fill="#00c8ff" opacity="0.5"/>
                    <circle cx="12" cy="12" r="2" fill="#00c8ff"/>
                  </svg>
                </div>
              </div>

              <!-- 消息内容 -->
              <div class="msg-body">
                <!-- 模式标签 -->
                <div class="msg-mode-tag" v-if="msg.is_thinking">
                  <el-icon><Cpu /></el-icon> 深度思考模式
                </div>
                <div class="msg-mode-tag search-tag" v-if="msg.is_search">
                  <el-icon><Search /></el-icon> 智能搜索模式
                </div>

                <!-- 用户上传的图片 -->
                <div class="msg-image" v-if="msg.image_preview">
                  <img :src="msg.image_preview" alt="用户上传图片" @click="previewFullImage(msg.image_preview)" />
                </div>

                <!-- 气泡 -->
                <div
                  class="msg-bubble"
                  :class="{ 'streaming': msg.is_streaming }"
                  v-html="formatMessage(msg.content)"
                ></div>

                <!-- 消息脚注 -->
                <div class="msg-footer" v-if="msg.role === 'assistant'">
                  <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
                  <div class="msg-ops">
                    <el-button size="small" text @click="copyMessage(msg.content)"><el-icon><CopyDocument /></el-icon></el-button>
                    <el-button size="small" text @click="regenerateMsg(idx)"><el-icon><RefreshRight /></el-icon> 重试</el-button>
                    <el-button size="small" text @click="goToCourseware"><el-icon><Document /></el-icon> 生成课件</el-button>
                  </div>
                </div>
                <!-- AI生成内容免责提示 -->
                <div class="ai-disclaimer" v-if="msg.role === 'assistant' && !msg.is_streaming && msg.content">
                  <span class="disclaimer-icon">&#9432;</span>
                  <span>内容由 AI 生成，仅供参考，请注意甄别</span>
                </div>
                <!-- 后续建议 -->
                <div class="followup-suggestions" v-if="msg.followup_suggestions && msg.followup_suggestions.length > 0 && !msg.is_streaming">
                  <div class="followup-chips">
                    <span
                      v-for="(suggestion, sIdx) in msg.followup_suggestions"
                      :key="sIdx"
                      class="followup-chip"
                      @click="useSuggestion(suggestion)"
                    >{{ suggestion }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 加载指示器 -->
            <div v-if="isLoading" class="msg-wrapper assistant">
              <div class="msg-avatar ai-av">
                <div class="avatar-circle ai-circle">
                  <svg viewBox="0 0 24 24" width="18" height="18">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#00c8ff" stroke-width="1.5"/>
                    <circle cx="12" cy="12" r="4" fill="#00c8ff" opacity="0.5"/>
                    <circle cx="12" cy="12" r="2" fill="#00c8ff"/>
                  </svg>
                </div>
              </div>
              <div class="msg-body">
                <div class="typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ========== 输入区域 ========== -->
        <div class="input-area">
          <!-- 已上传文件 -->
          <div class="uploaded-files" v-if="uploadedFiles.length > 0">
            <div v-for="f in uploadedFiles" :key="f.file_id" class="file-chip">
              <el-icon><Document /></el-icon>
              <span>{{ f.filename }}</span>
              <el-button :icon="Close" text size="small" @click="removeFile(f.file_id)" />
            </div>
          </div>

          <!-- 模式开关行 -->
          <div class="mode-row">
            <div class="mode-btn" :class="{ active: deepThinkingEnabled }" @click="toggleDeepThinking">
              <span class="mode-dot deep-dot"></span>
              <span>深度思考</span>
              <span class="mode-on" v-if="deepThinkingEnabled">ON</span>
            </div>
            <div class="mode-btn" :class="{ active: smartSearchEnabled }" @click="toggleSmartSearch">
              <span class="mode-dot search-dot"></span>
              <span>智能搜索</span>
              <span class="mode-on" v-if="smartSearchEnabled">ON</span>
            </div>

            <div class="mode-btn kb-btn" :class="{ active: useKnowledgeBase }" @click="useKnowledgeBase = !useKnowledgeBase">
              <span class="mode-dot kb-dot"></span>
              <span>知识库</span>
              <span class="mode-on" v-if="useKnowledgeBase">ON</span>
            </div>
            <div class="mode-sep"></div>
            <el-button text size="small" @click="openFilePanel">
              <el-icon><Upload /></el-icon>
              上传资料
            </el-button>
            <el-button text size="small" @click="openImagePicker">
              <el-icon><Picture /></el-icon>
              识图
            </el-button>
            <input ref="imageInputRef" type="file" accept="image/*" style="display:none" @change="onImageSelected" />
          </div>

          <!-- 图片预览区 -->
          <div class="image-preview-bar" v-if="pendingImage">
            <div class="image-preview-item">
              <img :src="pendingImage.preview" alt="待识别图片" />
              <el-button class="image-remove-btn" :icon="Close" circle size="small" @click="removePendingImage" />
            </div>
            <span class="image-hint">图片已就绪，输入问题后发送即可识图</span>
          </div>

          <!-- 输入行 -->
          <div class="input-row">
            <el-button
              circle
              :type="isVoiceListening ? 'danger' : 'default'"
              class="voice-btn"
              @click="toggleVoiceInput"
              :title="isVoiceListening ? '停止语音输入' : '语音输入'"
            >
              <el-icon><Microphone /></el-icon>
            </el-button>
            <el-input
              ref="inputRef"
              v-model="inputText"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :placeholder="isVoiceListening ? '正在聆听...' : inputPlaceholder"
              resize="none"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.shift.enter="(e) => {}"
            />
            <el-button
              v-if="!isLoading"
              type="primary"
              :icon="Promotion"
              :disabled="!inputText.trim()"
              class="send-btn"
              @click="sendMessage"
            >发送</el-button>
            <el-button
              v-else
              type="danger"
              :icon="VideoPause"
              class="send-btn"
              @click="stopStreaming"
            >停止</el-button>
            <el-button
              type="info"
              class="test-btn"
              @click="testConnection"
              title="测试LLM连接"
            >
              <el-icon><Connection /></el-icon>
            </el-button>
          </div>

          <!-- 底部功能行 -->
          <div class="input-footer">
            <el-checkbox v-model="useKnowledgeBase" size="small" @change="() => {}">启用知识库检索</el-checkbox>
            <div class="footer-sep"></div>
            <el-button text size="small" @click="summarizeRequirements" :disabled="messages.length < 4" :loading="summarizing">
              <el-icon><Check /></el-icon>
              总结需求
            </el-button>
            <el-button text size="small" @click="goToCourseware" :disabled="messages.length === 0">
              <el-icon><Document /></el-icon>
              生成课件
            </el-button>
            <el-button text size="small" @click="addFilesToKnowledge" :disabled="uploadedFiles.length === 0">
              <el-icon><Collection /></el-icon>
              加入知识库
            </el-button>
          </div>
        </div>
      </main>

      <!-- ========== 右侧需求确认面板 ========== -->
      <aside class="req-panel" v-if="showRequirements">
        <div class="req-header">
          <h3>📋 课件生成需求</h3>
          <el-button :icon="Close" text @click="showRequirements = false" />
        </div>
        <el-form :model="requirements" label-position="top" class="req-form">
          <el-form-item label="教学主题">
            <el-input v-model="requirements.topic" placeholder="如：Python基础语法">
              <template #prefix><el-icon><Edit /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="学科">
            <el-select v-model="requirements.subject" filterable allow-create style="width:100%">
              <el-option v-for="subject in ['语文','数学','英语','物理','化学','生物','历史','地理','道德与法治','科学','信息科技','艺术','体育与健康']" :key="subject" :label="subject" :value="subject" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标受众">
            <el-select v-model="requirements.target_audience" style="width:100%">
              <el-option v-for="grade in ['一年级','二年级','三年级','四年级','五年级','六年级','七年级','八年级','九年级','高一','高二','高三']" :key="grade" :label="grade" :value="grade" />
            </el-select>
          </el-form-item>
          <el-form-item label="课时时长">
            <el-slider v-model="requirements.duration" :min="15" :max="180" :step="15" show-stops :marks="{15:'15分',45:'45分',90:'90分',180:'180分'}" />
            <span class="dur-label">{{ requirements.duration }} 分钟</span>
          </el-form-item>
          <el-form-item label="难度等级">
            <el-radio-group v-model="requirements.difficulty">
              <el-radio label="easy"><span class="diff easy">入门</span></el-radio>
              <el-radio label="medium"><span class="diff medium">中等</span></el-radio>
              <el-radio label="hard"><span class="diff hard">进阶</span></el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="核心知识点">
            <el-input v-model="requirements.key_points_text" type="textarea" :rows="2" placeholder="输入知识点，逗号分隔" />
          </el-form-item>
          <el-form-item label="生成内容">
            <div class="gen-toggles">
              <el-checkbox v-model="requirements.include_ppt">📊 PPT课件</el-checkbox>
              <el-checkbox v-model="requirements.include_word">📝 Word教案</el-checkbox>
            </div>
          </el-form-item>
        </el-form>
        <div class="req-actions">
          <el-button @click="showRequirements = false">继续对话</el-button>
          <el-button type="primary" @click="startGeneration">
            <el-icon><VideoPlay /></el-icon>
            进入生成中心
          </el-button>
        </div>
      </aside>

</div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, onBeforeUnmount, onActivated, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/store/app'
import { resolveApiBaseURL } from '@/api/baseUrl'
import { trackedFetch } from '@/api/dataFlow'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
// 按需注册语言，避免把 highlight.js 全部 190+ 语言打进包（原 ChatView 产物 1MB）
import hljs from '@/utils/highlight'
import { renderMathInText } from '@/utils/mathRender'
import 'katex/dist/katex.min.css'
import {
  Plus, Delete, ChatDotRound, ChatLineRound, Upload, Document,
  Close, Promotion, UploadFilled, VideoPlay, UserFilled, CopyDocument,
  Edit, Collection, Check, VideoPause, Bell, Cpu, Search, Microphone,
  RefreshRight, Setting, Connection, Picture
} from '@element-plus/icons-vue'

defineOptions({ name: 'ChatView' })

// 配置 marked
marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      try { return hljs.highlight(code, { language: lang }).value } catch {}
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true, gfm: true
})

const router = useRouter()
const store = useAppStore()

// ====== 状态 ======
const messagesRef = ref(null)
const inputRef = ref(null)
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const uploadedFiles = ref([])
const currentConversationId = ref(null)
const conversations = ref([])
const showRequirements = ref(false)
const isSpeaking = ref(false)
const autoSpeak = ref(false)
const isVoiceListening = ref(false)
const summarizing = ref(false)
const deepThinkingEnabled = ref(false)
const smartSearchEnabled = ref(false)

const useKnowledgeBase = ref(false)
const configHydrated = ref(false)

const CHAT_SESSION_KEY = 'a04_chat_session_v1'

function persistChatSession() {
  try {
    sessionStorage.setItem(CHAT_SESSION_KEY, JSON.stringify({
      messages: messages.value,
      conversations: conversations.value,
      currentConversationId: currentConversationId.value
    }))
  } catch (e) {
    console.warn('persist chat session', e)
  }
}

function restoreChatSession() {
  try {
    const raw = sessionStorage.getItem(CHAT_SESSION_KEY)
    if (!raw) return
    const d = JSON.parse(raw)
    if (Array.isArray(d.messages)) messages.value = d.messages
    if (Array.isArray(d.conversations) && d.conversations.length > 0) {
      conversations.value = d.conversations
    }
    if (d.currentConversationId !== undefined && d.currentConversationId !== null) {
      currentConversationId.value = d.currentConversationId
    }
  } catch (e) {
    console.warn('restore chat session', e)
  }
}

// 图片识图相关
const pendingImage = ref(null)       // { file, base64, preview }
const imageInputRef = ref(null)

let streamController = null

// ====== 模式切换（可同时开启） ======
function toggleDeepThinking() {
  deepThinkingEnabled.value = !deepThinkingEnabled.value
}

function toggleSmartSearch() {
  smartSearchEnabled.value = !smartSearchEnabled.value
}

// ====== 计算属性 ======
const inputPlaceholder = computed(() => {
  if (deepThinkingEnabled.value && smartSearchEnabled.value) return '深度思考+智能搜索：先搜索再深度分析...'
  if (deepThinkingEnabled.value) return '深度思考模式：输入复杂问题，获取深入分析...'
  if (smartSearchEnabled.value) return '智能搜索模式：输入关键词搜索相关内容...'

  return '输入您的教学需求，按 Enter 发送，Shift+Enter 换行...'
})

const providerStatusType = computed(() => {
  if (!configHydrated.value) return 'info'
  return store.config?.api_key_configured ? 'success' : 'warning'
})

const providerStatusText = computed(() => {
  if (!configHydrated.value) return '加载中'
  return store.config?.api_key_configured ? '已配置' : '演示模式'
})

// ====== 快捷功能 ======
const quickActions = [
  { icon: '📊', label: '设计教学课件', desc: 'PPT + 教案', action: 'courseware', topic: 'Python编程入门', audience: '大一新生', duration: 45 },
  { icon: '📝', label: '生成教案', desc: 'Word文档', action: 'courseware', topic: '高中数学"函数的概念"', audience: '高中生', duration: 45 },
  { icon: '🎬', label: '动画演示', desc: '交互动画', action: 'animation', topic: '光的折射原理', audience: '初中生', duration: 30 },
  { icon: '🎮', label: '互动游戏', desc: '课堂游戏', action: 'game', topic: '英语单词学习', audience: '初中生', duration: 20 },
  { icon: '✏️', label: '作业批改', desc: '智能评分', action: 'chat', prompt: '请帮我设计一份Python作业的自动批改标准' },
  { icon: '📚', label: '知识问答', desc: '答疑解惑', action: 'chat', prompt: '请解答：什么是递归算法？用Python如何实现？请给出详细解释和代码示例' },
]

const quickHints = [
  '设计Python入门课件',
  '生成计算机网络教案',
  '创建数据结构PPT',
  '解答算法时间复杂度',
]

// ====== 需求表单 ======
const requirements = reactive({
  topic: '',
  subject: '数学',
  target_audience: '七年级',
  duration: 45,
  difficulty: 'medium',
  key_points_text: '',
  include_ppt: true,
  include_word: true
})

// ====== 工具函数 ======
function scrollBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMessage(text) {
  if (!text) return ''
  // 分离深度思考和最终回答
  let hasThinking = false, thinkingPart = '', answerPart = text
  if (text.includes('## 思考过程') && text.includes('## 最终回答')) {
    hasThinking = true
    const parts = text.split('## 最终回答')
    thinkingPart = marked.parse(renderMathInText(parts[0].replace('## 思考过程', '').trim()))
    answerPart = parts[1] ? marked.parse(renderMathInText(parts[1].trim())) : ''
  } else {
    answerPart = marked.parse(renderMathInText(text))
  }
  // 代码块加复制按钮
  answerPart = answerPart.replace(/<pre><code class="([^"]*)">/g,
    '<pre class="code-block"><button class="copy-btn" onclick="window._copyCode(this)">复制</button><code class="$1">')
  answerPart = answerPart.replace(/<pre><code>/g,
    '<pre class="code-block"><button class="copy-btn" onclick="window._copyCode(this)">复制</button><code>')
  if (hasThinking) {
    thinkingPart = thinkingPart.replace(/<pre><code/g,
      '<pre class="code-block"><button class="copy-btn" onclick="window._copyCode(this)">复制</button><code')
    return `<div class="think-container">
      <div class="think-section" onclick="this.classList.toggle('collapsed')">
        <div class="think-hdr"><span>🧠 深度思考过程</span><span class="think-toggle">▼</span></div>
        <div class="think-body">${thinkingPart}</div>
      </div>
      <div class="answer-section">${answerPart}</div>
    </div>`
  }
  return answerPart
}

window._copyCode = function(btn) {
  const code = btn.nextElementSibling
  if (code && code.tagName === 'CODE') {
    navigator.clipboard.writeText(code.textContent).then(() => {
      btn.textContent = '已复制!'
      setTimeout(() => { btn.textContent = '复制' }, 2000)
    })
  }
}

// ====== 聊天核心 ======
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  // 新建会话
  if (!currentConversationId.value) {
    currentConversationId.value = 'conv_' + Date.now()
    conversations.value.unshift({ id: currentConversationId.value, title: '新对话' })
  }

  // 追加用户消息（如果有图片，附带图片预览）
  const hasImage = !!pendingImage.value
  const userMsgObj = { role: 'user', content: text, timestamp: new Date().toISOString() }
  if (hasImage) {
    userMsgObj.image_preview = pendingImage.value.preview
  }
  messages.value.push(userMsgObj)
  const userMsg = text
  const imageData = hasImage ? pendingImage.value.base64 : null
  inputText.value = ''
  if (hasImage) pendingImage.value = null
  isLoading.value = true
  scrollBottom()

  // 获取当前激活的提供商和模型，确保测试和实际对话使用同一个模型
  const activeProvider = store.config.providers?.find(p => p.is_active)
  const currentProvider = activeProvider?.provider || store.config.provider || 'demo'
  // 确保模型不为空，如果activeProvider.model为空，使用后端配置中的models[currentProvider]
  const currentModel = activeProvider?.model || store.config.models?.[currentProvider] || ''
  const commonPayload = {
    conversation_id: currentConversationId.value,
    use_knowledge: useKnowledgeBase.value,
    provider: currentProvider,
    model: currentModel,
    history: messages.value.slice(0, -1).map(({ role, content }) => ({ role, content })),
    attachment_ids: uploadedFiles.value.map(file => file.file_id).filter(Boolean)
  }

  // 确定端点和构建 payload（支持深度思考+智能搜索同时开启+识图）
  let endpoint = '/chat/stream'
  let payload = {}

  if (imageData) {
    // 有图片时优先使用视觉识图端点
    endpoint = '/chat/vision'
    payload = {
      message: userMsg,
      image_base64: imageData,
      ...commonPayload
    }
  } else if (deepThinkingEnabled.value && smartSearchEnabled.value) {
    // 两者同时开启：先搜索获取资料，再深度思考分析
    endpoint = '/chat/deep-search'
    payload = {
      message: userMsg,
      query: userMsg,
      engine: 'baidu',
      top_k: 5,
      ...commonPayload
    }
  } else if (smartSearchEnabled.value) {
    endpoint = '/chat/search'
    payload = {
      query: userMsg,
      engine: 'baidu',
      top_k: 5,
      ...commonPayload
    }
  } else if (deepThinkingEnabled.value) {
    endpoint = '/chat/deep-thinking'
    payload = {
      message: userMsg,
      ...commonPayload
    }
  } else {
    payload = {
      message: userMsg,
      ...commonPayload
    }
  }

  // 追加AI占位
  const aiIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', timestamp: new Date().toISOString(), is_streaming: true,
    is_thinking: deepThinkingEnabled.value, is_search: smartSearchEnabled.value })

  let fullContent = ''
  try {
    const resp = await trackedFetch(resolveApiBaseURL() + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const reader = resp.body.getReader()
    streamController = reader
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            if (d.content) { fullContent += d.content; messages.value[aiIdx].content = fullContent }
            if (d.done) { messages.value[aiIdx].is_streaming = false }
            if (d.followup_suggestions) { messages.value[aiIdx].followup_suggestions = d.followup_suggestions }
          } catch {}
        }
      }
      scrollBottom()
    }
    messages.value[aiIdx].is_streaming = false

    // 自动保存历史
    await saveHistory()

    // 自动朗读
    if (autoSpeak.value && fullContent) speakText(fullContent)

  } catch (e) {
    console.error('发送失败:', e)
    messages.value[aiIdx].content = `❌ 发送失败：${e.message}\n\n请检查：\n1. 后端是否已在 localhost:8005 启动\n2. LLM 配置是否正确\n3. 网络连接是否正常`
    messages.value[aiIdx].is_streaming = false
    ElMessage.error(`发送失败: ${e.message}`)
  } finally {
    isLoading.value = false
    streamController = null
    scrollBottom()
  }
}

// 使用后续建议
function useSuggestion(suggestion) {
  inputText.value = suggestion
  sendMessage()
}

function stopStreaming() {
  if (streamController) {
    streamController.cancel()
    streamController = null
    isLoading.value = false
    const last = messages.value[messages.value.length - 1]
    if (last?.is_streaming) {
      last.is_streaming = false
      last.content += '\n\n[已停止生成]'
    }
    ElMessage.info('已停止生成')
  }
}

async function saveHistory() {
  if (!currentConversationId.value || messages.value.length === 0) return
  try {
    const history = messages.value.map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp }))
    await trackedFetch(`${resolveApiBaseURL()}/chat/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: currentConversationId.value, history })
    })
    // 更新会话标题
    const firstUserMsg = messages.value.find(m => m.role === 'user')
    if (firstUserMsg) {
      const title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '')
      const conv = conversations.value.find(c => c.id === currentConversationId.value)
      if (conv) conv.title = title
    }
  } catch (e) { console.error('保存历史失败:', e) }
}

async function loadHistory(convId) {
  try {
    const resp = await trackedFetch(`${resolveApiBaseURL()}/chat/history?conversation_id=${convId}`)
    const data = await resp.json()
    if (data.success && data.history) {
      messages.value = data.history.map(m => ({
        ...m, is_streaming: false,
        is_thinking: false, is_search: false
      }))
    }
  } catch (e) { console.error('加载历史失败:', e) }
}

// ====== 会话管理 ======
async function createNewChat() {
  currentConversationId.value = null
  messages.value = []
  showRequirements.value = false
  inputText.value = ''
  inputRef.value?.focus()
}

async function selectConversation(convId) {
  currentConversationId.value = convId
  await loadHistory(convId)
  scrollBottom()
}

async function deleteConversation(convId) {
  try {
    await trackedFetch(`${resolveApiBaseURL()}/chat/history?conversation_id=${convId}`, { method: 'DELETE' })
  } catch {}
  const idx = conversations.value.findIndex(c => c.id === convId)
  if (idx > -1) conversations.value.splice(idx, 1)
  if (currentConversationId.value === convId) createNewChat()
}

function clearCurrentChat() {
  messages.value = []
  if (currentConversationId.value) {
    trackedFetch(`${resolveApiBaseURL()}/chat/history?conversation_id=${currentConversationId.value}`, { method: 'DELETE' })
  }
  ElMessage.success('已清空当前对话')
}

async function regenerateMsg(idx) {
  if (idx > 0 && messages.value[idx - 1]?.role === 'user') {
    const userMsg = messages.value[idx - 1].content
    messages.value.splice(idx, messages.value.length - idx)
    inputText.value = userMsg
    await sendMessage()
  }
}

// ====== 图片识图 ======
function openImagePicker() {
  if (imageInputRef.value) {
    imageInputRef.value.value = ''
    imageInputRef.value.click()
  }
}

function onImageSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 10MB')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const base64Full = reader.result
    const base64Data = base64Full.split(',')[1]
    pendingImage.value = {
      file,
      base64: base64Data,
      preview: base64Full
    }
  }
  reader.readAsDataURL(file)
}

function removePendingImage() {
  pendingImage.value = null
}

function previewFullImage(src) {
  window.open(src, '_blank')
}

// ====== 文件上传 ======
function openFilePanel() {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.accept = '.pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.mp4,.avi,.mov,.wmv,.mp3,.wav'
  input.onchange = async (e) => {
    for (const file of e.target.files) {
      try {
        const res = await store.uploadFile(file.raw || file)
        uploadedFiles.value.push(res)
        ElMessage.success(`${file.name} 上传成功`)
      } catch { ElMessage.error(`${file.name} 上传失败`) }
    }
    // 上传完成后提示AI关注参考资料
    if (uploadedFiles.value.length > 0) {
      const fileNames = uploadedFiles.value.map(f => f.filename || f.file_id).join('、')
      inputText.value = `我上传了以下参考资料：${fileNames}。请帮我分析这些资料的内容，并告诉我如何在课件中利用这些资料。`
    }
  }
  input.click()
}

function removeFile(fileId) {
  const idx = uploadedFiles.value.findIndex(f => f.file_id === fileId)
  if (idx > -1) uploadedFiles.value.splice(idx, 1)
}

async function addFilesToKnowledge() {
  for (const f of uploadedFiles.value) {
    try { await store.addToKnowledge(f.file_id) } catch {}
  }
  ElMessage.success('文件已加入知识库')
}

// ====== 语音 ======
function speakText(text) {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text.replace(/[#*`\[\]]/g, ''))
  u.lang = 'zh-CN'
  u.onstart = () => { isSpeaking.value = true }
  u.onend = u.onerror = () => { isSpeaking.value = false }
  window.speechSynthesis.speak(u)
}

function stopSpeaking() {
  window.speechSynthesis?.cancel()
  isSpeaking.value = false
}

function toggleAutoSpeak() {
  autoSpeak.value = !autoSpeak.value
  ElMessage.success(autoSpeak.value ? '已开启自动朗读' : '已关闭自动朗读')
}

// ====== 语音输入(STT) ======
let speechRecognition = null

function toggleVoiceInput() {
  if (isVoiceListening.value) {
    stopVoiceInput()
  } else {
    startVoiceInput()
  }
}

function startVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用Chrome浏览器')
    return
  }

  // 检查是否在安全上下文中（HTTPS或localhost）
  if (!window.isSecureContext) {
    ElMessage.warning('语音识别需要HTTPS环境或localhost访问，当前环境不支持')
    return
  }

  // 先请求麦克风权限
  navigator.mediaDevices.getUserMedia({ audio: true }).then(() => {
    _doStartVoiceInput(SpeechRecognition)
  }).catch((err) => {
    if (err.name === 'NotAllowedError') {
      ElMessage.error('麦克风权限被拒绝，请在浏览器设置中允许麦克风访问')
    } else if (err.name === 'NotFoundError') {
      ElMessage.error('未检测到麦克风设备，请连接麦克风后重试')
    } else {
      ElMessage.error('无法访问麦克风: ' + err.message)
    }
  })
}

function _doStartVoiceInput(SpeechRecognition) {
  speechRecognition = new SpeechRecognition()
  speechRecognition.lang = 'zh-CN'
  speechRecognition.continuous = true
  speechRecognition.interimResults = true

  speechRecognition.onstart = () => {
    isVoiceListening.value = true
    ElMessage.success('语音输入已开启，请说话...')
  }

  speechRecognition.onresult = (event) => {
    let finalText = ''
    let interimText = ''
    for (let i = 0; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript
      if (event.results[i].isFinal) {
        finalText += transcript
      } else {
        interimText += transcript
      }
    }
    inputText.value = finalText + interimText
  }

  speechRecognition.onerror = (event) => {
    if (event.error === 'not-allowed') {
      ElMessage.error('麦克风权限被拒绝，请在浏览器地址栏左侧点击锁图标，允许麦克风权限后重试')
    } else if (event.error === 'network') {
      ElMessage.error('语音识别网络错误，请检查网络连接')
    } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
      ElMessage.warning('语音识别: ' + event.error)
    }
    isVoiceListening.value = false
  }

  speechRecognition.onend = () => {
    isVoiceListening.value = false
  }

  speechRecognition.start()
}

function stopVoiceInput() {
  if (speechRecognition) {
    speechRecognition.stop()
    speechRecognition = null
  }
  isVoiceListening.value = false
}

// ====== 需求总结确认 ======
async function summarizeRequirements() {
  if (!currentConversationId.value) {
    ElMessage.warning('请先开始对话')
    return
  }
  summarizing.value = true
  try {
    const resp = await trackedFetch(resolveApiBaseURL() + '/chat/summarize-requirements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: currentConversationId.value })
    })
    const data = await resp.json()
    if (data.success && data.requirements) {
      const req = data.requirements
      // 构建总结文本作为AI消息展示
      let summaryText = '## 教学需求总结确认\n\n'
      if (req.topic) summaryText += `**教学主题**: ${req.topic}\n`
      if (req.target_audience) summaryText += `**目标受众**: ${req.target_audience}\n`
      if (req.duration) summaryText += `**课时时长**: ${req.duration}\n`
      if (req.difficulty) summaryText += `**难度级别**: ${req.difficulty}\n`
      if (req.key_points && req.key_points.length > 0) {
        summaryText += `**核心知识点**: ${req.key_points.join('、')}\n`
      }
      if (req.teaching_goals) {
        summaryText += '\n**教学目标**:\n'
        if (req.teaching_goals.knowledge) summaryText += `- 知识目标: ${req.teaching_goals.knowledge}\n`
        if (req.teaching_goals.ability) summaryText += `- 能力目标: ${req.teaching_goals.ability}\n`
        if (req.teaching_goals.emotion) summaryText += `- 情感目标: ${req.teaching_goals.emotion}\n`
      }
      if (req.output_requirements && req.output_requirements.length > 0) {
        summaryText += `\n**产出要求**: ${req.output_requirements.join('、')}\n`
      }
      if (req.missing_info && req.missing_info.length > 0) {
        summaryText += `\n**待补充信息**: ${req.missing_info.join('、')}\n`
      }
      if (req.completeness !== undefined) {
        summaryText += `\n**需求完整度**: ${Math.round(req.completeness * 100)}%\n`
      }
      summaryText += '\n> 如需修改，请继续对话补充；确认无误后点击"生成课件"开始生成。'
      
      messages.value.push({
        role: 'assistant',
        content: summaryText,
        timestamp: new Date().toISOString(),
        is_summary: true
      })
      scrollBottom()

      // 自动填充需求面板
      if (req.topic) requirements.topic = req.topic
      if (req.target_audience) requirements.target_audience = req.target_audience
      if (req.duration) requirements.duration = parseInt(req.duration) || 45
      if (req.difficulty) requirements.difficulty = req.difficulty
      if (req.key_points) requirements.key_points_text = req.key_points.join('，')

      ElMessage.success('需求总结已生成，请确认后点击"生成课件"')
    } else {
      ElMessage.error(data.message || '总结失败')
    }
  } catch (e) {
    ElMessage.error(`需求总结失败: ${e.message}`)
  } finally {
    summarizing.value = false
  }
}

// ====== 复制 ======
function copyMessage(content) {
  navigator.clipboard.writeText(content.replace(/<[^>]+>/g, ''))
  ElMessage.success('已复制到剪贴板')
}

// ====== 测试连接 ======
async function testConnection() {
  try {
    ElMessage.info('正在测试连接...')
    const resp = await trackedFetch(`${resolveApiBaseURL()}/llm/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: store.config?.llm_provider || 'demo', api_key: '', base_url: null })
    })
    const data = await resp.json()
    ElMessage.success(data.success ? `✅ 连接成功: ${data.message}` : `⚠️ ${data.message || '连接失败'}`)
  } catch (e) {
    ElMessage.error(`❌ 连接失败: ${e.message}`)
  }
}

// ====== 快捷输入 ======
function useQuickPrompt(prompt) {
  inputText.value = prompt
  nextTick(() => { inputRef.value?.focus() })
}

// ====== 快捷操作处理 ======
function handleQuickAction(action) {
  if (action.action === 'courseware') {
    // 跳转到课件生成页面
    router.push({
      path: '/courseware',
      query: {
        topic: action.topic || '',
        audience: action.audience || '大一新生',
        duration: action.duration || 45,
        include_ppt: true,
        include_word: true,
        include_animation: false,
        include_game: false
      }
    })
  } else if (action.action === 'animation') {
    // 跳转到动画创意页面
    router.push({
      path: '/animation',
      query: {
        topic: action.topic || '',
        audience: action.audience || '初中生',
        duration: action.duration || 30
      }
    })
  } else if (action.action === 'game') {
    // 跳转到互动游戏页面
    router.push({
      path: '/game',
      query: {
        topic: action.topic || '',
        audience: action.audience || '初中生',
        duration: action.duration || 20
      }
    })
  } else {
    // 填充聊天输入框
    useQuickPrompt(action.prompt)
  }
}

// ====== 课件生成 ======
function goToCourseware() {
  // 提取对话中的主题信息，传递到课件生成页面
  const lastUser = messages.value.filter(m => m.role === 'user').pop()
  const topic = lastUser ? lastUser.content.slice(0, 50) : ''
  router.push({
    path: '/courseware',
    query: topic ? { topic } : {}
  })
}

function showRequirementPanel() {
  const lastUser = messages.value.filter(m => m.role === 'user').pop()
  if (lastUser) requirements.topic = lastUser.content.slice(0, 50)
  showRequirements.value = true
}

async function startGeneration() {
  if (!requirements.topic) { ElMessage.warning('请填写教学主题'); return }
  router.push({
    path: '/courseware',
    query: {
      topic: requirements.topic,
      subject: requirements.subject,
      audience: requirements.target_audience,
      duration: requirements.duration,
      difficulty: requirements.difficulty,
      key_points: requirements.key_points_text,
      reference_files: uploadedFiles.value.map(file => file.file_id).filter(Boolean).join(','),
      reference_names: uploadedFiles.value.map(file => file.filename || file.file_id).join(','),
      include_ppt: requirements.include_ppt,
      include_word: requirements.include_word
    }
  })
}

function goSettings() { router.push('/settings') }

watch([messages, conversations, currentConversationId], () => {
  persistChatSession()
}, { deep: true })

// ====== 生命周期 ======
function cleanupSpeech() {
  window.speechSynthesis?.cancel()
  isSpeaking.value = false
}

onMounted(async () => {
  // 清理可能残留的语音播放
  cleanupSpeech()
  window.addEventListener('beforeunload', cleanupSpeech)

  restoreChatSession()

  await store.fetchConfig()
  configHydrated.value = true
  try {
    const data = await store.getConversations()
    if (data?.conversations?.length) {
      const merged = [...conversations.value]
      const seen = new Set(merged.map(c => c.id))
      for (const c of data.conversations) {
        if (!seen.has(c.id)) {
          merged.push(c)
          seen.add(c.id)
        } else {
          const local = merged.find(x => x.id === c.id)
          if (local && c.title && (local.title === '新对话' || !local.title)) {
            local.title = c.title
          }
        }
      }
      conversations.value = merged
    }
  } catch {}
  // 若有会话但本地无消息，从服务端拉取当前会话历史（或恢复后仅有余 id）
  if (conversations.value.length > 0 && messages.value.length === 0) {
    const cid = currentConversationId.value || conversations.value[0].id
    currentConversationId.value = cid
    await loadHistory(cid)
    scrollBottom()
  }
})

// keep-alive 激活时刷新会话列表
onActivated(async () => {
  try {
    await store.fetchConfig()
    const data = await store.getConversations()
    if (data?.conversations) conversations.value = data.conversations
  } catch {}
})

onBeforeUnmount(() => {
  persistChatSession()
  cleanupSpeech()
  stopVoiceInput()
  window.removeEventListener('beforeunload', cleanupSpeech)
})
</script>

<style lang="scss" scoped>
.chat-view {
  height: calc(100vh - 112px);
  overflow: hidden;
  background: var(--bg-dark, #0a0e27);
}

.chat-layout {
  display: flex;
  height: 100%;
  gap: 12px;
  padding: 12px;
}

/* ========== 侧边栏 ========== */
.chat-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(15, 20, 50, 0.95);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 14px;
  overflow: hidden;

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid rgba(0, 200, 255, 0.1);
  }

  .sidebar-logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
  }

  .conversation-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .conv-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 12px;
    border-radius: 8px;
    cursor: pointer;
    color: #b0b8c4;
    font-size: 13px;
    transition: all 0.2s;
    margin-bottom: 2px;

    &:hover { background: rgba(0,200,255,0.08); color: #fff; .conv-del { opacity: 1 } }
    &.active { background: rgba(0,200,255,0.15); color: var(--primary, #00c8ff) }
    .conv-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .conv-del { opacity: 0; transition: opacity 0.2s; color: #666; }
  }

  .empty-convs {
    display: flex; flex-direction: column; align-items: center;
    padding: 30px 0; color: #444; font-size: 12px;
    p { margin-top: 8px; }
  }

  .sidebar-footer {
    padding: 10px 12px;
    border-top: 1px solid rgba(0,200,255,0.1);
    display: flex;
    justify-content: flex-start;
  }
}

/* ========== 主聊天区 ========== */
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgba(12, 17, 45, 0.9);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 14px;
  overflow: hidden;
}

/* ========== 顶部栏 ========== */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(0,200,255,0.1);
  background: rgba(15,20,50,0.5);
  gap: 12px;
}

.dh-widget {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.dh-avatar {
  position: relative;
  flex-shrink: 0;
  cursor: default;
  svg { display: block; }
  .pulse-ring {
    position: absolute; inset: -5px;
    border: 2px solid #00c8ff; border-radius: 50%;
    animation: dh-pulse 1.4s ease-out infinite;
  }
  .status-lamp {
    position: absolute; bottom: 3px; right: 3px;
    width: 11px; height: 11px; border-radius: 50%;
    border: 2px solid #0a0e27;
    &.lamp-idle { background: #00ff88; }
    &.lamp-think { background: #ffcc00; animation: lamp-blink 0.8s infinite; }
    &.lamp-speak { background: #00c8ff; animation: lamp-blink 0.5s infinite; }
  }
}

.dh-info {
  .dh-name-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .dh-name { font-size: 14px; font-weight: 700; color: #fff; }
  .dh-status { font-size: 12px; margin-bottom: 6px; }
  .status-thinking { color: #ffcc00; .blink-dot { animation: lamp-blink 0.8s infinite; &::after { content: '·'; } } }
  .status-speaking { color: #00c8ff; }
  .status-ready { color: #00ff88; }
  .mode-tags { display: flex; gap: 5px; flex-wrap: wrap; }
  .mode-tag {
    font-size: 10px; padding: 2px 8px; border-radius: 10px;
    &.deep { background: rgba(255,204,0,0.15); color: #ffcc00; border: 1px solid rgba(255,204,0,0.3); }
    &.search { background: rgba(0,200,255,0.15); color: #00c8ff; border: 1px solid rgba(0,200,255,0.3); }
    &.teacher { background: rgba(255,107,107,0.15); color: #ff8080; border: 1px solid rgba(255,107,107,0.3); }
    &.kb { background: rgba(0,255,136,0.15); color: #00ff88; border: 1px solid rgba(0,255,136,0.3); }
  }
}

.voice-ctrl { display: flex; gap: 6px; align-items: center; }
.topbar-right { display: flex; gap: 8px; }

/* ========== 消息区域 ========== */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

/* 欢迎页 */
.welcome-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px 20px;
  .welcome-avatar-wrap {
    position: relative; width: 100px; height: 100px;
    display: flex; align-items: center; justify-content: center;
    .welcome-ring {
      position: absolute; inset: 0;
      border: 2px solid #00c8ff; border-radius: 50%;
      animation: dh-pulse 2s ease-out infinite;
    }
  }
  h2 { font-size: 20px; color: #fff; margin: 16px 0 8px; text-align: center; }
  .welcome-desc { font-size: 13px; color: #888; margin-bottom: 28px; text-align: center; }
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 100%;
  max-width: 600px;
  margin-bottom: 20px;
  .quick-card {
    display: flex; flex-direction: column; align-items: center;
    padding: 14px 8px; border-radius: 10px;
    background: rgba(20,25,60,0.8);
    border: 1px solid rgba(0,200,255,0.2);
    cursor: pointer; transition: all 0.2s; text-align: center;
    &:hover { background: rgba(0,200,255,0.12); border-color: #00c8ff; transform: translateY(-2px); }
    .qc-icon { font-size: 22px; margin-bottom: 4px; }
    .qc-label { font-size: 12px; font-weight: 600; color: #fff; }
    .qc-desc { font-size: 10px; color: #666; margin-top: 2px; }
  }
}

.welcome-hints {
  display: flex; flex-wrap: wrap; gap: 8px; justify-content: center;
  .hint-chip {
    padding: 6px 14px; border-radius: 20px; font-size: 12px;
    background: rgba(20,25,60,0.8); border: 1px solid rgba(0,200,255,0.2);
    color: #b0b8c4; cursor: pointer; transition: all 0.2s;
    &:hover { background: rgba(0,200,255,0.1); color: #00c8ff; border-color: #00c8ff; }
  }
}

/* 消息列表 */
.messages-list { display: flex; flex-direction: column; gap: 16px; }

.msg-wrapper {
  display: flex;
  gap: 12px;
  animation: msg-in 0.25s ease;

  &.user { flex-direction: row-reverse; .msg-bubble { background: linear-gradient(135deg,#0099cc,#0066aa); border: none; } }

  .msg-avatar { flex-shrink: 0; padding-top: 2px; }
  .avatar-circle {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
  }
  .user-circle { background: rgba(0,150,200,0.3); color: #00c8ff; border: 1px solid rgba(0,150,200,0.4); }
  .ai-circle { background: rgba(15,20,50,0.9); border: 1px solid rgba(0,200,255,0.3); }

  .msg-body { max-width: 72%; }

  .msg-mode-tag {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    background: rgba(255,204,0,0.15); color: #ffcc00;
    border: 1px solid rgba(255,204,0,0.3); margin-bottom: 6px;
    &.search-tag { background: rgba(0,200,255,0.15); color: #00c8ff; border-color: rgba(0,200,255,0.3); }
  }

  .msg-bubble {
    padding: 14px 18px; border-radius: 14px;
    background: rgba(18,23,60,0.95); border: 1px solid rgba(0,200,255,0.15);
    font-size: 13.5px; line-height: 1.7; color: #e0e6f0;
    word-break: break-word;
    :deep(pre.code-block) { background: rgba(5,8,25,0.95); border: 1px solid rgba(0,200,255,0.2); border-radius: 8px; padding: 14px; margin: 10px 0; overflow-x: auto; position: relative;
      .copy-btn { position: absolute; top: 6px; right: 8px; background: rgba(0,200,255,0.1); border: 1px solid rgba(0,200,255,0.3); border-radius: 4px; padding: 2px 8px; font-size: 11px; color: #00c8ff; cursor: pointer; opacity: 0; transition: opacity 0.2s; }
      &:hover .copy-btn { opacity: 1; }
    }
    :deep(code) { font-family: 'Consolas','Monaco',monospace; font-size: 13px; color: #e0e6f0; }
    :deep(p) { margin: 6px 0; }
    :deep(strong) { color: #fff; }
    :deep(em) { color: #00ff88; font-style: italic; }
    :deep(a) { color: #00c8ff; }
    :deep(h3) { font-size: 16px; color: #fff; margin: 14px 0 8px; border-bottom: 1px solid rgba(0,200,255,0.15); padding-bottom: 6px; }
    :deep(h4) { font-size: 14px; color: #00c8ff; margin: 10px 0 6px; }
    :deep(ul), :deep(ol) { padding-left: 20px; margin: 6px 0; li { margin: 4px 0; color: #d0d8e8; } }
    :deep(blockquote) { border-left: 3px solid #00c8ff; background: rgba(0,200,255,0.05); padding: 8px 12px; border-radius: 0 8px 8px 0; color: #b0b8c4; margin: 8px 0; }
    :deep(.math-block) { background: rgba(0,200,255,0.05); border: 1px solid rgba(0,200,255,0.2); border-radius: 6px; padding: 10px; text-align: center; color: #00ff88; margin: 10px 0; overflow-x: auto; }
    :deep(.math-inline) { background: rgba(0,255,136,0.08); padding: 1px 5px; border-radius: 3px; color: #00ff88; }
    :deep(.katex) { color: #00ff88; font-size: 1.05em; }
    :deep(.katex-display) { margin: 0; overflow-x: auto; overflow-y: hidden; }
    :deep(.katex .mord), :deep(.katex .mbin), :deep(.katex .mrel), :deep(.katex .mopen), :deep(.katex .mclose), :deep(.katex .mpunct) { color: #00ff88; }
    :deep(.katex .mfrac .frac-line) { border-bottom-color: #00ff88; }
    :deep(table) { border-collapse: collapse; width: 100%; margin: 10px 0; th,td { padding: 8px 12px; border: 1px solid rgba(0,200,255,0.15); } th { background: rgba(0,200,255,0.08); color: #fff; } }
    &.streaming { border-color: rgba(0,200,255,0.4); }
  }

  /* 深度思考容器 */
  :deep(.think-container) { display: flex; flex-direction: column; gap: 10px; }
  :deep(.think-section) {
    background: rgba(20,25,50,0.6); border: 1px solid rgba(255,204,0,0.2); border-radius: 10px; overflow: hidden;
    .think-hdr { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; cursor: pointer; color: #ffcc00; font-size: 13px; font-weight: 600; }
    .think-toggle { font-size: 11px; transition: transform 0.2s; }
    .think-body { padding: 0 14px 12px; font-size: 12.5px; color: #b0b8c4; border-top: 1px solid rgba(255,204,0,0.1); }
    &.collapsed { .think-body { display: none; } .think-toggle { transform: rotate(-90deg); } }
  }
  :deep(.answer-section) {
    background: rgba(0,200,255,0.04); border: 1px solid rgba(0,200,255,0.15); border-radius: 10px; padding: 12px 14px;
  }

  .msg-footer {
    display: flex; align-items: center; gap: 10px; margin-top: 6px;
    .msg-time { font-size: 11px; color: #555; }
    .msg-ops { display: flex; gap: 4px; }
  }

  .ai-disclaimer {
    display: flex; align-items: center; gap: 5px; margin-top: 6px;
    font-size: 11px; color: #888; opacity: 0.75;
    .disclaimer-icon { font-size: 13px; color: #aaa; }
  }
  .followup-suggestions {
    margin-top: 8px;
    .followup-chips {
      display: flex; flex-wrap: wrap; gap: 6px;
    }
    .followup-chip {
      display: inline-block; padding: 5px 12px; font-size: 12px;
      color: #00c8ff; background: rgba(0,200,255,0.08);
      border: 1px solid rgba(0,200,255,0.25); border-radius: 16px;
      cursor: pointer; transition: all 0.2s;
      &:hover { background: rgba(0,200,255,0.18); border-color: rgba(0,200,255,0.5); }
    }
  }
}

.typing-dots {
  display: flex; align-items: center; gap: 5px; padding: 14px 18px;
  span { width: 7px; height: 7px; border-radius: 50%; background: #00c8ff; animation: typing 1.2s infinite;
    &:nth-child(1) { animation-delay: -0.32s } &:nth-child(2) { animation-delay: -0.16s } }
}

/* ========== 输入区域 ========== */
.input-area {
  padding: 12px 16px 14px;
  border-top: 1px solid rgba(0,200,255,0.1);
  background: rgba(12,17,45,0.98);
}

.uploaded-files {
  display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px;
  .file-chip { display: flex; align-items: center; gap: 5px; padding: 3px 10px; background: rgba(0,200,255,0.08); border: 1px solid rgba(0,200,255,0.2); border-radius: 20px; font-size: 12px; color: #00c8ff; }
}

.mode-row {
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap;
  .mode-btn {
    display: flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 16px;
    font-size: 12px; color: #888; border: 1px solid rgba(255,255,255,0.08); cursor: pointer; transition: all 0.2s; background: transparent;
    .mode-dot { width: 6px; height: 6px; border-radius: 50%; background: #555; }
    &.active { border-color: currentColor; color: #fff; }
    &.active .deep-dot { background: #ffcc00 } &.active .search-dot { background: #00c8ff } &.active .teacher-dot { background: #ff8080 } &.active .kb-dot { background: #00ff88 }
    .mode-on { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 8px; background: rgba(255,255,255,0.1); }
  }
  .mode-sep { flex: 1 }
}

.image-preview-bar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px; padding: 8px 10px;
  background: rgba(0,200,255,0.05); border: 1px dashed rgba(0,200,255,0.25); border-radius: 10px;
  .image-preview-item {
    position: relative; width: 64px; height: 64px; border-radius: 8px; overflow: hidden; flex-shrink: 0;
    img { width: 100%; height: 100%; object-fit: cover; border-radius: 8px; }
    .image-remove-btn { position: absolute; top: -4px; right: -4px; width: 20px !important; height: 20px !important; min-height: 20px !important; background: rgba(0,0,0,0.7); border: none; color: #ff6b6b; }
  }
  .image-hint { font-size: 12px; color: #888; }
}

.msg-image {
  margin-bottom: 8px; max-width: 280px;
  img { width: 100%; border-radius: 8px; cursor: pointer; border: 1px solid rgba(0,200,255,0.15); transition: transform 0.2s;
    &:hover { transform: scale(1.02); }
  }
}

.input-row {
  display: flex; align-items: flex-end; gap: 8px; margin-bottom: 8px;
  .el-textarea { flex: 1; :deep(.el-textarea__inner) { background: rgba(15,20,50,0.9) !important; border: 1px solid rgba(0,200,255,0.25) !important; color: #fff !important; border-radius: 12px; } }
  .send-btn { height: 36px; padding: 0 18px; border-radius: 12px; font-size: 14px; font-weight: 600; }
  .test-btn { height: 36px; border-radius: 12px; }
  .voice-btn { flex-shrink: 0; &.el-button--danger { animation: voicePulse 1s ease-in-out infinite; } }
}
@keyframes voicePulse { 0%,100%{box-shadow:0 0 0 0 rgba(245,108,108,0.4)} 50%{box-shadow:0 0 0 8px rgba(245,108,108,0)} }

.input-footer {
  display: flex; align-items: center; gap: 10px; font-size: 12px; color: #666;
  .footer-sep { flex: 1 }
}

/* ========== 需求面板 ========== */
.req-panel {
  width: 300px; flex-shrink: 0; display: flex; flex-direction: column;
  background: rgba(15,20,50,0.95); border: 1px solid rgba(0,200,255,0.15); border-radius: 14px; overflow: hidden;
  .req-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid rgba(0,200,255,0.1);
    h3 { font-size: 14px; color: #fff; } }
  .req-form { flex: 1; overflow-y: auto; padding: 12px 16px;
    :deep(.el-form-item__label) { color: #b0b8c4; font-size: 13px; }
    :deep(.el-input__wrapper) { background: rgba(5,8,25,0.8) !important; }
  }
  .dur-label { display: block; text-align: center; color: #00c8ff; font-size: 13px; margin-top: 4px; }
  .diff { padding: 2px 8px; border-radius: 10px; font-size: 12px; &.easy { background: rgba(0,255,136,0.15); color: #00ff88; } &.medium { background: rgba(255,204,0,0.15); color: #ffcc00; } &.hard { background: rgba(255,107,107,0.15); color: #ff8080; } }
  .gen-toggles { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .req-actions { padding: 12px 16px; border-top: 1px solid rgba(0,200,255,0.1); display: flex; gap: 8px; justify-content: flex-end; }
}

/* ========== 动画 ========== */
@keyframes msg-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes dh-pulse { 0% { transform: scale(0.9); opacity: 0.8; } 100% { transform: scale(1.6); opacity: 0; } }
@keyframes lamp-blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
@keyframes typing { 0%,80%,100% { transform: scale(0.6); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }

/* ========== 滚动条 ========== */
.messages-container, .conversation-list, .req-form {
  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: rgba(0,200,255,0.2); border-radius: 3px; }
  &::-webkit-scrollbar-thumb:hover { background: rgba(0,200,255,0.4); }
}

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .chat-layout { flex-direction: column; }
  .chat-sidebar { width: 100%; height: 160px; }
  .req-panel { width: 100%; }
  .quick-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
