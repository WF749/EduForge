<template>
  <canvas ref="canvasRef" class="particle-canvas" aria-hidden="true"></canvas>
</template>

<script setup>
/**
 * 轻量粒子背景。
 *
 * 重写原因：原实现是"比赛演示级"效果，却是全站卡顿的元凶——它挂在 App.vue 上，
 * 每个页面都在跑。主要开销：
 *   1) O(n²) 连接线计算（150 粒子 => 每帧约 1.1 万次配对 + sqrt）
 *   2) 每条线、每个粒子每帧都新建 createLinearGradient / createRadialGradient，
 *      60fps 下每秒产生数十万个临时对象，GC 压力极大
 *   3) drawCore 用 Math.random() 决定是否绘制，每帧随机闪烁
 *   4) 标签页切到后台仍全速运行
 *
 * 优化策略（保留观感，去掉浪费）：
 *   - 粒子数按面积自适应并大幅下调
 *   - 连接线用纯色 stroke（alpha 编码距离），不再为每条线创建渐变
 *   - 粒子用实心圆 + 少量缓存光晕，不再每帧建径向渐变
 *   - 限帧 30fps；标签页隐藏时暂停；尊重 prefers-reduced-motion
 */
import { ref, onMounted, onUnmounted } from 'vue'

const canvasRef = ref(null)

let rafId = null
let particles = []
let ctx = null
let canvasEl = null
let lastFrame = 0
let running = false

const MAX_PARTICLES = 60       // 原 150
const LINK_DIST = 150          // 连线距离
const FPS = 30                 // 限帧，原为满帧 60
const FRAME_MS = 1000 / FPS

const PALETTE = [
  [0, 200, 255],   // 青
  [124, 58, 237],  // 紫
  [0, 120, 255],   // 蓝
  [0, 255, 136],   // 绿
]

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function makeParticle(w, h) {
  const [r, g, b] = PALETTE[Math.floor(Math.random() * PALETTE.length)]
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    size: Math.random() * 1.6 + 0.8,
    alpha: Math.random() * 0.45 + 0.25,
    color: `${r},${g},${b}`,
  }
}

function resize() {
  if (!canvasEl || !ctx) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvasEl.width = Math.floor(window.innerWidth * dpr)
  canvasEl.height = Math.floor(window.innerHeight * dpr)
  canvasEl.style.width = window.innerWidth + 'px'
  canvasEl.style.height = window.innerHeight + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  const w = window.innerWidth
  const h = window.innerHeight
  const count = Math.min(MAX_PARTICLES, Math.floor((w * h) / 26000))
  particles = Array.from({ length: count }, () => makeParticle(w, h))
}

function draw(now) {
  if (!running) return
  rafId = requestAnimationFrame(draw)

  // 限帧：不满足间隔则跳过本帧绘制
  if (now - lastFrame < FRAME_MS) return
  lastFrame = now

  const w = window.innerWidth
  const h = window.innerHeight

  ctx.clearRect(0, 0, w, h)

  // 更新位置（边界反弹）
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    if (p.x < 0 || p.x > w) p.vx *= -1
    if (p.y < 0 || p.y > h) p.vy *= -1
  }

  // 连接线：纯色 stroke，alpha 随距离衰减（不再逐线创建渐变）
  ctx.lineWidth = 1
  for (let i = 0; i < particles.length; i++) {
    const a = particles[i]
    for (let j = i + 1; j < particles.length; j++) {
      const b = particles[j]
      const dx = a.x - b.x
      const dy = a.y - b.y
      const d2 = dx * dx + dy * dy
      if (d2 > LINK_DIST * LINK_DIST) continue
      const t = 1 - Math.sqrt(d2) / LINK_DIST
      ctx.strokeStyle = `rgba(${a.color},${(t * 0.16).toFixed(3)})`
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
    }
  }

  // 粒子：实心圆，不再每帧创建径向渐变
  for (const p of particles) {
    ctx.fillStyle = `rgba(${p.color},${p.alpha})`
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
    ctx.fill()
  }
}

function start() {
  if (running || prefersReducedMotion()) return
  running = true
  lastFrame = 0
  rafId = requestAnimationFrame(draw)
}

function stop() {
  running = false
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

function onVisibility() {
  if (document.hidden) stop()
  else start()
}

onMounted(() => {
  canvasEl = canvasRef.value
  if (!canvasEl) return
  ctx = canvasEl.getContext('2d')
  resize()
  start()
  window.addEventListener('resize', resize)
  document.addEventListener('visibilitychange', onVisibility)
})

onUnmounted(() => {
  stop()
  window.removeEventListener('resize', resize)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.particle-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}
</style>
