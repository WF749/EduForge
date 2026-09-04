/**
 * 共享数学公式渲染工具
 * 提供 KaTeX 渲染、Markdown+数学组合渲染、纯文本符号替换
 */
import katex from 'katex'
import 'katex/dist/katex.min.css'

/**
 * 渲染文本中的 LaTeX 数学公式
 * 支持块级 $$...$$ 和行内 $...$
 * 自动保护代码块不被公式渲染影响
 */
export function renderMathInText(src) {
  if (!src) return ''
  // 保护代码块不被公式渲染影响
  const codeBlocks = []
  let s = src.replace(/```[\s\S]*?```/g, m => { codeBlocks.push(m); return `%%CODE_BLOCK_${codeBlocks.length - 1}%%` })
  s = s.replace(/`[^`]+`/g, m => { codeBlocks.push(m); return `%%CODE_BLOCK_${codeBlocks.length - 1}%%` })
  // 渲染块级公式 $$...$$
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (_, latex) => {
    try { return '<div class="math-block">' + katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false }) + '</div>' }
    catch { return '<div class="math-block">' + latex + '</div>' }
  })
  // 渲染行内公式 $...$
  s = s.replace(/\$([^$\n]+?)\$/g, (_, latex) => {
    try { return katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false }) }
    catch { return '<span class="math-inline">' + latex + '</span>' }
  })
  // 还原代码块
  s = s.replace(/%%CODE_BLOCK_(\d+)%%/g, (_, i) => codeBlocks[parseInt(i)])
  return s
}

/**
 * 纯文本数学符号替换（不依赖 KaTeX）
 * 用于后端生成的独立 HTML 或纯文本场景
 */
export function simplifyMathSymbols(text) {
  if (!text) return ''
  return text
    .replace(/\\\times/g, '\u00d7')
    .replace(/\\\div/g, '\u00f7')
    .replace(/\\\pm/g, '\u00b1')
    .replace(/\\\leq/g, '\u2264')
    .replace(/\\\geq/g, '\u2265')
    .replace(/\\\neq/g, '\u2260')
    .replace(/\\\sqrt/g, '\u221a')
    .replace(/\\\infty/g, '\u221e')
    .replace(/\\\alpha/g, '\u03b1')
    .replace(/\\\beta/g, '\u03b2')
    .replace(/\\\gamma/g, '\u03b3')
    .replace(/\\\delta/g, '\u03b4')
    .replace(/\\\pi/g, '\u03c0')
    .replace(/\\\theta/g, '\u03b8')
    .replace(/\\\sum/g, '\u2211')
    .replace(/\\\int/g, '\u222b')
    .replace(/\*\*/g, '\u00d7')
    .replace(/\^2/g, '\u00b2')
    .replace(/\^3/g, '\u00b3')
    .replace(/\^n/g, '\u207f')
    .replace(/\^{(\d+)}/g, (_, n) => {
      const sup = { '0': '\u2070', '1': '\u00b9', '2': '\u00b2', '3': '\u00b3', '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077', '8': '\u2078', '9': '\u2079' }
      return n.split('').map(c => sup[c] || c).join('')
    })
}
