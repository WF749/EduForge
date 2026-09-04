<template>
  <div class="voice-input">
    <el-button
      :icon="Microphone"
      class="voice-btn"
      :class="{ recording: isRecording, processing: isProcessing }"
      circle
      @click="toggleRecording"
      @keydown="handleKeydown"
    />

    <!-- 录音状态指示器 -->
    <div v-if="isRecording" class="recording-indicator">
      <div class="recording-dot"></div>
      <span>{{ recordingDuration }}s</span>
    </div>

    <!-- 音频波形可视化 -->
    <div v-if="isRecording || isProcessing" class="waveform">
      <div
        v-for="i in 20"
        :key="i"
        class="wave-bar"
        :style="{ animationDelay: `${i * 0.05}s` }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone } from '@element-plus/icons-vue'

const emit = defineEmits(['transcript', 'error'])

const isRecording = ref(false)
const isProcessing = ref(false)
const recordingDuration = ref(0)

let mediaRecorder = null
let audioContext = null
let analyser = null
let animationId = null
let timer = null
let activeRecognition = null

async function toggleRecording() {
  if (isRecording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

async function startRecording() {
  try {
    // 检查浏览器支持
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      ElMessage.warning('您的浏览器不支持语音录制')
      emit('error', '浏览器不支持语音录制')
      return
    }

    // 请求麦克风权限
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream)
    
    // 设置音频分析
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    analyser = audioContext.createAnalyser()
    const source = audioContext.createMediaStreamSource(stream)
    source.connect(analyser)
    analyser.fftSize = 256

    // 开始录制
    mediaRecorder.start()
    isRecording.value = true
    recordingDuration.value = 0

    // 计时器
    timer = setInterval(() => {
      recordingDuration.value++
      // 最长录制60秒
      if (recordingDuration.value >= 60) {
        stopRecording()
      }
    }, 1000)

    // 监听数据
    mediaRecorder.ondataavailable = async (event) => {
      isProcessing.value = true
      const audioBlob = event.data

      try {
        // 使用Web Speech API进行语音识别
        const transcript = await speechToText(audioBlob)
        emit('transcript', transcript)
      } catch (error) {
        console.error('语音识别失败:', error)
        emit('error', error.message)
      } finally {
        isProcessing.value = false
        // 清理
        stream.getTracks().forEach(track => track.stop())
        if (audioContext) {
          audioContext.close()
        }
      }
    }

    ElMessage.success('开始录音')

  } catch (error) {
    console.error('录音失败:', error)
    ElMessage.error('无法访问麦克风，请检查权限设置')
    emit('error', error.message)
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  isRecording.value = false
  
  if (timer) {
    clearInterval(timer)
    timer = null
  }

  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
}

// 使用Web Speech API进行语音识别
function speechToText(audioBlob) {
  return new Promise((resolve, reject) => {
    // 检查浏览器支持
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      reject(new Error('浏览器不支持语音识别'))
      return
    }

    const recognition = new SpeechRecognition()
    activeRecognition = recognition
    recognition.lang = 'zh-CN' // 中文
    recognition.continuous = true
    recognition.interimResults = false

    let finalTranscript = ''

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalTranscript += transcript
        }
      }
    }

    recognition.onerror = (event) => {
      reject(new Error(event.error))
    }

    recognition.onend = () => {
      if (finalTranscript) {
        resolve(finalTranscript)
      } else {
        reject(new Error('未能识别语音内容'))
      }
    }

    // 启动识别
    recognition.start()

    // 设置超时
    setTimeout(() => {
      recognition.stop()
    }, recordingDuration.value * 1000 || 10000)
  })
}

function handleKeydown(event) {
  // 支持空格键开始/结束录音
  if (event.code === 'Space') {
    event.preventDefault()
    toggleRecording()
  }
}

onUnmounted(() => {
  stopRecording()
  if (activeRecognition) {
    try { activeRecognition.abort() } catch {}
    activeRecognition = null
  }
})
</script>

<style lang="scss" scoped>
.voice-input {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.voice-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  transition: all 0.3s ease;

  &.recording {
    background: #f56c6c;
    border-color: #f56c6c;
    color: white;
    animation: pulse-recording 1s infinite;

    &:hover {
      background: #f78989;
      border-color: #f78989;
    }
  }

  &.processing {
    background: var(--primary);
    border-color: var(--primary);
    color: white;
  }
}

@keyframes pulse-recording {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.7);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 0 10px rgba(245, 108, 108, 0);
  }
}

.recording-indicator {
  position: absolute;
  top: -30px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(245, 108, 108, 0.9);
  border-radius: 12px;
  color: white;
  font-size: 12px;
  white-space: nowrap;
}

.recording-dot {
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.waveform {
  position: absolute;
  bottom: -20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 2px;
  height: 20px;
  align-items: center;
}

.wave-bar {
  width: 3px;
  background: var(--primary);
  border-radius: 2px;
  animation: wave 0.5s ease-in-out infinite alternate;
}

@keyframes wave {
  0% { height: 4px; }
  100% { height: 16px; }
}
</style>
