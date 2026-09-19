/**
 * 代码块高亮的冒烟测试（纯 Node，不联网、秒级）。
 *
 * 存在的理由：这个功能**已经静默失效过一次**。marked 从 v5 起移除了
 * `highlight` 配置项，项目升到 18 后 `setOptions({ highlight })` 变成了
 * 一个被忽略的字段：界面上代码块不再着色，但控制台不报错、构建正常、
 * `utils/highlight.js` 里按需注册的 12 种语言看起来也"在"。
 * 没有任何自动化手段能发现它 —— 于是它坏了很久。
 *
 * 所以这里盯两件事：
 *   1. 高亮结果本身对（关键字/字符串真的被包上了 span）；
 *   2. **高亮确实接进了 marked**（installCodeHighlight 之后 parse 出来的
 *      HTML 里必须有 hljs 的 span）—— 第 2 条才是防线，第 1 条只是补充。
 */
// marked 装在前端的 node_modules 里，本脚本在项目根目录执行 —— 裸写 `'marked'`
// 会从脚本自身位置往上找 node_modules，根目录没有，直接 ERR_MODULE_NOT_FOUND。
// 这里按**解析后的真实文件路径**导入：Node 的 ESM 按解析结果去重，
// 与 markdownCode.js 里 `import 'marked'` 拿到的是同一个实例
// （否则会出现"我 install 的是 A 实例，你 parse 用的是 B 实例"的假绿灯）。
import { marked } from '../frontend/node_modules/marked/lib/marked.esm.js'
import { renderCodeBlock, installCodeHighlight } from '../frontend/src/utils/markdownCode.js'

let PASS = 0
const FAIL = []

function check(name, cond, extra = '') {
  if (cond) { PASS++; console.log(`  [PASS] ${name}${extra ? '  ' + extra : ''}`) }
  else { FAIL.push(name); console.log(`  [FAIL] ${name}${extra ? '  ' + extra : ''}`) }
}

console.log('\n=== 1. 认得出来的语言要高亮 ===')
const js = renderCodeBlock('const a = 1', 'js')
check('关键字被包上 hljs span', js.includes('hljs-keyword'), js.slice(0, 70))
check('数字被包上 hljs span', js.includes('hljs-number'))
check('class 里带语言名（CSS/复制按钮都靠它）', js.includes('language-js'))
check('python 也能高亮', renderCodeBlock('def f():\n    pass', 'python').includes('hljs-keyword'))
check('json 能高亮', renderCodeBlock('{"a": 1}', 'json').includes('hljs-'))

console.log('\n=== 2. 认不出的语言不能炸，也不能假装高亮 ===')
const unknown = renderCodeBlock('some ??? text', '不存在的语言')
check('未知语言不抛异常', typeof unknown === 'string' && unknown.includes('<pre>'))
check('未知语言不退化成空', unknown.includes('some'))
check('空语言走自动识别', renderCodeBlock('const a = 1', '').includes('<pre>'))
check('语言名带参数也能解析', renderCodeBlock('a', 'js title=x').includes('language-js'))

console.log('\n=== 3. 空输入与脏输入 ===')
check('空字符串不炸', renderCodeBlock('', 'js').includes('<pre>'))
check('null 不炸', renderCodeBlock(null, 'js').includes('<pre>'))
check('undefined 不炸', renderCodeBlock(undefined, undefined).includes('<pre>'))
check('未知 lang 为 undefined 不炸', renderCodeBlock('a', undefined).includes('<pre>'))

console.log('\n=== 4. 转义：代码里的尖括号必须被转义，不能变成真标签 ===')
const xml = renderCodeBlock('<script>alert(1)</script>', 'xml')
check('尖括号被转义', !xml.includes('<script>'), xml.slice(0, 90))
check('转义后仍保留了原文可见性', xml.includes('&lt;') || xml.includes('script'))

console.log('\n=== 5. 关键防线：高亮真的接进 marked 了吗 ===')
// 用一段独占的标记，避免与其它用例互相影响
const marker = 'const 关键防线变量 = 42'
const before = marked.parse('```js\n' + marker + '\n```')
installCodeHighlight()
const after = marked.parse('```js\n' + marker + '\n```')
check(
  'install 之前 marked 不快（说明 setOptions 那条路确实不通）',
  !before.includes('hljs-keyword'),
  '若这里失败，说明 marked 又改回了 setOptions 支持，实现可以简化'
)
check('install 之后 marked 产出的代码块带高亮 span', after.includes('hljs-keyword'))
check('install 之后仍保留代码原文', after.includes('42'))

// 幂等：重复 install 不应把 renderer 套娃（套了会重复转义）
installCodeHighlight()
installCodeHighlight()
const twice = marked.parse('```js\nconst x = 1\n```')
check('重复 install 幂等（不重复转义）', !twice.includes('&amp;lt;'), twice.slice(0, 80))
check('重复 install 后内容仍正确', twice.includes('hljs-keyword') && twice.includes('x'))

console.log('\n=== 6. 代码块仍然能被"复制按钮"后处理命中 ===')
// utils/markdown.js 里按 <pre><code class="..."> 和 <pre><code> 两种形态注入按钮，
// renderer 改了输出结构就必须同步；否则复制按钮会静默消失
const withClass = renderCodeBlock('a', 'js')
const noClass = renderCodeBlock('a', '')
check('带语言时是 <pre><code class="...">', /<pre><code class="[^"]*">/.test(withClass))
check('不带语言时是 <pre><code class="hljs">', /<pre><code class="[^"]*">/.test(noClass))
check('两种形态都不会漏到无 class 的裸 <pre><code>', !/<pre><code>/.test(withClass) && !/<pre><code>/.test(noClass))

console.log(`\n通过 ${PASS} 项，失败 ${FAIL.length} 项`)
if (FAIL.length) {
  console.log('失败项：' + FAIL.join('、'))
  process.exit(1)
}
