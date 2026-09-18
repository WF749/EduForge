/**
 * 语音能力纯函数的冒烟测试（不碰浏览器 API，毫秒级）。
 *
 * 存在的理由：语音这块**没法在 CI 里真跑**（要麦克风、要 HTTPS、要 Chrome），
 * 所以凡是能抽成纯逻辑的部分就必须抽出来测，否则它就是一片无人验证的代码，
 * 等演示那天才发现"点了没反应"。
 *
 * 这里钉死两件事：
 *   1. 错误码翻译要能覆盖真实会遇到的那几个，且"用户自己停的"不许弹提示；
 *   2. 朗读前的文本清洗要真的去掉 Markdown 标记 —— 念出"井号星号"很出戏。
 */
import { describeSttError, stripForSpeech } from '../frontend/src/composables/useSpeech.js'

let pass = 0
let fail = 0

function eq(name, actual, expected) {
  const ok = actual === expected
  ok ? pass++ : fail++
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}` + (ok ? '' : `  期望「${expected}」实得「${actual}」`))
}

console.log('\n=== 1. 麦克风/识别错误码翻译 ===')
eq('NotAllowedError 提示去点锁图标',
  describeSttError('NotAllowedError').includes('锁图标'), true)
eq('not-allowed（识别回调的写法）同义',
  describeSttError('not-allowed').includes('锁图标'), true)
eq('NotFoundError 提示没麦克风',
  describeSttError('NotFoundError').includes('未检测到麦克风'), true)
eq('network 提示查网络',
  describeSttError('network').includes('网络'), true)
eq('no-speech 提示再说一次',
  describeSttError('no-speech').includes('再说一次'), true)
eq('audio-capture 提示被占用',
  describeSttError('audio-capture').includes('占用'), true)
eq('service-not-allowed 建议换浏览器',
  describeSttError('service-not-allowed').includes('Chrome'), true)
// 用户自己按停的，弹提示是打扰
eq('aborted 不提示', describeSttError('aborted'), '')
eq('未知错误也给得出话（不静默）', describeSttError('weird-code').includes('weird-code'), true)
eq('空值不提示', describeSttError(''), '')
eq('undefined 不提示', describeSttError(undefined), '')

console.log('\n=== 2. 朗读前文本清洗 ===')
eq('去掉标题井号', stripForSpeech('## 浮力'), '浮力')
eq('去掉加粗星号', stripForSpeech('**重点**'), '重点')
eq('去掉行内代码反引号', stripForSpeech('用 `F=ρgV` 算'), '用 F=ρgV 算')
eq('代码块整体跳过', stripForSpeech('看代码：\n```js\nlet a=1\n```\n结束'), '看代码： （代码块已跳过） 结束')
eq('压缩多余空白', stripForSpeech('a    b\n\n\nc'), 'a b c')
eq('去掉引用符号', stripForSpeech('> 引用'), '引用')
eq('空值返回空串', stripForSpeech(''), '')
eq('null 返回空串', stripForSpeech(null), '')
eq('数字不炸', stripForSpeech(42), '42')
eq('不误删中文标点', stripForSpeech('浮力：是什么？'), '浮力：是什么？')

console.log(`\n${'='.repeat(64)}\n通过 ${pass} 项，失败 ${fail} 项\n${'='.repeat(64)}`)
process.exit(fail ? 1 : 0)
