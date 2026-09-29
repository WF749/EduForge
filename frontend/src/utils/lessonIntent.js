/**
 * 从教师的一句话里读出「这节课是什么」。
 *
 * 为什么需要它：新手最自然的用法是「生成一份浮力教案」一口气说完，
 * 系统却回「请先在顶部填好教学主题」——**那句话本身就是主题**。
 * 把系统的数据模型（先填表、再生成）强加给人，是新手劝退的头号原因：
 * 他明明已经说清楚了，却被要求换个地方再说一遍。
 *
 * 纯函数、不碰 store：学科/年级词表由调用方传入（它们在 `store/lesson.js` 里），
 * 这样本模块能在 Node 下直接跑测试 —— 而 store 依赖 pinia，测不了。
 *
 * 分寸：**只读不猜**。读不出来就返回空，由调用方去问一句人话，
 * 绝不编一个主题出来（编错会让教师生成一整份与自己无关的教案）。
 */

/** 一句话里的噪声：动作词、量词、礼貌词、成品类型词 */
const NOISE = [
  /(?:帮我|请|麻烦|给我|替我|我想|我要|我打算|我需要|需要|能不能|可不可以|可以|能否|直接|重新|先|再)\s*/g,
  // 动作词要全：老版本只有"生成/制作/设计/写/做"，
  // "来一份""弄一个""准备一节""安排一节""出一份" 全都漏在外面，被当成主题。
  /(?:生成|创建|制作|设计|编写|准备|安排|弄|搞|写|做|出|来一?[份个节堂])/g,
  /(?:一|两|三|[0-9]+)\s*[份个节堂]/g,
  // "内容是浮力""主题是一次函数" —— 冒号后才是主题，冒号前全是引导语
  /(?:内容是|内容是|内容为|主题是|主题为|课题是|课题为|讲的是|教的是|内容|主题|课题)/g,
  /(?:关于|有关|围绕)/g,
  // 学段词：它不是主题（"初中八年级生物《细胞的结构》"里的"初中"）
  /(?:小学|初中|高中|中职|职高|大学)/g,
  /(?:一下|一遍|一趟)/g,
  // "八年级物理浮力教学课件" —— "教学"是修饰成品的，不是主题的一部分。
  // 但"教学设计"是**成品类型词**，不能把它的"教学"先吃掉只留"设计"
  // （那会让"生成一份教学设计"抽出主题"设计"），所以排除后接"设计"的情况。
  /(?:教学|授课|上课)(?!设计)/g,
  // 语气尾巴：留在主题里会变成"浮力 吗"
  /(?:吧|呢|啊|哦|哈|呀|吗|好吗|行吗|谢谢)\s*$/g,
]

/** 成品类型词 —— 它们不是主题的一部分，是"要做什么" */
const ARTIFACT_WORDS = /(?:教学设计|课时设计|备课|教案|学案|导学案|说课稿|PPT|ppt|Ppt|课件|幻灯片|演示文稿|微课|演示动画|动画|互动实验|探究实验|实验|互动小游戏|互动游戏|小游戏|游戏|闯关|练习题|习题|试题)/g

/**
 * 学段别名 → 标准取值。
 * 取值与后端 `llm_lesson_plan_all_stages.level_rules` 的键名一致，
 * 这样 stage 可以直接喂给 `analyze_requirements(level=...)`，零转换。
 *
 * 为什么学段要独立成字段：「高中语文」认得出学段、认不出具体年级 ——
 * 只靠年级推，这类输入就整个丢失了。
 */
const STAGE_ALIASES = {
  小学: '小学', 初中: '初中', 高中: '普通高中', 高一: '普通高中',
  高二: '普通高中', 高三: '普通高中',
  中职: '职业高中·中等职业学校', 职高: '职业高中·中等职业学校',
  中专: '职业高中·中等职业学校',
  大学: '普通高等院校', 高校: '普通高等院校'
}

/** 学科别名 → 标准名（只放"人会说但词表里没有"的说法） */
const SUBJECT_ALIASES = {
  道法: '道德与法治', 思政: '道德与法治', 政治: '道德与法治',
  信息技术: '信息科技', 计算机: '信息科技', 编程: '信息科技',
  音乐: '艺术', 美术: '艺术', 体育: '体育与健康'
}

/** 年级别名 → 标准名 */
const GRADE_ALIASES = {
  初一: '七年级', 初二: '八年级', 初三: '九年级',
  小一: '一年级', 小二: '二年级', 小三: '三年级',
  小四: '四年级', 小五: '五年级', 小六: '六年级',
  高一: '高一', 高二: '高二', 高三: '高三',
  高中一年级: '高一', 高中二年级: '高二', 高中三年级: '高三',
  七年级下册: '七年级', 八年级下册: '八年级', 九年级下册: '九年级'
}

const DURATION = /([0-9]{2,3})\s*(?:分钟|min)/

/** 去掉首尾的标点、空格、"的/地"这类连接词 */
function tidy(text) {
  // 先 trimStart：前面的替换会留下前导空格，不先去掉的话下面所有 `^` 规则都会失效
  return String(text || '')
    .trimStart()
    // 「做一节课，主题是X」剥完动作与量词后剩下「课，X」—— 这个光杆量词名词要去掉
    .replace(/^(?:课|节|份|个|堂)\s*[，,、；;：:]?\s*/, '')
    // 书名号**不在**剥离范围：《故乡》是主题的一部分，不是标点
    .replace(/^[\s，,。.、；;：:!！?？'"'（）()【】\[\]-]+/, '')
    .replace(/[\s，,。.、；;：:!！?？'"'（）()【】\[\]-]+$/, '')
    .replace(/^(?:的|地|得)\s*/, '')
    .replace(/\s*(?:的|地|得)$/, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

/**
 * @param {string} text 教师输入的一句话
 * @param {{subjects?: string[], grades?: string[]}} vocab 词表（来自 store）
 * @returns {{topic: string, subject: string, grade: string, duration: number, matched: string[]}}
 *          `matched` 是"这句话里明确提到了什么"，调用方据此决定要不要覆盖已填字段
 */
export function inferLessonFields(text, vocab = {}) {
  const subjects = Array.isArray(vocab.subjects) ? vocab.subjects : []
  const grades = Array.isArray(vocab.grades) ? vocab.grades : []

  const raw = String(text || '').trim()
  const out = { topic: '', subject: '', grade: '', stage: '', duration: 0, matched: [] }
  if (!raw) return out

  // ---- 书名号里的东西先"挖"出来 ----
  // 《课间操的科学》里的"科学"是篇名的一部分，不是学科。
  // 不先挖走，学科识别会把它当成学科剔掉，篇名就被拆成"课间操的"。
  const quoted = []
  const MARK = '\u0001'   // 不会命中任何噪声规则的占位符
  let rest = raw.replace(/《[^》]*》/g, (m) => {
    quoted.push(m)
    return `${MARK}${quoted.length - 1}${MARK}`
  })
  /** 把挖走的书名还原回去（主题定型前调用） */
  const restore = (s) => s.replace(
    new RegExp(`${MARK}(\\d+)${MARK}`, 'g'), (_, i) => quoted[Number(i)] || '')

  // 学段单独认一次：**从整句话里认**，因为"高中语文"认得出学段却认不出年级。
  // 只靠年级反推的话，这类输入整个丢失。
  const stageWords = Object.keys(STAGE_ALIASES).sort((a, b) => b.length - a.length)
  for (const word of stageWords) {
    if (raw.includes(word)) {
      out.stage = STAGE_ALIASES[word]
      out.matched.push('stage')
      break
    }
  }

  for (const alias of Object.keys(SUBJECT_ALIASES)) {
    if (rest.includes(alias)) {
      out.subject = SUBJECT_ALIASES[alias]
      out.matched.push('subject')
      rest = rest.split(alias).join(' ')
      break
    }
  }
  if (!out.subject) {
    const hit = subjects.find((s) => s && rest.includes(s))
    if (hit) {
      out.subject = hit
      out.matched.push('subject')
      rest = rest.split(hit).join(' ')
    }
  }

  // 长别名优先（"九年级下册"必须先于"九年级"匹配上）
  const gradeWords = [...Object.keys(GRADE_ALIASES).sort((a, b) => b.length - a.length), ...grades]
  for (const word of gradeWords) {
    if (word && rest.includes(word)) {
      out.grade = GRADE_ALIASES[word] || word
      out.matched.push('grade')
      rest = rest.split(word).join(' ')
      break
    }
  }

  const dur = rest.match(DURATION)
  if (dur) {
    const n = Number(dur[1])
    if (n >= 15 && n <= 180) {
      out.duration = n
      out.matched.push('duration')
      rest = rest.replace(dur[0], ' ')
    }
  }

  // ---- 剩下的就是主题候选 ----
  // 顺序有讲究：先按规则剥离，再**合并空白**，最后才做首尾清理 ——
  // 反过来的话，"能 浮力 吗" 这类中间带空格的结果会让句尾语气词匹配不上。
  //
  // 句首的"能/能否/可以"要**锚定**着剥：不锚定的话"动能定理"会被吃成"动 定理"。
  rest = rest.replace(/^\s*(?:能不能|可不可以|能否|可以|能)\s*/, ' ')
  for (const re of NOISE) rest = rest.replace(re, ' ')
  rest = restore(rest)
  rest = rest.replace(ARTIFACT_WORDS, ' ')
  // 书名号**保留**：《故乡》是篇名，是主题本身。
  // 旧版把它当分隔符剔掉，"鲁迅《故乡》" 就被拆成 "鲁迅 故乡" —— 篇名没了。
  // 只有括号类才当分隔符。
  rest = rest.replace(/[【】\[\]""''（）()]/g, ' ')
  // "准备一节关于浮力的课" → "浮力的课"：量词剥离后残留的句尾"课"要收掉。
  // 必须在 tidy **之前**做：tidy 里有"去掉句首光杆量词名词"的规则，
  // 若先 tidy 再收句尾，第二次 tidy 会把「课间操的科学」的"课"当成量词吃掉。
  rest = rest.replace(/(?:的)?(?:课|课程)\s*$/, '')
  rest = rest.replace(/\s+/g, ' ')
  let topic = tidy(rest)
  // 整句就是一个书名时把书名号脱掉（"《浮力》" → "浮力"），
  // 但"鲁迅《故乡》"这种部分包裹的要原样保留。
  // 脱完要再收一次句尾的"的"，但不能调 tidy —— 它会把「课间操」的"课"当量词吃掉。
  topic = topic.replace(/^《(.+)》$/, '$1')
  topic = topic.replace(/\s+/g, ' ').replace(/\s*(?:的|地|得)$/, '').trim()

  // 学段没明说但年级认出来了 → 由年级派生。
  // 反过来不成立："高中语文"认得出学段认不出年级，所以两个字段都要留。
  if (!out.stage && out.grade) {
    if (/^[一二三四五六]年级$/.test(out.grade)) out.stage = '小学'
    else if (/^[七八九]年级$/.test(out.grade)) out.stage = '初中'
    else if (/^高[一二三]$/.test(out.grade)) out.stage = '普通高中'
    if (out.stage && !out.matched.includes('stage')) out.matched.push('stage')
  }

  // 只剩连接词/量词说明没读到东西，不要把它当成主题
  if (/^(?:的|地|得|一|两|三|[0-9]+)$/.test(topic)) topic = ''
  // 太短的不算主题（"课""节""份"），但拉丁字母/数字主题要放过（"PPT""3D"）
  if (topic.length < 2 && !/[A-Za-z0-9]/.test(topic)) topic = ''
  out.topic = topic
  // 主题存在即视为"他说了"：这是调用方决定要不要覆盖档案里旧主题的依据
  if (topic) out.matched.push('topic')

  return out
}

/**
 * 把推断结果贴到课程档案上，返回"改了什么"的人话列表。
 *
 * 规则：
 *   - 教师**明确说了**的字段（`matched` 命中）→ 覆盖，以他的话为准；
 *   - 没说但档案里空着的 → 补上；
 *   - 没说且档案里有值 → 不动（不要用一次顺口的话把之前的设定抹掉）。
 */
export function applyInferred(store, inferred) {
  const changes = []
  const said = (k) => inferred.matched.includes(k)

  if (inferred.topic && (said('topic') || !String(store.topic || '').trim())) {
    if (String(store.topic || '').trim() !== inferred.topic) {
      store.topic = inferred.topic
      changes.push(`主题「${inferred.topic}」`)
    }
  }
  if (inferred.subject && said('subject') && store.subject !== inferred.subject) {
    store.subject = inferred.subject
    changes.push(`学科「${inferred.subject}」`)
  }
  if (inferred.grade && said('grade') && store.grade !== inferred.grade) {
    store.grade = inferred.grade
    changes.push(`年级「${inferred.grade}」`)
  }
  // 学段只在"认得出学段、但年级还没定"时补：
  // 年级一旦确定，学段由它派生即可，不必再存一份（避免两份真值不一致）。
  if (inferred.stage && said('stage') && !store.grade) {
    changes.push(`学段「${inferred.stage}」`)
  }
  if (inferred.duration && said('duration') && store.duration !== inferred.duration) {
    store.duration = inferred.duration
    changes.push(`课时 ${inferred.duration} 分钟`)
  }
  return changes
}
