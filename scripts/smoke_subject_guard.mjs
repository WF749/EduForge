/**
 * 学科一致性检查的回归测试。
 *
 * 钉死的是一个**整份产物作废**的问题：主题「细胞的结构」+ 学科「数学」，
 * 系统顺着矛盾生成了一份"用数学读懂生命、统计核糖体数量"的生物课件。
 * 排版再好也是废的。
 *
 * 两个方向都要钉：
 *   该提醒的必须提醒（生物词 + 数学学科）
 *   **不该提醒的一个都不能报** —— 误报多了教师就把提示当噪音，
 *   真出问题时也不会看。跨学科课（数学×生物）本身就是合法的，不能拦。
 *
 * 运行：node scripts/smoke_subject_guard.mjs
 */
import assert from 'node:assert'

const src = await import('file:///' + process.cwd().replace(/\\/g, '/') + '/frontend/src/utils/subjectGuard.js')
const { suggestSubject, SUBJECT_KEYWORDS } = src

let pass = 0
let fail = 0
function check(name, cond, extra = '') {
  if (cond) { pass++; console.log(`  [PASS] ${name}${extra ? '  ' + extra : ''}`) }
  else { fail++; console.log(`  [FAIL] ${name}${extra ? '  ' + extra : ''}`) }
}

console.log('================================================================')
console.log('学科一致性检查 —— 行为测试')
console.log('================================================================')

console.log('\n== 1. 必须提醒：主题像另一门课 ==')
const mustWarn = [
  ['细胞的结构', '数学', '生物'],
  ['浮力', '语文', '物理'],
  ['一元二次方程', '生物', '数学'],
  ['光合作用与呼吸作用', '英语', '生物'],
  ['鸦片战争', '数学', '历史'],
  ['元素周期律', '物理', '化学'],
]
for (const [topic, current, expect] of mustWarn) {
  const r = suggestSubject(topic, current)
  check(`「${topic}」+ ${current} → 提示 ${expect}`,
    !!r && r.subject === expect, r ? `(命中 ${r.matched.slice(0, 2).join('、')})` : '(未提示)')
  check(`「${topic}」提示里说明后果`, !!r && r.message.includes(current))
}

console.log('\n== 2. 不该提醒：学科本来就对 ==')
const noWarn = [
  ['细胞的结构', '生物'],
  ['浮力', '物理'],
  ['一元二次方程', '数学'],
  ['静夜思', '语文'],
]
for (const [topic, current] of noWarn) {
  check(`「${topic}」+ ${current} → 不打扰`, suggestSubject(topic, current) === null)
}

console.log('\n== 3. 不该提醒：跨学科与无关主题 ==')
const quiet = [
  // 真正的跨学科：主题里同时有生物词（细胞）和数学词（函数），系统不该替教师判
  ['细胞中的函数关系', '数学', '跨学科：同时命中生物与数学'],
  ['函数的图像', '数学', ''],
  ['我的暑假', '语文', '无学科特征'],
  ['复习课', '数学', '无学科特征'],
]
for (const [topic, current, note] of quiet) {
  check(`「${topic}」+ ${current} → 不打断${note ? '（' + note + '）' : ''}`,
    suggestSubject(topic, current) === null)
}

console.log('\n== 4. 词表纪律：不放跨学科通用词 ==')
const genericWords = ['结构', '变化', '关系', '应用', '方法', '概念', '特点', '作用', '意义']
let leaked = []
for (const [subj, words] of Object.entries(SUBJECT_KEYWORDS)) {
  for (const w of genericWords) if (words.includes(w)) leaked.push(`${subj}:${w}`)
}
check('词表里没有跨学科通用词（否则处处误报）', leaked.length === 0, leaked.join(','))

console.log('\n== 5. 边界 ==')
check('空主题 → null', suggestSubject('', '数学') === null)
check('空学科 → null', suggestSubject('细胞的结构', '') === null)
check('两者都空 → null', suggestSubject('', '') === null)
check('主题含学科词但学科为空 → 不崩', suggestSubject('浮力', null) === null)

console.log('\n================================================================')
console.log(`通过 ${pass} 项，失败 ${fail} 项`)
console.log('================================================================')
process.exit(fail ? 1 : 0)
