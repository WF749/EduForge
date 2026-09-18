/**
 * 把教师的一句话映射成一个动作：改 / 生成 / 聊天。
 *
 * 为什么是纯函数（且不调模型）：
 *   对话是主界面，教师每敲一句话都要立刻知道"这句话会被当成什么"。
 *   调模型去判意图既慢又费额度，而且判错了是**静默**的——
 *   他说"第三段太难换个例子"，系统当成"重新生成整份教案"，
 *   前面几轮改的东西全没了。规则判定虽然笨，但是可解释、可测试、可回滚。
 *
 * 误判代价是不对称的：
 *   - 把"改"判成"生成" —— 丢掉已有成果，代价高；
 *   - 把"生成"判成"改" —— 提示"还没生成"，教师再点一次生成即可，代价低。
 * 所以规则里"重新生成"必须**显式**才成立（含"重新/重做/从头"这类词），
 * 其余一律偏向保守。
 */

/** 成品类型与它在中文里常见的说法 */
const KIND_WORDS = [
  { kind: 'lesson_plan', words: ['教案', '教学设计', '课时设计', '备课'] },
  { kind: 'ppt', words: ['ppt', '课件', '幻灯片', '演示文稿'] },
  { kind: 'animation', words: ['动画', '微课', '演示动画'] },
  { kind: 'game', words: ['游戏', '闯关', '互动游戏', '小游戏'] }
]

export const KINDS = KIND_WORDS.map((k) => k.kind)

// 「重新生成」必须显式：只认这几个词，避免把"再改改"当成推倒重来
const REGENERATE = /(重新生成|重新做|重新来|重做|重来|再来一份|从头|另起|推翻)/

const GENERATE = /(生成|创建|制作|做一?[份个]|来一?[份个]|帮我做|帮我写|写一份|出一?[份个]|设计一?[份个]|搞一?[份个])/

// 「太」单独匹配会误伤"太阳"，必须限定后面的形容词
const MODIFY = [
  /太(难|长|短|多|少|抽象|复杂|简单|啰嗦|拗口|笼统|枯燥)/,
  /(改成|改为|换成|换为|换成|改成|替换成|调整一?下|改一?下|改改|修改)/,
  /(加上|加上一段|补充|再加|多加|删掉|去掉|删除|精简|压缩|展开|详细(一点|些)|简单(一点|些))/,
  /(不够(好|详细|清楚|生动)|不好懂|听不懂|不够生动)/,
  /(重写|改写|换个(例子|说法|思路))/
]

// 明显是提问而非指令
const QUESTION = /(什么|如何|怎么|为什么|是不是|能不能|可以吗|有哪些)[^。！!?？]*[?？]?$/

function detectKind(text) {
  const lower = String(text || '').toLowerCase()
  let hit = null
  let pos = Infinity
  for (const { kind, words } of KIND_WORDS) {
    for (const w of words) {
      const i = lower.indexOf(w.toLowerCase())
      if (i >= 0 && i < pos) {
        pos = i
        hit = kind
      }
    }
  }
  return hit
}

function hasModifySignal(text) {
  return MODIFY.some((re) => re.test(text))
}

/**
 * @param {string} message 教师输入的一句话
 * @param {object} ctx
 * @param {boolean} ctx.hasVersion 该成品是否已有可修改的版本
 * @param {string} [ctx.activeKind] 当前右侧展示的成品类型（消息里没提类型时用）
 * @param {object} [ctx.explicit] UI 显式指令（快捷按钮），优先于一切规则
 * @returns {{action:'revise'|'generate'|'chat', kind?:string, reason:string, blocked?:string}}
 */
export function routeUserMessage(message, ctx = {}) {
  const text = String(message || '').trim()

  if (ctx.explicit && ctx.explicit.action) {
    return {
      action: ctx.explicit.action,
      kind: ctx.explicit.kind || ctx.activeKind || 'lesson_plan',
      reason: '快捷指令'
    }
  }

  if (!text) {
    return { action: 'chat', kind: ctx.activeKind || '', reason: '空消息' }
  }

  const kind = detectKind(text) || ctx.activeKind || 'lesson_plan'

  // 1. 「重新生成」优先于「修改」：显式推倒重来才算生成
  if (REGENERATE.test(text)) {
    return { action: 'generate', kind, reason: '命中重新生成' }
  }

  // 2. 有版本 + 修改信号 → 增量修改
  if (hasModifySignal(text)) {
    if (ctx.hasVersion) {
      return { action: 'revise', kind, reason: '命中修改信号且已有版本' }
    }
    return {
      action: 'revise',
      kind,
      reason: '命中修改信号但没有可修改的版本',
      blocked: '这门课还没有生成过该成品，请先生成再修改'
    }
  }

  // 3. 生成信号
  if (GENERATE.test(text)) {
    return { action: 'generate', kind, reason: '命中生成信号' }
  }

  // 4. 其他一律交给对话（提问、闲聊、需求描述）
  return {
    action: 'chat',
    kind,
    reason: QUESTION.test(text) ? '像是在提问' : '没有明确的生成/修改指令'
  }
}
