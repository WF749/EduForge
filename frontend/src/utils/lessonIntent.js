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
  /(?:生成|创建|制作|设计|写|做|搞|出|来一?[份个节堂])/g,
  /(?:一|两|三|[0-9]+)\s*[份个节堂]/g,
  // "内容是浮力""主题是一次函数" —— 冒号后才是主题，冒号前全是引导语
  /(?:内容是|内容是|内容为|主题是|主题为|课题是|课题为|讲的是|教的是|内容|主题|课题)/g,
  /(?:关于|有关|围绕)/g,
  // 学段词：它不是主题（"初中八年级生物《细胞的结构》"里的"初中"）
  /(?:小学|初中|高中|中职|职高|大学)/g,
  /(?:一下|一遍|一趟)/g,
  // 语气尾巴：留在主题里会变成"浮力 吗"
  /(?:吧|呢|啊|哦|哈|呀|吗|好吗|行吗|谢谢)\s*$/g,
]

/** 成品类型词 —— 它们不是主题的一部分，是"要做什么" */
const ARTIFACT_WORDS = /(?:教学设计|课时设计|备课|教案|PPT|ppt|Ppt|课件|幻灯片|演示文稿|微课|演示动画|动画|互动小游戏|互动游戏|小游戏|游戏|闯关)/g

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
    .replace(/^[\s，,。.、；;：:!！?？'"""''（）()《》【】\[\]-]+/, '')
    .replace(/[\s，,。.、；;：:!！?？'"""''（）()《》【】\[\]-]+$/, '')
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
  const out = { topic: '', subject: '', grade: '', duration: 0, matched: [] }
  if (!raw) return out

  // ---- 先认学科 / 年级 / 时长：认出来之后要把它们从主题里剔掉 ----
  let rest = raw

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
  rest = rest.replace(ARTIFACT_WORDS, ' ')
  // 书名号/引号只当分隔符：去掉它们，别让《》留进主题
  rest = rest.replace(/[《》〈〉【】\[\]""''「」『』（）()]/g, ' ')
  rest = rest.replace(/\s+/g, ' ')
  let topic = tidy(rest)

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
  if (inferred.duration && said('duration') && store.duration !== inferred.duration) {
    store.duration = inferred.duration
    changes.push(`课时 ${inferred.duration} 分钟`)
  }
  return changes
}
