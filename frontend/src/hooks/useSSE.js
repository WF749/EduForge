/**
 * SSE连接Hook - Vue3专用SSE实时推送连接管理
 * 
 * 功能：
 * 1. 自动连接/断开SSE流
 * 2. 消息监听与解析
 * 3. 自动重连机制
 * 4. 连接状态管理
 * 
 * 使用示例:
 * ```javascript
 * import { useSSE } from '@/hooks/useSSE'
 * 
 * const { 
 *   connect,      // 连接SSE
 *   disconnect,   // 断开连接
 *   status,       // 连接状态
 *   lastMessage,  // 最后收到的消息
 *   error         // 错误信息
 * } = useSSE()
 * 
 * // 连接
 * connect('/api/courseware/sse/' + taskId)
 * 
 * // 监听消息
 * watch(lastMessage, (msg) => {
 *   if (msg.type === 'progress') {
 *     progress.value = msg.progress
 *   }
 * })
 * ```
 */

import { ref, onUnmounted, readonly } from 'vue'

// SSE消息类型
export const MessageType = {
  PROGRESS: 'progress',      // 进度更新
  STAGE_START: 'stage_start', // 阶段开始
  STAGE_COMPLETE: 'stage_complete', // 阶段完成
  PREVIEW_UPDATE: 'preview_update', // 预览更新
  ERROR: 'error',            // 错误
  COMPLETED: 'completed',    // 完成
  HEARTBEAT: 'heartbeat'    // 心跳
}

// 阶段名称映射
export const StageNames = {
  init: '初始化',
  requirements_parsing: '需求解析',
  outline_generation: '大纲生成',
  content_generation: '内容生成',
  style_rendering: '样式渲染',
  file_generation: '文件生成',
  validation: '校验',
  completed: '完成'
}

export function useSSE(options = {}) {
  // 配置
  const config = {
    reconnect: true,        // 是否自动重连
    reconnectInterval: 3000, // 重连间隔(ms)
    maxReconnectAttempts: 5, // 最大重连次数
    heartbeatTimeout: 10000,  // 心跳超时(ms)
    ...options
  }

  // 状态
  const status = ref('disconnected') // disconnected | connecting | connected | error
  const lastMessage = ref(null)
  const error = ref(null)
  const reconnectAttempts = ref(0)
  const isManualClose = ref(false)

  // 内部变量
  let eventSource = null
  let heartbeatTimer = null
  let reconnectTimer = null

  // 解析SSE消息
  function parseMessage(dataStr) {
    try {
      const data = JSON.parse(dataStr)
      return data
    } catch (e) {
      console.error('SSE消息解析失败:', e)
      return null
    }
  }

  // 连接SSE
  function connect(url) {
    if (eventSource) {
      disconnect()
    }

    isManualClose.value = false
    status.value = 'connecting'
    error.value = null

    try {
      eventSource = new EventSource(url)

      // 连接成功
      eventSource.onopen = () => {
        status.value = 'connected'
        reconnectAttempts.value = 0
        error.value = null
        resetHeartbeat()
        console.log('SSE连接已建立')
      }

      // 消息处理
      eventSource.onmessage = (event) => {
        resetHeartbeat()

        const data = parseMessage(event.data)
        if (data) {
          lastMessage.value = data
          
          // 根据消息类型处理
          if (data.type === MessageType.ERROR) {
            error.value = data.error
            status.value = 'error'
          } else if (data.type === MessageType.COMPLETED) {
            lastMessage.value = data
            handleCompleted(data)
          } else if (data.type === '[DONE]') {
            // 连接结束标记
            handleCompleted()
          }
        }
      }

      // 错误处理
      eventSource.onerror = (e) => {
        console.error('SSE错误:', e)
        
        if (status.value === 'connected') {
          // 连接中断，尝试重连
          status.value = 'error'
          error.value = '连接中断'
          attemptReconnect(url)
        } else {
          status.value = 'error'
          error.value = '无法连接到服务器'
        }
      }

    } catch (e) {
      console.error('SSE连接失败:', e)
      status.value = 'error'
      error.value = e.message || '连接失败'
    }
  }

  // 断开连接
  function disconnect() {
    isManualClose.value = true
    clearTimers()
    
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    
    status.value = 'disconnected'
    console.log('SSE连接已断开')
  }

  // 尝试重连
  function attemptReconnect(url) {
    if (!config.reconnect || isManualClose.value) {
      return
    }

    if (reconnectAttempts.value >= config.maxReconnectAttempts) {
      console.error('达到最大重连次数，停止重连')
      error.value = '连接失败，请刷新页面重试'
      return
    }

    reconnectAttempts.value++
    console.log(`尝试重连 (${reconnectAttempts.value}/${config.maxReconnectAttempts})...`)

    reconnectTimer = setTimeout(() => {
      connect(url)
    }, config.reconnectInterval)
  }

  // 重置心跳计时器
  function resetHeartbeat() {
    clearTimeout(heartbeatTimer)
    heartbeatTimer = setTimeout(() => {
      if (status.value === 'connected') {
        console.warn('SSE心跳超时，断开连接')
        status.value = 'error'
        error.value = '连接超时'
        disconnect()
      }
    }, config.heartbeatTimeout)
  }

  // 清除所有计时器
  function clearTimers() {
    clearTimeout(heartbeatTimer)
    clearTimeout(reconnectTimer)
  }

  // 处理完成
  function handleCompleted(data) {
    disconnect()
    console.log('SSE任务完成', data)
  }

  // 手动发送消息（用于测试）
  function sendTestMessage(message) {
    lastMessage.value = message
  }

  // 组件卸载时清理
  onUnmounted(() => {
    disconnect()
  })

  return {
    // 状态（只读）
    status: readonly(status),
    lastMessage: readonly(lastMessage),
    error: readonly(error),
    reconnectAttempts: readonly(reconnectAttempts),
    
    // 方法
    connect,
    disconnect,
    sendTestMessage,
    
    // 消息类型常量
    MessageType
  }
}

/**
 * 课件生成SSE Hook - 专门用于课件生成进度
 */
export function useCoursewareGeneration(onProgress, onComplete, onError) {
  const sse = useSSE()
  
  // 生成的页面列表
  const pages = ref([])
  
  // 当前进度
  const progress = ref(0)
  
  // 当前阶段
  const currentStage = ref('init')
  
  // 阶段进度
  const stageProgress = ref(0)
  
  // 预览数据
  const previewData = ref(null)
  
  // 监听消息
  const stopWatch = watch(sse.lastMessage, (msg) => {
    if (!msg) return
    
    switch (msg.type) {
      case MessageType.PROGRESS:
        progress.value = msg.progress || 0
        currentStage.value = msg.stage || 'init'
        stageProgress.value = msg.stage_progress || 0
        previewData.value = msg.preview_data
        
        // 调用回调
        onProgress && onProgress({
          progress: msg.progress,
          stage: msg.stage,
          stageName: msg.stage_name,
          stageProgress: msg.stage_progress,
          message: msg.message,
          previewData: msg.preview_data
        })
        break
      
      case MessageType.PREVIEW_UPDATE:
        // 更新页面预览
        const pageIndex = msg.page_index
        const pageData = msg.page_data
        
        if (pageIndex && pageData) {
          // 确保数组有足够的元素
          while (pages.value.length < pageIndex) {
            pages.value.push(null)
          }
          pages.value[pageIndex - 1] = pageData
        }
        break
      
      case MessageType.STAGE_START:
        currentStage.value = msg.stage
        stageProgress.value = 0
        break
      
      case MessageType.COMPLETED:
        // 生成完成
        sse.disconnect()
        onComplete && onComplete({
          result: msg.result,
          pages: pages.value
        })
        break
      
      case MessageType.ERROR:
        sse.disconnect()
        onError && onError({
          error: msg.error,
          details: msg.error_details
        })
        break
    }
  }, { immediate: true })

  // 组件卸载时清理
  onUnmounted(() => {
    stopWatch()
    sse.disconnect()
  })

  return {
    ...sse,
    pages,
    progress,
    currentStage,
    stageProgress,
    previewData
  }
}

// 辅助函数 - watch
function watch(source, cb, options = {}) {
  let oldValue = options.immediate ? undefined : typeof source.value === 'object' ? {...source.value} : source.value
  
  const unwatch = setInterval(() => {
    const newValue = source.value
    if (JSON.stringify(newValue) !== JSON.stringify(oldValue)) {
      const old = oldValue
      oldValue = typeof newValue === 'object' ? {...newValue} : newValue
      cb(newValue, old)
    }
  }, 50)
  
  // 返回停止函数
  return () => clearInterval(unwatch)
}
