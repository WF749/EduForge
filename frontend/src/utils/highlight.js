/**
 * 轻量 highlight.js —— 只注册教学场景常用语言。
 *
 * 背景：原先在 ChatView.vue 里 `import hljs from 'highlight.js'`，
 * 这会把 190+ 种语言的语法定义全部打进包里（约 800KB+），
 * 导致 ChatView 产物高达 1MB，是页面卡顿/切换缓慢的主因之一。
 *
 * 这里改用 `highlight.js/lib/core` 并按需注册语言，API 完全一致
 * （getLanguage / highlight / highlightAuto 均可用），体积大幅下降。
 */
import hljs from 'highlight.js/lib/core'

import bash from 'highlight.js/lib/languages/bash'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'

const languages = {
  bash,
  cpp,
  css,
  java,
  javascript,
  json,
  markdown,
  plaintext,
  python,
  sql,
  typescript,
  xml,
}

Object.entries(languages).forEach(([name, def]) => {
  try {
    hljs.registerLanguage(name, def)
  } catch {
    // 单个语言注册失败不应影响整体功能
  }
})

export default hljs
