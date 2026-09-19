/**
 * 消息正文渲染：Markdown + 数学公式 + 代码高亮 + 代码块复制按钮。
 *
 * 为什么抽成公共模块：原来这段逻辑只活在 ChatView.vue 里。工作台对话现在
 * 也要渲染模型回答 —— 各写一份的话，公式处理和代码块复制按钮迟早分叉
 * （同一份东西维护两遍，改了一处忘了另一处，界面上只是"看起来不太一样"，
 * 没人会当成 bug 报上来）。抽取理由与 `composables/useSpeech.js` 相同。
 *
 * 代码高亮由 `markdownCode.js` 安装（那边才能被 Node 冒烟测试直接覆盖）。
 */
import { marked } from 'marked'
import { renderMathInText } from './mathRender'
import { installCodeHighlight } from './markdownCode.js'

// breaks: 模型输出的单换行按换行显示（不加这条，模型的分点会挤成一段）
// gfm:    表格、删除线等 GitHub 风格语法
marked.setOptions({ breaks: true, gfm: true })
// 必须显式装 renderer —— marked 从 v5 起移除了 `highlight` 配置项，
// 只写 setOptions 的话高亮会**静默失效**（详见 markdownCode.js 顶部说明）
installCodeHighlight()

const COPY_BTN = '<button class="copy-btn" onclick="window._copyCode(this)">复制</button>'

/** 先渲染数学公式再交给 marked：顺序反了 KaTeX 的 HTML 会被当成 Markdown 处理 */
function renderBody(text) {
  return marked.parse(renderMathInText(String(text || '')))
}

function addCopyButtons(html) {
  return html
    .replace(/<pre><code class="([^"]*)">/g, `<pre class="code-block">${COPY_BTN}<code class="$1">`)
    .replace(/<pre><code>/g, `<pre class="code-block">${COPY_BTN}<code>`)
}

/**
 * 把一条消息的正文渲染成 HTML。
 *
 * 深度思考的返回是两段（`## 思考过程` / `## 最终回答`），这里拆成可折叠块；
 * 普通回答直接渲染。判断条件保持原样（必须两段都在），
 * 只出现一段时按普通正文处理，不要猜。
 */
export function formatMessage(text) {
  if (!text) return ''
  const raw = String(text)

  if (raw.includes('## 思考过程') && raw.includes('## 最终回答')) {
    const parts = raw.split('## 最终回答')
    const thinking = addCopyButtons(
      renderBody(parts[0].replace('## 思考过程', '').trim())
    )
    const answer = addCopyButtons(renderBody(parts[1] ? parts[1].trim() : ''))
    return `<div class="think-container">
      <div class="think-section" onclick="this.classList.toggle('collapsed')">
        <div class="think-hdr"><span>🧠 深度思考过程</span><span class="think-toggle">▼</span></div>
        <div class="think-body">${thinking}</div>
      </div>
      <div class="answer-section">${answer}</div>
    </div>`
  }

  return addCopyButtons(renderBody(raw))
}

/**
 * 代码块复制按钮的全局处理函数 —— 用 `onclick` 内联调用最简单，
 * 省掉给每个 code 块挂事件监听的清理逻辑。
 */
if (typeof window !== 'undefined' && !window._copyCode) {
  window._copyCode = function (btn) {
    const code = btn.nextElementSibling
    if (!code || code.tagName !== 'CODE') return
    navigator.clipboard.writeText(code.textContent).then(() => {
      btn.textContent = '已复制!'
      setTimeout(() => { btn.textContent = '复制' }, 2000)
    })
  }
}
