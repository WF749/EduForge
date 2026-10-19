"""互动游戏生成服务 - 生成可玩的HTML5小游戏"""
import os
import json
import uuid
from typing import Optional, Dict, List
from datetime import datetime
from .llm_service import llm_service


class GameGenerator:
    """互动游戏生成器 - 生成可玩的HTML5小游戏"""

    def __init__(self, output_dir: str = "generated_games"):
        """初始化游戏生成器"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, topic: str, audience: str, teaching_content: str,
                 game_type: Optional[str] = None, provider: Optional[str] = None) -> Dict:
        """生成互动游戏"""
        if provider:
            llm_service.set_provider(provider)

        # 生成唯一ID
        task_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_dir = os.path.join(self.output_dir, f"{topic}_{timestamp}_{task_id}")
        os.makedirs(task_dir, exist_ok=True)

        # 生成游戏内容
        game_data = self._generate_game_content(topic, audience, teaching_content, game_type)

        # 生成可玩的HTML5游戏
        html_path = self._create_playable_game(topic, audience, game_data, task_dir)

        # 保存游戏数据
        data_path = os.path.join(task_dir, "game_data.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump({
                "topic": topic,
                "audience": audience,
                "game_type": game_data.get('type'),
                "game_name": game_data.get('name'),
                "description": game_data.get('description'),
                "rules": game_data.get('rules'),
                "questions": game_data.get('questions', []),
                "html_path": html_path,
                "task_dir": task_dir
            }, f, ensure_ascii=False, indent=2)

        # 读取HTML内容用于前端内嵌预览
        html_content = ""
        if html_path and os.path.exists(html_path):
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception:
                pass

        return {
            "task_id": task_id,
            "topic": topic,
            "audience": audience,
            "game_type": game_data.get('type'),
            "game_name": game_data.get('name'),
            "description": game_data.get('description'),
            "rules": game_data.get('rules'),
            "game_data": game_data,
            "html_path": html_path,
            "html_content": html_content,
            "task_dir": task_dir
        }

    def _generate_game_content(self, topic: str, audience: str,
                              teaching_content: str, game_type: Optional[str]) -> Dict:
        """使用AI生成游戏内容"""
        # 确定游戏类型
        if not game_type:
            game_type = self._recommend_game_type(audience)

        prompt = f"""请为主题为'{topic}'、面向{audience}的教学内容设计一个互动小游戏。

教学内容：
{teaching_content}

游戏类型要求：{game_type}

请生成以下JSON格式的游戏设计（只输出JSON，不要其他内容）：
{{
    "name": "游戏名称",
    "type": "游戏类型（选择题/填空题/匹配题/排序题/闯关游戏）",
    "description": "游戏简介（50字内）",
    "rules": ["规则1", "规则2", "规则3"],
    "difficulty": "easy/medium/hard",
    "time_limit": 300,
    "questions": [
        {{
            "id": 1,
            "type": "choice",
            "question": "问题内容",
            "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
            "answer": "A. 选项A",
            "explanation": "答案解析（解释为什么选A）",
            "points": 10
        }}
    ],
    "rewards": ["奖励机制描述"]
}}

严格要求：
- 生成8-10道题目，题目与{topic}教学内容紧密相关
- **答案必须100%正确！** 请三次检查每道题的正确答案
- answer字段的值必须与options中某个选项的完整文本完全一致
- 每道题必须有详细的解析说明为什么答案正确
- 选项中不能出现错别字或事实性错误
- 难度适合{audience}的认知水平
- 如果是英语/单词相关主题，确保拼写正确
- 只输出JSON格式数据，不要其他说明文字"""

        try:
            result = llm_service.chat(prompt, purpose="game_code")
            # 尝试解析JSON
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                game_data = json.loads(json_match.group())
                qs = game_data.get("questions") or []
                game_data["questions"] = self._normalize_questions(qs)
                return game_data
        except Exception as e:
            print(f"解析游戏数据失败: {e}")

        # 默认游戏数据
        return self._get_default_game(topic, audience)

    def _recommend_game_type(self, audience: str) -> str:
        """根据受众推荐游戏类型"""
        recommendations = {
            "小学生": "选择题",
            "初中生": "选择题或闯关游戏",
            "高中生": "多种类型混合",
            "大一新生": "挑战赛或问答游戏",
            "大二学生": "专业挑战游戏",
            "研究生": "学术挑战游戏",
            "在职人员": "案例分析游戏",
            "公众": "趣味问答"
        }
        return recommendations.get(audience, "选择题")

    @staticmethod
    def _normalize_questions(questions: List) -> List:
        """将答案统一为与 options 中某项完全一致，避免仅写 A/B 导致前端判题失败。"""
        out = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            opts = q.get("options")
            if not opts or not isinstance(opts, list):
                out.append(q)
                continue
            ans = q.get("answer")
            if ans is None:
                out.append(q)
                continue
            ans_str = str(ans).strip()
            fixed = dict(q)
            # 已是某一选项原文
            if any(str(o).strip() == ans_str for o in opts):
                out.append(fixed)
                continue
            # 仅字母选项 A-D
            if len(ans_str) <= 2 and ans_str[:1].upper() in "ABCD":
                letter = ans_str[:1].upper()
                for opt in opts:
                    os = str(opt).strip()
                    if os.upper().startswith(letter + ".") or os.upper().startswith(letter + "．") or os.upper().startswith(letter + "、"):
                        fixed["answer"] = opt
                        break
                else:
                    # 选项仅为 A/B/C/D
                    for opt in opts:
                        if str(opt).strip().upper() == letter:
                            fixed["answer"] = opt
                            break
            out.append(fixed)
        return out

    def _get_default_game(self, topic: str, audience: str) -> Dict:
        """获取默认游戏数据"""
        return {
            "name": f"{topic}知识挑战",
            "type": "选择题",
            "description": f"测试你对{topic}知识的掌握程度",
            "rules": [
                "每题10分，共5题",
                "答对得分，答错不扣分",
                "完成后显示总分"
            ],
            "difficulty": "medium",
            "time_limit": 300,
            "questions": [
                {
                    "id": 1,
                    "type": "choice",
                    "question": f"关于{topic}，下列说法正确的是？",
                    "options": ["A. 正确选项", "B. 错误选项1", "C. 错误选项2", "D. 错误选项3"],
                    "answer": "A. 正确选项",
                    "explanation": f"这是关于{topic}的基础知识",
                    "points": 10
                }
            ],
            "rewards": ["完成挑战获得称号"]
        }

    def _create_playable_game(self, topic: str, audience: str,
                              game_data: Dict, task_dir: str) -> Optional[str]:
        """创建可玩的HTML5游戏"""
        try:
            game_type = game_data.get('type', '选择题')
            game_name = game_data.get('name', f'{topic}知识游戏')
            questions = game_data.get('questions', [])

            # 生成HTML游戏
            html_content = self._generate_game_html(game_name, game_type, questions, topic, audience)

            filename = f"{self._clean_filename(topic)}_game.html"
            filepath = os.path.join(task_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            return filepath
        except Exception as e:
            print(f"创建游戏HTML失败: {e}")
            return None

    def _generate_game_html(self, game_name: str, game_type: str,
                           questions: List, topic: str, audience: str) -> str:
        """生成游戏HTML - 增强版，含计时器、音效、进度、动画"""
        # 构建题目数据
        questions_json = json.dumps(questions, ensure_ascii=False)

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{game_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#0a0e27 0%,#1a1040 50%,#0d1333 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;color:#fff}}
.game-box{{background:rgba(20,24,60,0.95);border-radius:20px;box-shadow:0 8px 40px rgba(0,0,0,0.5);max-width:720px;width:100%;overflow:hidden;border:1px solid rgba(0,200,255,0.15)}}
.game-header{{background:linear-gradient(135deg,#00c8ff 0%,#7c3aed 100%);padding:20px 24px;display:flex;justify-content:space-between;align-items:center}}
.game-header h1{{font-size:22px}}
.timer-box{{display:flex;align-items:center;gap:8px;background:rgba(0,0,0,0.25);padding:8px 16px;border-radius:20px;font-size:15px;font-weight:600}}
.timer-box.warning{{animation:pulse 0.5s ease infinite alternate;color:#ff6b6b}}
@keyframes pulse{{to{{transform:scale(1.05)}}}}
.game-body{{padding:24px}}
.top-bar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.score-badge{{background:linear-gradient(135deg,#00c8ff,#7c3aed);padding:6px 16px;border-radius:20px;font-size:14px;font-weight:600}}
.progress-track{{height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;margin-bottom:20px}}
.progress-bar{{height:100%;background:linear-gradient(90deg,#00c8ff,#7c3aed);border-radius:4px;transition:width 0.4s ease}}
.q-card{{background:rgba(255,255,255,0.05);border-radius:16px;padding:24px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.08);animation:slideIn 0.4s ease}}
@keyframes slideIn{{from{{opacity:0;transform:translateX(30px)}}to{{opacity:1;transform:translateX(0)}}}}
.q-num{{font-size:13px;color:#00c8ff;margin-bottom:8px;font-weight:600}}
.q-text{{font-size:18px;line-height:1.6;margin-bottom:20px}}
.opts{{display:flex;flex-direction:column;gap:10px}}
.opt{{padding:14px 18px;background:rgba(255,255,255,0.06);border:2px solid rgba(255,255,255,0.1);border-radius:12px;cursor:pointer;transition:all 0.25s;font-size:15px;position:relative;overflow:hidden}}
.opt:hover{{border-color:rgba(0,200,255,0.5);background:rgba(0,200,255,0.08)}}
.opt.correct{{border-color:#22c55e;background:rgba(34,197,94,0.15)}}
.opt.correct::after{{content:'\\2714';position:absolute;right:16px;top:50%;transform:translateY(-50%);color:#22c55e;font-size:20px}}
.opt.wrong{{border-color:#ef4444;background:rgba(239,68,68,0.15)}}
.opt.wrong::after{{content:'\\2718';position:absolute;right:16px;top:50%;transform:translateY(-50%);color:#ef4444;font-size:20px}}
.opt.locked{{pointer-events:none;opacity:0.6}}
.explain{{margin-top:16px;padding:14px 18px;background:rgba(255,200,0,0.08);border-radius:12px;border-left:4px solid #ffd93d;font-size:14px;line-height:1.6;color:#d0d8e8;display:none}}
.explain.show{{display:block;animation:slideIn 0.3s ease}}
.next-btn{{display:block;width:100%;padding:14px;background:linear-gradient(135deg,#00c8ff,#7c3aed);border:none;border-radius:12px;color:#fff;font-size:16px;font-weight:600;cursor:pointer;transition:all 0.2s}}
.next-btn:hover{{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,200,255,0.3)}}
.next-btn:disabled{{opacity:0.4;cursor:not-allowed;transform:none;box-shadow:none}}
/* Screens */
.screen{{display:none}}.screen.active{{display:block}}
/* Start */
.start-center{{text-align:center;padding:50px 20px}}
.start-icon{{font-size:72px;margin-bottom:16px;animation:bounce 1s ease infinite alternate}}
@keyframes bounce{{to{{transform:translateY(-10px)}}}}
.start-center h2{{font-size:24px;margin-bottom:10px}}
.start-center p{{color:#8899bb;margin-bottom:30px}}
.start-btn{{display:inline-block;padding:14px 48px;background:linear-gradient(135deg,#00c8ff,#7c3aed);border:none;border-radius:30px;color:#fff;font-size:18px;font-weight:600;cursor:pointer;transition:all 0.2s}}
.start-btn:hover{{transform:scale(1.05)}}
/* Result */
.result-center{{text-align:center;padding:40px 20px}}
.result-score{{font-size:56px;font-weight:700;background:linear-gradient(135deg,#00c8ff,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:16px 0}}
.result-msg{{font-size:20px;margin-bottom:24px}}
.stars-row{{font-size:40px;margin:12px 0 24px}}
.stat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px}}
.stat-item{{background:rgba(255,255,255,0.05);border-radius:12px;padding:16px}}
.stat-item .label{{font-size:12px;color:#8899bb}}.stat-item .val{{font-size:22px;font-weight:700;margin-top:4px}}
.restart-btn{{display:inline-block;padding:12px 40px;background:rgba(255,255,255,0.1);border:2px solid rgba(0,200,255,0.4);border-radius:30px;color:#fff;font-size:16px;cursor:pointer;transition:all 0.2s}}
.restart-btn:hover{{background:rgba(0,200,255,0.15);transform:scale(1.05)}}
/* Fill input */
.fill-input{{width:100%;padding:14px;background:rgba(255,255,255,0.06);border:2px solid rgba(255,255,255,0.15);border-radius:12px;color:#fff;font-size:16px;outline:none}}
.fill-input:focus{{border-color:#00c8ff}}
.fill-submit{{margin-top:12px;padding:12px;background:linear-gradient(135deg,#00c8ff,#7c3aed);border:none;border-radius:10px;color:#fff;font-size:15px;width:100%;cursor:pointer}}
</style>
</head>
<body>
<div class="game-box">
<div class="game-header">
<h1>{game_name}</h1>
<div class="timer-box" id="timerBox">&#9201; <span id="timerText">05:00</span></div>
</div>
<div class="game-body">
<!-- Start Screen -->
<div class="screen active" id="startScreen">
<div class="start-center">
<div class="start-icon">&#127918;</div>
<h2>准备好挑战了吗？</h2>
<p>主题: {topic} | 面向: {audience}</p>
<button class="start-btn" onclick="startGame()">&#9654; 开始挑战</button>
</div>
</div>
<!-- Game Screen -->
<div class="screen" id="gameScreen">
<div class="top-bar">
<span class="q-num" id="qLabel">第 1 题 / 共 ? 题</span>
<span class="score-badge" id="scoreBadge">&#127942; 0 分</span>
</div>
<div class="progress-track"><div class="progress-bar" id="pBar" style="width:0%"></div></div>
<div class="q-card" id="qCard">
<div class="q-text" id="qText"></div>
<div class="opts" id="optsBox"></div>
<div class="explain" id="explainBox"></div>
</div>
<button class="next-btn" id="nextBtn" onclick="nextQ()" disabled>下一题 &#9654;</button>
</div>
<!-- Result Screen -->
<div class="screen" id="resultScreen">
<div class="result-center">
<div class="stars-row" id="starsRow"></div>
<div class="result-score" id="finalScore">0</div>
<div style="font-size:14px;color:#8899bb;margin-bottom:8px">总分</div>
<div class="result-msg" id="resultMsg"></div>
<div class="stat-grid">
<div class="stat-item"><div class="label">正确</div><div class="val" id="statCorrect" style="color:#22c55e">0</div></div>
<div class="stat-item"><div class="label">错误</div><div class="val" id="statWrong" style="color:#ef4444">0</div></div>
<div class="stat-item"><div class="label">用时</div><div class="val" id="statTime" style="color:#00c8ff">-</div></div>
</div>
<button class="restart-btn" onclick="restart()">&#128260; 再来一次</button>
</div>
</div>
</div>
</div>
<script>
const QS={questions_json};
let ci=0,score=0,answered=false,correct=0,wrong=0,timer=null,timeLeft=300,startTime=0;
function $(id){{return document.getElementById(id)}}
function startGame(){{
  $('startScreen').classList.remove('active');
  $('gameScreen').classList.add('active');
  startTime=Date.now();
  timeLeft=300;
  score=0;ci=0;correct=0;wrong=0;answered=false;
  timer=setInterval(tick,1000);
  showQ();
}}
function tick(){{
  timeLeft--;
  if(timeLeft<=0){{clearInterval(timer);showResult();return}}
  const m=Math.floor(timeLeft/60),s=timeLeft%60;
  $('timerText').textContent=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  $('timerBox').classList.toggle('warning',timeLeft<=30);
}}
function showQ(){{
  answered=false;
  const q=QS[ci];
  $('qLabel').textContent=`第 ${{ci+1}} 题 / 共 ${{QS.length}} 题`;
  $('pBar').style.width=((ci)/QS.length*100)+'%';
  $('scoreBadge').textContent='\\u{{1F3C6}} '+score+' \\u5206';
  $('qText').textContent=q.question;
  $('explainBox').classList.remove('show');
  $('nextBtn').disabled=true;
  if(ci===QS.length-1) $('nextBtn').textContent='查看结果 \\u{{1F3C6}}';
  const box=$('optsBox');box.innerHTML='';
  // Re-trigger card animation
  const card=$('qCard');card.style.animation='none';card.offsetHeight;card.style.animation='';
  if(q.options&&q.options.length){{
    q.options.forEach(opt=>{{
      const d=document.createElement('div');
      d.className='opt';d.textContent=opt;
      d.onclick=function(){{pick(d,opt,q)}};
      box.appendChild(d);
    }});
  }} else {{
    box.innerHTML='<input class="fill-input" id="fillAns" placeholder="请输入答案" onkeydown="if(event.key===\\'Enter\\')submitFill()"><button class="fill-submit" onclick="submitFill()">提交答案</button>';
  }}
}}
function pick(el,sel,q){{
  if(answered)return;answered=true;
  document.querySelectorAll('.opt').forEach(o=>o.classList.add('locked'));
  if(sel===q.answer){{
    el.classList.add('correct');
    score+=(q.points||10);correct++;
  }}else{{
    el.classList.add('wrong');wrong++;
    document.querySelectorAll('.opt').forEach(o=>{{if(o.textContent===q.answer)o.classList.add('correct')}});
  }}
  $('scoreBadge').textContent='\\u{{1F3C6}} '+score+' 分';
  $('explainBox').textContent='\\u{{1F4A1}} '+( q.explanation||'');
  $('explainBox').classList.add('show');
  $('nextBtn').disabled=false;
}}
function submitFill(){{
  if(answered)return;answered=true;
  const q=QS[ci],ans=$('fillAns').value.trim();
  if(ans===q.answer){{score+=(q.points||10);correct++}}else{{wrong++}}
  $('scoreBadge').textContent='\\u{{1F3C6}} '+score+' 分';
  $('explainBox').textContent='\\u{{1F4A1}} 正确答案: '+q.answer+' | '+(q.explanation||'');
  $('explainBox').classList.add('show');
  $('nextBtn').disabled=false;
}}
function nextQ(){{
  ci++;
  if(ci<QS.length){{showQ()}}else{{showResult()}}
}}
function showResult(){{
  clearInterval(timer);
  $('gameScreen').classList.remove('active');
  $('resultScreen').classList.add('active');
  const maxS=QS.reduce((s,q)=>s+(q.points||10),0);
  const pct=maxS>0?(score/maxS*100):0;
  const elapsed=Math.round((Date.now()-startTime)/1000);
  const em=Math.floor(elapsed/60),es=elapsed%60;
  $('finalScore').textContent=score+'/'+maxS;
  $('statCorrect').textContent=correct;
  $('statWrong').textContent=wrong;
  $('statTime').textContent=em+'分'+String(es).padStart(2,'0')+'秒';
  let stars='',msg='';
  if(pct>=90){{stars='\\u2B50\\u2B50\\u2B50';msg='太棒了！你是学霸！'}}
  else if(pct>=70){{stars='\\u2B50\\u2B50';msg='很不错！继续加油！'}}
  else if(pct>=50){{stars='\\u2B50';msg='还需要多加学习哦！'}}
  else{{stars='\\u{{1F4AA}}';msg='别灰心，再来一次吧！'}}
  $('starsRow').textContent=stars;
  $('resultMsg').textContent=msg;
}}
function restart(){{
  $('resultScreen').classList.remove('active');
  $('startScreen').classList.add('active');
  $('nextBtn').textContent='下一题 \\u25B6';
  $('timerText').textContent='05:00';
  $('timerBox').classList.remove('warning');
}}
</script>
</body>
</html>'''

    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        return filename[:50]

    def get_game_types(self) -> List[Dict]:
        """获取支持的游戏类型"""
        return [
            {"id": "选择题", "name": "知识问答", "description": "选择题形式测试知识点"},
            {"id": "填空题", "name": "填空挑战", "description": "填写正确答案"},
            {"id": "匹配题", "name": "连连看", "description": "匹配相关概念"},
            {"id": "排序题", "name": "排序挑战", "description": "按正确顺序排列"},
            {"id": "闯关游戏", "name": "知识闯关", "description": "逐关挑战获取胜利"}
        ]
