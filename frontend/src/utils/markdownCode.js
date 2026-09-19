/**
 * 代码块语法高亮：把 highlight.js 接进 marked 的 `code` renderer。
 *
 * 为什么必须显式写 renderer，而不是 `marked.setOptions({ highlight })`：
 * marked 从 v5 起**移除了** `highlight` 配置项，本项目升到 18 之后
 * `setOptions({ highlight: ... })` 变成一个被静默忽略的字段 ——
 * 界面上代码块不再着色，但控制台不报任何错、构建也正常，
 * 于是"高亮失效"这件事一直没人发现（`utils/highlight.js` 里按需注册的
 * 12 种语言全部白注册）。这是典型的"不报错的功能消失"。
 *
 * 单独成文件是为了可测：本模块只依赖 marked 与 highlight.js（纯 JS），
 * 可以在 Node 里直接跑；渲染管线另一头（`utils/markdown.js`）依赖
 * KaTeX 的 CSS，Node 里 import 不了。脚本 smoke_markdown_code.mjs 盯的就是
 * "高亮到底有没有真的接上" —— 上面那次失效，正是没人盯才发生的。
 */
import { marked } from 'marked'
// 显式写 .js 扩展名：Node 的 ESM 对相对路径不做扩展名补全，
// 少了它就 import 不进来（本模块要能被 scripts/smoke_markdown_code.mjs 直接跑）。
import hljs from './highlight.js'

// 只在确实有把握时按语言高亮；语言不认识就交给 highlightAuto，
// 它至少能把字符串/数字/注释标出来，比整块灰字强。
export function renderCodeBlock(code, lang) {
  const text = String(code ?? '')
  const name = String(lang || '').trim().split(/\s+/)[0]
  let html
  if (name && hljs.getLanguage(name)) {
    try {
      html = hljs.highlight(text, { language: name }).value
    } catch {
      html = hljs.highlightAuto(text).value
    }
  } else {
    html = hljs.highlightAuto(text).value
  }
  // class 里带上语言名，CSS 与"复制"后处理都靠它识别；
  // 语言未知时退化成纯 code 块（后处理里有对应分支）。
  return name
    ? `<pre><code class="hljs language-${name}">${html}\n</code></pre>`
    : `<pre><code class="hljs">${html}\n</code></pre>`
}

let installed = false

/** 幂等：多个组件 import 本模块时只会装一次 */
export function installCodeHighlight() {
  if (installed) return
  installed = true
  marked.use({
    renderer: {
      code: (token) => renderCodeBlock(token?.text, token?.lang)
    }
  })
}
