import { computed, onBeforeUnmount, ref } from 'vue'

/**
 * 语音能力：把"说话输入"和"读出来"收在一处。
 *
 * 为什么要抽出来：这两件事在 ChatView 里各自内联了一份（STT 80 行 / TTS 10 行），
 * 新的备课对话要用，不可能再抄一遍 —— 抄一份就多一处会各自漂移的实现。
 *
 * 关于"多模态"：语音输入是本项目的第四种输入模态（文本 / 文件 / 图片 / 语音），
 * 但它有两个**硬性前提**，必须如实告知而不是默默失败：
 *   1. 浏览器要支持 Web Speech API（目前主要 Chrome 系）；
 *   2. 必须是安全上下文（HTTPS 或 localhost），否则直接没有麦克风权限。
 * 所以 sttSupported / ttsSupported 对外可见，调用方据此决定要不要显示按钮。
 *
 * 刻意不做：不做"自动朗读开关"这类策略，策略留给调用方（ChatView 有 autoSpeak，
 * 备课对话不需要），这里只提供能力。
 */

/** 把麦克风/识别的错误码翻成教师看得懂的一句话。纯函数，可单测。 */
export function describeSttError(nameOrCode) {
  const key = String(nameOrCode || '').toLowerCase()
  switch (key) {
    case 'notallowederror':
    case 'not-allowed':
    case 'permission-denied':
      return '麦克风权限被拒绝，请在浏览器地址栏左侧点击锁图标，允许麦克风后重试'
    case 'notfounderror':
    case 'not-found':
      return '未检测到麦克风设备，请连接麦克风后重试'
    case 'network':
      return '语音识别网络错误，请检查网络连接'
    case 'no-speech':
      return '没有听到声音，请再说一次'
    case 'aborted':
      return '' // 用户自己停的，不需要提示
    case 'audio-capture':
      return '麦克风被其他程序占用，请关闭后重试'
    case 'service-not-allowed':
      return '语音识别服务不可用，请换 Chrome 浏览器试试'
    default:
      return key ? `语音识别出错：${key}` : ''
  }
}

/** 去掉 Markdown 标记，朗读时才不会念出"井号""星号" */
export function stripForSpeech(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, '（代码块已跳过）')
    .replace(/[#*`_>[\]()]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function useSpeech() {
  const listening = ref(false)
  const speaking = ref(false)
  // 读一次就够：API 存在性不会在会话中途变化
  const SpeechRecognitionImpl =
    typeof window !== 'undefined'
      ? (window.SpeechRecognition || window.webkitSpeechRecognition || null)
      : null
  const sttSupported = computed(
    () => Boolean(SpeechRecognitionImpl) && Boolean(window.isSecureContext)
  )
  const ttsSupported = computed(() => typeof window !== 'undefined' && Boolean(window.speechSynthesis))

  let rec = null

  /**
   * 开始听写。
   * @param {object} opts
   * @param {(text: string, isFinal: boolean) => void} opts.onText 实时回灌（含中间结果）
   * @param {(msg: string, code: string) => void} [opts.onError] 面向用户的中文提示。
   *   code 为 'unsupported' / 'insecure' 时是环境不支持（不是用户的错，适合 warning），
   *   其余是操作失败（适合 error），由调用方决定提示级别。
   */
  function startListening({ onText, onError } = {}) {
    if (listening.value) return
    if (!SpeechRecognitionImpl) {
      onError?.('当前浏览器不支持语音识别，请使用 Chrome 浏览器', 'unsupported')
      return
    }
    if (!window.isSecureContext) {
      onError?.('语音识别需要 HTTPS 环境或 localhost 访问，当前环境不支持', 'insecure')
      return
    }

    // 先要权限再开识别：否则用户会在"已经显示正在听"之后才被弹窗打断
    navigator.mediaDevices.getUserMedia({ audio: true }).then(() => {
      rec = new SpeechRecognitionImpl()
      rec.lang = 'zh-CN'
      rec.continuous = true
      rec.interimResults = true

      rec.onstart = () => { listening.value = true }
      rec.onresult = (event) => {
        let finalText = ''
        let interimText = ''
        for (let i = 0; i < event.results.length; i++) {
          const t = event.results[i][0].transcript
          if (event.results[i].isFinal) finalText += t
          else interimText += t
        }
        onText?.(finalText + interimText, false)
      }
      rec.onerror = (event) => {
        const code = String(event?.error || '')
        const msg = describeSttError(code)
        listening.value = false
        if (msg) onError?.(msg, code)
      }
      rec.onend = () => { listening.value = false }

      rec.start()
    }).catch((err) => {
      const code = String(err?.name || '')
      const msg = describeSttError(code)
      if (msg) onError?.(msg, code)
    })
  }

  function stopListening() {
    try { rec?.stop() } catch { /* 已经停了就算了 */ }
    rec = null
    listening.value = false
  }

  function toggleListening(opts) {
    listening.value ? stopListening() : startListening(opts)
  }

  function speak(text) {
    const clean = stripForSpeech(text)
    if (!clean || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(clean)
    u.lang = 'zh-CN'
    u.onstart = () => { speaking.value = true }
    u.onend = u.onerror = () => { speaking.value = false }
    window.speechSynthesis.speak(u)
  }

  function stopSpeaking() {
    try { window.speechSynthesis?.cancel() } catch { /* ignore */ }
    speaking.value = false
  }

  // 组件卸载时必须停掉：不停的话麦克风指示灯一直亮着，教师会以为被监听
  onBeforeUnmount(() => {
    stopListening()
    stopSpeaking()
  })

  return {
    listening, speaking, sttSupported, ttsSupported,
    startListening, stopListening, toggleListening,
    speak, stopSpeaking
  }
}
