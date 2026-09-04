<template>
  <div class="speech-synthesis" v-if="supported">
    <el-slider
      v-model="volume"
      :min="0"
      :max="100"
      :show-tooltip="false"
      @change="setVolume"
    />
    <el-button
      :icon="isSpeaking ? VideoPause : VideoPlay"
      circle
      :disabled="!text"
      @click="toggleSpeech"
    />
    <el-button
      :icon="isPaused ? VideoPlay : VideoPause"
      circle
      :disabled="!isSpeaking"
      @click="pauseSpeech"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'

const props = defineProps({
  text: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['start', 'end', 'error'])

const supported = ref('speechSynthesis' in window)
const isSpeaking = ref(false)
const isPaused = ref(false)
const volume = ref(100)

let utterance = null

function speak(text) {
  if (!supported.value) {
    emit('error', '浏览器不支持语音合成')
    return
  }

  // 停止之前的语音
  stop()

  utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN' // 中文
  utterance.rate = 1.0 // 语速
  utterance.pitch = 1.0 // 音调
  utterance.volume = volume.value / 100

  // 选择中文语音
  const voices = speechSynthesis.getVoices()
  const chineseVoice = voices.find(v => v.lang.includes('zh'))
  if (chineseVoice) {
    utterance.voice = chineseVoice
  }

  utterance.onstart = () => {
    isSpeaking.value = true
    isPaused.value = false
    emit('start')
  }

  utterance.onend = () => {
    isSpeaking.value = false
    isPaused.value = false
    emit('end')
  }

  utterance.onerror = (event) => {
    isSpeaking.value = false
    isPaused.value = false
    emit('error', event.error)
  }

  speechSynthesis.speak(utterance)
}

function toggleSpeech() {
  if (isSpeaking.value) {
    stop()
  } else if (props.text) {
    speak(props.text)
  }
}

function pauseSpeech() {
  if (isSpeaking.value) {
    if (isPaused.value) {
      speechSynthesis.resume()
      isPaused.value = false
    } else {
      speechSynthesis.pause()
      isPaused.value = true
    }
  }
}

function stop() {
  speechSynthesis.cancel()
  isSpeaking.value = false
  isPaused.value = false
}

function setVolume(value) {
  volume.value = value
  if (utterance) {
    utterance.volume = value / 100
  }
}

// 监听文本变化
watch(() => props.text, (newText) => {
  if (newText && !isSpeaking.value) {
    // 可选：自动播放
  }
})

onUnmounted(() => {
  stop()
})
</script>

<style lang="scss" scoped>
.speech-synthesis {
  display: flex;
  align-items: center;
  gap: 8px;

  .el-slider {
    width: 100px;
  }

  .el-button {
    width: 36px;
    height: 36px;
  }
}
</style>
