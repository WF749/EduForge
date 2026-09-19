/**
 * 对话动作路由的冒烟测试（纯 Node，不启服务、不调模型，毫秒级）。
 *
 * 存在的理由：对话是主界面，教师每句话都要被分流成「改 / 生成 / 聊天」。
 * 这个分流判错的代价是**静默且不可逆**的——
 *   他说"第三段太难换个例子"，系统判成"重新生成"，
 *   前面几轮辛苦改好的内容瞬间被覆盖，而且没有任何报错。
 * 规则本身又极易在"顺手加两个关键词"时破坏，所以必须钉死。
 *
 * 运行：node scripts/smoke_chat_action.mjs
 */
import { looksLikeQuestion, routeUserMessage } from '../frontend/src/utils/chatAction.js'

let pass = 0
let fail = 0

function check(name, cond, extra = '') {
  if (cond) pass += 1
  else fail += 1
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}${extra ? '  ' + extra : ''}`)
}

function route(text, ctx = {}) {
  return routeUserMessage(text, ctx)
}

console.log('='.repeat(64))
console.log('对话动作路由冒烟测试')
console.log('='.repeat(64))

console.log('\n== 1. 修改指令必须优先于生成（误判代价最高的一条）==')
const has = { hasVersion: true, activeKind: 'lesson_plan' }
check('第三段太难，换成生活里的例子 → revise',
  route('第三段太难，换成生活里的例子', has).action === 'revise')
check('把导入环节改成煮饺子的例子 → revise',
  route('把导入环节改成煮饺子的例子', has).action === 'revise')
check('作业布置再加两道题 → revise',
  route('作业布置再加两道题', has).action === 'revise')
check('这段太啰嗦，精简一下 → revise',
  route('这段太啰嗦，精简一下', has).action === 'revise')
check('教学目标写得不够清楚 → revise',
  route('教学目标写得不够清楚', has).action === 'revise')

console.log('\n== 2. 显式「重新生成」才允许推倒重来 ==')
check('重新生成教案 → generate',
  route('重新生成教案', has).action === 'generate')
check('这份教案重做一份 → generate',
  route('这份教案重做一份', has).action === 'generate')
check('"再改改" 不能被当成重新生成',
  route('再改改', has).action !== 'generate', route('再改改', has).action)
check('"再想想" 不能被当成重新生成',
  route('再想想', has).action !== 'generate')

console.log('\n== 3. 生成指令 ==')
const none = { hasVersion: false, activeKind: 'lesson_plan' }
check('帮我生成一份浮力教案 → generate',
  route('帮我生成一份浮力教案', none).action === 'generate')
check('来一份 PPT → generate 且 kind=ppt',
  (() => { const r = route('来一份 PPT', none); return r.action === 'generate' && r.kind === 'ppt' })())
check('做个互动游戏 → generate 且 kind=game',
  (() => { const r = route('做个互动游戏', none); return r.action === 'generate' && r.kind === 'game' })())
check('做一个动画 → generate 且 kind=animation',
  (() => { const r = route('做一个动画', none); return r.action === 'generate' && r.kind === 'animation' })())

console.log('\n== 4. 没有版本时不能"改" ==')
const blocked = route('把导入环节改成煮饺子的例子', { hasVersion: false })
check('判定仍是 revise（意图没错）', blocked.action === 'revise')
check('但带 blocked 提示', Boolean(blocked.blocked), blocked.blocked || '')

console.log('\n== 5. 提问与其他 → 聊天 ==')
check('什么是浮力？ → chat', route('什么是浮力？', has).action === 'chat')
check('这样设计合理吗？ → chat', route('这样设计合理吗？', has).action === 'chat')
check('我想讲八年级物理浮力 → chat（没有明确动词）',
  route('我想讲八年级物理浮力', none).action === 'chat')

console.log('\n== 6. 快捷指令优先于一切规则 ==')
check('显式 revise 覆盖生成词',
  routeUserMessage('生成教案', { explicit: { action: 'revise', kind: 'lesson_plan' } }).action === 'revise')
check('显式 generate 覆盖修改词',
  routeUserMessage('把这段改掉', { explicit: { action: 'generate', kind: 'ppt' } }).action === 'generate')

console.log('\n== 7. 边界 ==')
check('空消息 → chat', route('', has).action === 'chat')
check('null → chat', route(null, has).action === 'chat')
check('消息没提类型时用当前类型', route('改成生活例子', has).kind === 'lesson_plan')
check('"太阳" 不会被当成"太难"',
  route('太阳', has).action === 'chat', route('太阳', has).reason)
check('大小写不敏感识别 PPT', route('来一份 ppt', none).kind === 'ppt')

console.log('\n== 8. 提问检测（决定走"问答"还是走"澄清"）==')
// 这一条判错的表现是：教师提问，系统反问"请问你想了解什么主题的知识"，
// 再问一句就只剩"你直接说要生成什么"——正是被吐槽的那个毛病
check('什么是三角函数 → 提问', looksLikeQuestion('什么是三角函数'))
check('浮力是什么 → 提问', looksLikeQuestion('浮力是什么'))
check('解释一下动能定理 → 提问', looksLikeQuestion('解释一下动能定理'))
check('学生总把 k 和 b 搞混，怎么讲 → 提问', looksLikeQuestion('学生总把 k 和 b 搞混，怎么讲'))
check('这两个概念有什么区别 → 提问', looksLikeQuestion('这两个概念有什么区别'))
check('电磁感应有什么易错点 → 提问', looksLikeQuestion('电磁感应有什么易错点'))
check('怎么教一次函数比较好 → 提问', looksLikeQuestion('怎么教一次函数比较好'))
check('给我讲讲这个原理 → 提问', looksLikeQuestion('给我讲讲这个原理'))
check('帮我想想这节课的导入 → 提问', looksLikeQuestion('帮我想想这节课的导入'))
check('能不能举一个生活中的例子 → 提问', looksLikeQuestion('能不能举一个生活中的例子'))
check('带问号的短问句也算', looksLikeQuestion('这样对吗？'))

check('生成指令不算提问', !looksLikeQuestion('生成一份浮力教案'))
check('修改指令不算提问', !looksLikeQuestion('导入环节太抽象，换成煮饺子的例子'))
check('含糊诉求不算提问（该走澄清）', !looksLikeQuestion('帮我搞个能讲浮力的东西'))
check('空串不算提问', !looksLikeQuestion(''))
check('null 不算提问', !looksLikeQuestion(null))
// 反向对照：提问与"要东西"都能被同一套规则分开，规则本身没退化成恒真/恒假
check('规则没退化成恒真',
  looksLikeQuestion('什么是三角函数') && !looksLikeQuestion('生成一份浮力教案'))

// 提问必须落在 chat 动作上 —— 若它被判成 generate/revise，问答那条路根本不会被走到
check('提问不会被误判成 generate', route('什么是三角函数', has).action === 'chat')
check('提问不会被误判成 revise', route('学生总把 k 和 b 搞混，怎么讲', has).action === 'chat')
check('提问的 reason 标明是提问', route('什么是三角函数', has).reason === '像是在提问')

console.log('\n' + '='.repeat(64))
console.log(`通过 ${pass} 项，失败 ${fail} 项`)
console.log('='.repeat(64))
process.exit(fail ? 1 : 0)
