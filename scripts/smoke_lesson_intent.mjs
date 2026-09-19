/**
 * 「从一句话里读出这节课是什么」的冒烟测试（纯 Node，毫秒级）。
 *
 * 存在的理由：这个函数决定了新手能不能开口就用。
 * 它有两种坏法，都很安静：
 *   1. **读不出来**（"生成一份浮力教案" 抽不出"浮力"）→ 系统又去要求填表单，
 *      用户看到的就是"我都说了你还让我填"；
 *   2. **读错**（把"生成教案"抽成主题"生成"）→ 教师拿到一整份跟浮力无关的教案，
 *      而且他会以为是自己说错了。
 * 所以这里两个方向都要钉：该读出来的必须读出来，读不出来的必须返回空。
 */
import { inferLessonFields, applyInferred } from '../frontend/src/utils/lessonIntent.js'

let pass = 0
const fail = []

function eq(name, actual, expected) {
  const ok = actual === expected
  ok ? pass++ : fail.push(name)
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}` + (ok ? '' : `  期望「${expected}」实得「${actual}」`))
}

function check(name, cond, extra = '') {
  cond ? pass++ : fail.push(name)
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}${extra ? '  ' + extra : ''}`)
}

const SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '道德与法治', '科学', '信息科技', '艺术', '体育与健康']
const GRADES = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '高一', '高二', '高三']
const V = { subjects: SUBJECTS, grades: GRADES }
const T = (t) => inferLessonFields(t, V)

console.log('\n=== 1. 新手最常见的说法：必须读出主题 ===')
eq('生成一份浮力教案', T('生成一份浮力教案').topic, '浮力')
eq('帮我生成一份浮力教案', T('帮我生成一份浮力教案').topic, '浮力')
eq('生成一节浮力的教案', T('生成一节浮力的教案').topic, '浮力')
eq('来一份PPT，内容是浮力', T('来一份PPT，内容是浮力').topic, '浮力')
eq('生成浮力教案', T('生成浮力教案').topic, '浮力')
eq('生成一份《浮力》教案', T('生成一份《浮力》教案').topic, '浮力')
eq('做一节课，主题是一次函数的图像与性质', T('做一节课，主题是一次函数的图像与性质').topic, '一次函数的图像与性质')
eq('设计一份关于电磁感应的教案', T('设计一份关于电磁感应的教案').topic, '电磁感应')

console.log('\n=== 2. 顺带读出学科 / 年级 / 课时 ===')
const a = T('帮我做一节九年级物理的浮力教案')
eq('学科', a.subject, '物理')
eq('年级', a.grade, '九年级')
eq('主题（学科年级已剔掉）', a.topic, '浮力')
const b = T('生成一份初中八年级生物《细胞的结构》课件，40分钟')
eq('年级 2', b.grade, '八年级')
eq('学科 2', b.subject, '生物')
eq('课时', b.duration, 40)
eq('主题 2', b.topic, '细胞的结构')
eq('别名 初一 → 七年级', T('初一数学的相反数教案').grade, '七年级')
eq('别名 道法 → 道德与法治', T('八年级道法教案').subject, '道德与法治')
eq('九年级下册优先于九年级', T('九年级下册化学的酸碱盐教案').grade, '九年级')
eq('时长越界不认（5 分钟）', T('5分钟微课').duration, 0)
eq('时长越界不认（300 分钟）', T('300分钟教案').duration, 0)

console.log('\n=== 3. 读不出来就返回空 —— 绝不编造 ===')
eq('只说动作没有主题', T('生成教案').topic, '')
eq('只说成品类型', T('生成一份PPT').topic, '')
eq('空串', T('').topic, '')
eq('null', T(null).topic, '')
eq('只有量词', T('来一份').topic, '')
eq('只有礼貌词', T('帮我做一下').topic, '')
check('空输入不报错也不编学科', T('').subject === '' && T('').grade === '')
check('"教案"不会被当成主题', T('生成教案').topic !== '教案')
check('"PPT"不会被当成主题', T('来份PPT').topic !== 'PPT')
eq('疑问句不会把"吗"带进主题', T('能做一份浮力教案吗').topic, '浮力')

console.log('\n=== 4. matched 标记：调用方靠它决定要不要覆盖已有设定 ===')
check('说了主题 → matched 含 topic', T('生成一份浮力教案').matched.includes('topic'))
check('说了学科 → matched 含 subject', T('九年级物理浮力教案').matched.includes('subject'))
check('没说学科 → matched 不含 subject', !T('生成一份浮力教案').matched.includes('subject'))
check('没说年级 → matched 不含 grade', !T('生成一份浮力教案').matched.includes('grade'))

console.log('\n=== 5. applyInferred：只覆盖"他说了的"，补"空着的" ===')
function fakeStore(init = {}) {
  return { topic: '', subject: '数学', grade: '七年级', duration: 45, ...init }
}
let s = fakeStore()
let changes = applyInferred(s, T('生成一份浮力教案'))
eq('空主题被补上', s.topic, '浮力')
eq('说了的字段会出现在变更列表', changes.join('、'), '主题「浮力」')
check('没说的学科不被改', s.subject === '数学')
check('没说的年级不被改', s.grade === '七年级')

s = fakeStore({ topic: '一次函数' })
applyInferred(s, T('生成一份浮力教案'))
eq('明确说了新主题 → 覆盖旧的', s.topic, '浮力')

s = fakeStore({ topic: '浮力' })
changes = applyInferred(s, T('生成一份浮力教案'))
eq('主题没变 → 不报变更', changes.length, 0)

s = fakeStore()
applyInferred(s, T('帮我做一节九年级物理的浮力教案'))
eq('说的学科被应用', s.subject, '物理')
eq('说的年级被应用', s.grade, '九年级')
eq('说的主题被应用', s.topic, '浮力')

s = fakeStore()
changes = applyInferred(s, T('生成教案'))
eq('啥也没读出来 → 主题仍为空（交给调用方去问）', s.topic, '')
eq('啥也没读出来 → 无变更', changes.length, 0)

console.log('\n=== 6. 反例对照：规则没退化成"随便截一段" ===')
check('不同输入给不同主题',
  T('生成一份浮力教案').topic !== T('生成一份电磁感应教案').topic)
check('主题不含动作词', !/生成|制作|设计/.test(T('帮我生成一份浮力教案').topic))

console.log(`\n通过 ${pass} 项，失败 ${fail.length} 项`)
if (fail.length) {
  console.log('失败项：' + fail.join('、'))
  process.exit(1)
}
