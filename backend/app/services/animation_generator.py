"""动画演示生成服务 - LLM驱动生成HTML5教学演示动画"""
import os
import json
import uuid
import re
from typing import Optional, Dict, List, Any
from datetime import datetime
from .llm_service import llm_service

# 导入新的分层动画系统
from .animation import (
    content_parser,
    animation_engine,
    SubjectType
)


class AnimationGenerator:
    """动画演示生成器 - LLM驱动，生成可直接运行的HTML5教学演示动画"""

    def __init__(self, output_dir: str = "generated_animations"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, topic: str, audience: str, teaching_content: str,
                 duration: int = 5, provider: Optional[str] = None,
                 style: str = "") -> Dict:
        """生成教学演示动画——LLM驱动HTML5，不依赖预设风格选项"""
        if provider:
            llm_service.set_provider(provider)

        brief = (teaching_content or "").strip()
        if not brief:
            brief = (topic or "").strip()

        # 增强：用户只给了主题、没给教学文本时，用 LLM 生成简要教学内容，
        # 让知识点抽取与场景编排有真实素材（否则会退回泛型占位“核心概念”）。
        enriched = None
        if not (teaching_content or "").strip():
            enriched = self._llm_enrich(topic, audience)
            if enriched:
                brief = enriched.get("brief") or brief
                teaching_content = brief

        combined = f"{topic or ''}\n{teaching_content or ''}".strip()

        task_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_dir = os.path.join(self.output_dir, f"{self._clean_filename(topic)}_{timestamp}_{task_id}")
        os.makedirs(task_dir, exist_ok=True)

        html_path = None
        generation_method = "canvas_demo"
        animation_data = {}
        subject = None
        knowledge_points = []
        scenes = []

        # 第0层：新分层动画系统 - 学科特定组件（优先，质量最高）
        try:
            new_system_result = self._generate_with_new_animation_system(
                topic, audience, combined or brief, task_dir
            )
            if new_system_result and new_system_result.get("html_path"):
                html_path = new_system_result.get("html_path")
                subject = new_system_result.get("subject")
                knowledge_points = new_system_result.get("knowledge_points", [])
                scenes = new_system_result.get("scenes", [])
                generation_method = "subject_specific"
                print(f"[动画生成] 新分层系统成功生成学科特定动画")
        except Exception as e:
            print(f"[动画生成] 新分层系统生成失败: {e}")

        # 知识点增强：解析器是纯正则，常常只能产出 1-2 个泛型知识点。
        # 判断依据是"知识点本身够不够好"，而不是"用户有没有给教学文本"——
        # 否则用户给了文本、但文本没命中正则模式时，反而会退化成泛型的
        # 「核心概念」，比不给文本时更差。
        if self._needs_richer_knowledge_points(knowledge_points):
            if enriched is None:
                # 上面只在「无教学文本」分支抽过一次，这里按需补抽
                enriched = self._llm_enrich(topic, audience)
            llm_kps = (enriched or {}).get("knowledge_points") or []
            if llm_kps:
                knowledge_points = llm_kps
                if not subject:
                    subject = "general"

        # 第1层：LLM生成HTML5动画（核心路径）
        if not html_path:
            try:
                html_path = self._generate_llm_html5_animation_v2(
                    topic, audience, combined or brief, task_dir
                )
                if html_path:
                    generation_method = "llm_html5"
                    print(f"[动画生成] LLM成功生成HTML5动画")
            except Exception as e:
                print(f"[动画生成] LLM HTML5动画生成失败: {e}")

        # 第2层：通用Canvas动画（不依赖LLM，任何主题都能工作）
        if not html_path:
            try:
                html_path = self._create_canvas_demo_animation(
                    topic, audience, combined or brief, task_dir
                )
                if html_path:
                    generation_method = "canvas_demo"
                    print(f"[动画生成] 使用Canvas演示动画")
            except Exception as e:
                print(f"[动画生成] Canvas演示动画生成失败: {e}")

        # 第3层：传统分镜预览（最终回退）
        if not html_path:
            animation_data = self._generate_animation_content_v2(topic, audience, combined or brief)
            html_path = self._create_animation_preview(topic, audience, animation_data, task_dir)
            generation_method = "storyboard_fallback"
            print(f"[动画生成] 使用分镜预览回退")

        # 读取HTML内容用于前端内嵌预览
        html_content = ""
        if html_path and os.path.exists(html_path):
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception as e:
                print(f"[动画生成] 读取HTML内容失败: {e}")

        # 保存动画数据
        data_path = os.path.join(task_dir, "animation_data.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump({
                "topic": topic, "audience": audience, "duration": duration,
                "animation_data": animation_data, "html_path": html_path, "task_dir": task_dir
            }, f, ensure_ascii=False, indent=2)

        return {
            "task_id": task_id, "topic": topic, "audience": audience, "duration": duration,
            "animation_data": animation_data, "html_path": html_path,
            "html_content": html_content, "task_dir": task_dir,
            "generation_method": generation_method,
            "subject": subject,
            "knowledge_points": knowledge_points,
            "scenes": scenes
        }

    def _generate_with_new_animation_system(self, topic: str, audience: str, 
                                             teaching_content: str, task_dir: str) -> Optional[Dict]:
        """使用新分层动画系统生成学科特定的高质量动画"""
        # 1. 内容解析
        analysis_result = content_parser.parse(teaching_content, topic, audience)
        
        # 2. 生成动画项目
        project = animation_engine.generate_animation_project(analysis_result, topic, audience)
        
        # 3. 生成HTML动画
        html_content = animation_engine.generate_html_animation(project)
        
        # 4. 保存文件
        if html_content:
            filename = f"{self._clean_filename(topic)}_subject_animation.html"
            filepath = os.path.join(task_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 同时保存项目JSON供后续使用
            project_path = os.path.join(task_dir, "animation_project.json")
            with open(project_path, 'w', encoding='utf-8') as f:
                json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
            
            # 转换知识点为字典格式
            kp_dicts = []
            for kp in analysis_result.knowledge_points:
                kp_dicts.append({
                    "id": kp.id,
                    "name": kp.name,
                    "description": kp.description,
                    "subject": kp.subject.value if hasattr(kp.subject, 'value') else str(kp.subject),
                    "difficulty": kp.difficulty,
                    "related_concepts": kp.related_concepts,
                    "examples": kp.examples,
                    "visual_hints": kp.visual_hints
                })
            
            # 转换场景
            scene_dicts = []
            for scene in project.scenes:
                scene_dicts.append({
                    "id": scene.id,
                    "title": scene.title,
                    "description": scene.description,
                    "duration": scene.duration,
                    "narration": scene.narration,
                    "key_points": scene.key_points
                })
            
            return {
                "html_path": filepath,
                "html_content": html_content,
                "subject": analysis_result.subject.value if hasattr(analysis_result.subject, 'value') else str(analysis_result.subject),
                "knowledge_points": kp_dicts,
                "scenes": scene_dicts,
                "difficulty_level": analysis_result.difficulty_level,
                "target_audience": analysis_result.target_audience,
                "key_concepts": analysis_result.key_concepts
            }
        
        return None

    # 正则解析器在没命中任何模式时产出的占位名，这类名字没有任何信息量
    _GENERIC_KP_NAMES = {"核心概念", "概念", "知识点", "重点", "主要内容"}

    def _needs_richer_knowledge_points(self, knowledge_points) -> bool:
        """判断知识点是否差到需要用 LLM 重新抽取。

        两种信号都算"不够好"：
          1. 数量过少（≤2）—— 说明正则基本没解析出东西；
          2. 仍是泛型占位名（如"核心概念"）—— 即使数量够也没信息量。
        """
        if not knowledge_points:
            return True
        if len(knowledge_points) <= 2:
            return True
        for kp in knowledge_points:
            name = (kp.get("name") if isinstance(kp, dict) else str(kp)) or ""
            if name.strip() in self._GENERIC_KP_NAMES:
                return True
        return False

    def _llm_enrich(self, topic: str, audience: str) -> Optional[Dict]:
        """仅当用户没提供教学文本时调用：用 LLM 生成简要教学内容 + 结构化知识点。

        返回 {"brief": str, "knowledge_points": [dict, ...]}；失败返回 None（调用方回退到原逻辑）。
        这是动画知识点偏模板化的根因修复点：原 content_parser 纯正则，无文本时只能产出泛型占位。
        """
        prompt = f"""你是学科教学专家。请为主题「{topic}」（面向{audience}）准备动画教学素材。
只输出一个 JSON 对象（不要任何解释文字），结构如下：
{{
  "brief": "3-5 句连贯的教学内容，覆盖核心概念、原理与典型例子；句式可用『XX是指…』『XX表明…』，不要重复堆叠主题词",
  "knowledge_points": [
    {{"name": "具体知识点名（不要只写主题词，要写如『阿基米德原理』『物体的浮沉条件』这类子知识点）", "description": "一句话准确解释", "difficulty": 2, "examples": ["一个生活或实验例子"], "visual_hints": ["一个可视化建议"]}}
  ]
}}
要求：knowledge_points 必须 3-5 个，彼此不同且都紧扣「{topic}」，difficulty 取 1-3（1基础/2进阶/3难点）。"""

        try:
            result = llm_service.chat(prompt, purpose="animation_code")
            start = result.find('{')
            if start < 0:
                return None
            depth = 0
            end = -1
            for i in range(start, len(result)):
                if result[i] == '{':
                    depth += 1
                elif result[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end < 0:
                return None
            data = json.loads(result[start:end + 1])

            kps = data.get("knowledge_points") or []
            clean = []
            for kp in kps[:5]:
                if not isinstance(kp, dict) or not kp.get("name"):
                    continue
                clean.append({
                    "id": "kp_llm_" + uuid.uuid4().hex[:6],
                    "name": str(kp.get("name"))[:30],
                    "description": str(kp.get("description") or "")[:200],
                    "subject": "general",
                    "difficulty": int(kp.get("difficulty") or 1),
                    "examples": kp.get("examples") or [],
                    "visual_hints": kp.get("visual_hints") or [],
                })
            if not clean:
                return None
            return {"brief": str(data.get("brief") or ""), "knowledge_points": clean}
        except Exception as e:
            print(f"[动画生成] LLM 增强失败（已安全回退）: {e}")
            return None

    def _generate_llm_html5_animation_v2(self, topic: str, audience: str, teaching_content: str, task_dir: str) -> Optional[str]:
        """LLM驱动的HTML5教学动画生成"""
        brief = (teaching_content or "")[:3000]

        prompt = f"""你是一名资深HTML5教育动画开发专家。请根据以下教学内容，生成一个完整的、可直接在浏览器中运行的HTML5教学演示动画。

【教学主题】{topic}
【目标受众】{audience}
【教学内容】
{brief}

【核心要求】
1. 仅使用 HTML + CSS + 原生 JavaScript，禁止引用任何CDN或第三方库。
2. 必须包含 Canvas 绘图或 SVG 图形来可视化教学概念，不能只是文字。
3. 需要包含以下交互控件：播放/暂停按钮、上一步/下一步、场景进度指示器。
4. 动画应该分步骤展示教学内容，每个步骤之间有自然的过渡。
5. 颜色方案干净专业，适合课堂演示。
6. 页面长度完整可运行，从 <!DOCTYPE html> 到 </html> 完整输出。

请直接输出完整的HTML源码，不要任何解释文字。"""

        try:
            result = llm_service.chat(prompt, purpose="animation_code")

            html_match = re.search(r"<!DOCTYPE html>.*?</html>", result, re.DOTALL | re.IGNORECASE)
            if not html_match:
                html_match = re.search(r"<html.*?>.*?</html>", result, re.DOTALL | re.IGNORECASE)

            if html_match:
                html_code = html_match.group()
                low = html_code.lower()
                has_animation = any(kw in low for kw in ["animation", "canvas", "requestanimationframe", "<svg"])
                has_content = len(html_code) > 1500 or (has_animation and len(html_code) > 800)
                
                if not has_content:
                    print(f"[动画生成] LLM生成的HTML不满足要求")
                    return None

                filename = f"{self._clean_filename(topic)}_llm.html"
                filepath = os.path.join(task_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_code)
                return filepath

        except Exception as e:
            print(f"[动画生成] LLM HTML5动画生成异常: {e}")

        return None

    def _create_canvas_demo_animation(self, topic: str, audience: str, teaching_content: str, task_dir: str) -> Optional[str]:
        """通用Canvas教学演示——自动提取知识点生成多步骤可交互动画"""
        tc = (teaching_content or topic).strip()[:2000]
        scenes = self._extract_teaching_scenes(topic, tc)
        scenes_json = json.dumps(scenes, ensure_ascii=False)

        # 读取外部HTML模板文件
        template_path = os.path.join(os.path.dirname(__file__), 'animation_template.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
        else:
            # 使用内置模板
            html = self._get_canvas_template()

        html = html.replace('__TOPIC__', topic)
        html = html.replace('__AUDIENCE__', audience)
        html = html.replace('__SCENES__', scenes_json)

        filename = f"{self._clean_filename(topic)}_canvas.html"
        filepath = os.path.join(task_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        return filepath

    def _get_canvas_template(self) -> str:
        """获取内置的Canvas动画模板"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TOPIC__ - 教学演示动画</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Microsoft YaHei','PingFang SC',sans-serif;background:#0f1724;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px}}
.header{{text-align:center;padding:16px 0}}
.header h1{{font-size:28px;background:linear-gradient(135deg,#38bdf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}}
.header p{{font-size:14px;color:#64748b}}
.player{{width:100%;max-width:960px;background:#1e293b;border-radius:20px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.4)}}
.canvas-wrap{{position:relative;width:100%;height:500px;overflow:hidden;background:#0f1724}}
canvas{{display:block;width:100%;height:100%}}
.overlay{{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);display:flex;gap:10px;background:rgba(15,23,36,0.9);padding:12px 24px;border-radius:30px;backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1)}}
.step-dot{{width:12px;height:12px;border-radius:50%;background:#475569;cursor:pointer;transition:all 0.3s ease;border:2px solid transparent}}
.step-dot:hover{{transform:scale(1.3);background:#64748b}}
.step-dot.active{{background:#38bdf8;transform:scale(1.5);box-shadow:0 0 12px rgba(56,189,248,0.6);border-color:#fff}}
.controls{{display:flex;align-items:center;gap:16px;padding:20px 24px;background:rgba(0,0,0,0.2)}}
.ctrl-btn{{width:44px;height:44px;border-radius:50%;border:none;cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all 0.25s;color:#e2e8f0}}
.ctrl-btn.play{{background:linear-gradient(135deg,#38bdf8,#a78bfa);color:#fff;font-size:20px}}
.ctrl-btn.nav{{background:rgba(255,255,255,0.1)}}
.ctrl-btn:hover{{transform:scale(1.15);background:rgba(255,255,255,0.2)}}
.progress-bar{{flex:1;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;cursor:pointer}}
.progress-fill{{height:100%;background:linear-gradient(90deg,#38bdf8,#a78bfa);border-radius:3px;transition:width 0.5s ease}}
.step-info{{display:flex;align-items:center;gap:12px;color:#94a3b8;font-size:13px}}
.step-number{{font-weight:600;color:#38bdf8}}
.keywords{{display:flex;gap:8px;flex-wrap:wrap;padding:16px 24px;background:rgba(0,0,0,0.1);border-top:1px solid rgba(255,255,255,0.05)}}
.keyword-tag{{background:rgba(56,189,248,0.15);color:#38bdf8;padding:6px 14px;border-radius:20px;font-size:12px;border:1px solid rgba(56,189,248,0.3)}}
</style>
</head>
<body>
<div class="header">
  <h1>__TOPIC__</h1>
  <p>面向__AUDIENCE__ | 交互式教学演示</p>
</div>
<div class="player">
  <div class="canvas-wrap">
    <canvas id="canvas"></canvas>
    <div class="overlay" id="stepOverlay"></div>
  </div>
  <div class="controls">
    <button class="ctrl-btn nav" onclick="prevScene()" title="上一步">&#9664;</button>
    <button class="ctrl-btn play" id="playBtn" onclick="togglePlay()">&#9654;</button>
    <button class="ctrl-btn nav" onclick="nextScene()" title="下一步">&#9654;</button>
    <div class="progress-bar" onclick="seekScene(event)"><div class="progress-fill" id="progressFill"></div></div>
    <div class="step-info">
      <span class="step-number" id="stepNumber">1</span>
      <span>/</span>
      <span id="totalSteps">1</span>
    </div>
  </div>
  <div class="keywords" id="keywords"></div>
</div>
<script>
const scenes = __SCENES__;
let cur = 0, playing = false, timer = null;
let canvas, ctx, W, H;

function initCanvas() {
  canvas = document.getElementById('canvas');
  ctx = canvas.getContext('2d');
  function resize() {
    const wrap = canvas.parentElement;
    W = canvas.width = wrap.clientWidth;
    H = canvas.height = wrap.clientHeight;
    drawScene(cur);
  }
  resize();
  window.addEventListener('resize', resize);
}

function drawScene(idx) {
  if (!ctx || !scenes[idx]) return;
  ctx.clearRect(0, 0, W, H);
  const s = scenes[idx];
  const c = s.color || '#38bdf8';
  const t = Date.now() / 1000;

  const bg = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W,H)*0.8);
  bg.addColorStop(0, '#1e293b');
  bg.addColorStop(1, '#0f1724');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  drawGrid(c, t);
  drawParticles(c, t);
  drawCenterGraphic(idx, s, c, t);

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = 'bold ' + Math.min(40, W/14) + 'px Microsoft YaHei';
  const titleGrad = ctx.createLinearGradient(W/2-250, H*0.15, W/2+250, H*0.15);
  titleGrad.addColorStop(0, '#38bdf8');
  titleGrad.addColorStop(1, '#a78bfa');
  ctx.fillStyle = titleGrad;
  ctx.fillText(s.title, W/2, H*0.15);

  ctx.font = Math.min(18, W/42) + 'px Microsoft YaHei';
  ctx.fillStyle = '#94a3b8';
  const desc = s.desc || '';
  const lines = wrapText(ctx, desc, W*0.7);
  lines.forEach((line, i) => {
    ctx.fillText(line, W/2, H*0.25 + i*30);
  });
}

function drawGrid(color, t) {
  ctx.strokeStyle = color + '08';
  ctx.lineWidth = 1;
  const gridSize = 50 + Math.sin(t*0.2) * 10;
  for (let x = (t * 20) % gridSize; x < W; x += gridSize) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = (t * 20) % gridSize; y < H; y += gridSize) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
}

function drawParticles(color, t) {
  const r = parseInt(color.slice(1,3),16);
  const g = parseInt(color.slice(3,5),16);
  const b = parseInt(color.slice(5,7),16);
  
  for (let i = 0; i < 20; i++) {
    const px = (Math.sin(t*0.5 + i*1.3) * 0.5 + 0.5) * W;
    const py = (Math.cos(t*0.3 + i*0.8) * 0.4 + 0.6) * H;
    const size = 3 + Math.sin(t*2 + i) * 2;
    const alpha = 0.15 + Math.sin(t*1.5 + i*0.5) * 0.15;
    
    ctx.beginPath();
    ctx.arc(px, py, size, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    ctx.fill();
    
    ctx.beginPath();
    ctx.arc(px, py, size * 2.5, 0, Math.PI*2);
    const gradient = ctx.createRadialGradient(px, py, 0, px, py, size * 2.5);
    gradient.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + (alpha*0.5) + ')');
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gradient;
    ctx.fill();
  }
}

function drawCenterGraphic(idx, s, color, t) {
  const cx = W / 2;
  const cy = H / 2;
  const r = Math.min(W, H) * 0.25;
  
  const patterns = [
    () => drawCirclePattern(cx, cy, r, color, t),
    () => drawSquarePattern(cx, cy, r, color, t),
    () => drawTrianglePattern(cx, cy, r, color, t),
    () => drawStarPattern(cx, cy, r, color, t),
    () => drawHexagonPattern(cx, cy, r, color, t),
    () => drawWavePattern(cx, cy, r, color, t),
  ];
  
  const patternIdx = idx % patterns.length;
  patterns[patternIdx]();
}

function drawCirclePattern(cx, cy, r, color, t) {
  for (let i = 3; i >= 1; i--) {
    const radius = r * (0.5 + i * 0.25);
    const pulse = 0.8 + Math.sin(t * 2 + i) * 0.2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * pulse, 0, Math.PI * 2);
    ctx.strokeStyle = color + (Math.floor((40 + i * 20) * pulse).toString(16).padStart(2, '0'));
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.3, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function drawSquarePattern(cx, cy, r, color, t) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(t * 0.5);
  
  for (let i = 2; i >= 1; i--) {
    const size = r * i * 0.6;
    const offset = (t * 50) % 20;
    ctx.beginPath();
    ctx.rect(-size/2 + offset, -size/2 + offset, size, size);
    ctx.strokeStyle = color + (60 - i * 15).toString(16).padStart(2, '0');
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  
  ctx.fillStyle = color;
  ctx.fillRect(-r * 0.15, -r * 0.15, r * 0.3, r * 0.3);
  ctx.restore();
}

function drawTrianglePattern(cx, cy, r, color, t) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(t * 0.3);
  
  for (let i = 2; i >= 1; i--) {
    const size = r * i * 0.7;
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.866, size * 0.5);
    ctx.lineTo(-size * 0.866, size * 0.5);
    ctx.closePath();
    ctx.strokeStyle = color + (50 - i * 15).toString(16).padStart(2, '0');
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0, -r * 0.2);
  ctx.lineTo(r * 0.17, r * 0.1);
  ctx.lineTo(-r * 0.17, r * 0.1);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawStarPattern(cx, cy, r, color, t) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(t * 0.4);
  
  for (let i = 2; i >= 1; i--) {
    const size = r * i * 0.6;
    drawStar(0, 0, size, 5, color + (50 - i * 15).toString(16).padStart(2, '0'));
  }
  
  ctx.fillStyle = color;
  drawStar(0, 0, r * 0.2, 5, color);
  ctx.restore();
}

function drawStar(cx, cy, r, points, color) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const radius = i % 2 === 0 ? r : r * 0.5;
    const angle = (i * Math.PI) / points - Math.PI / 2;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fill();
}

function drawHexagonPattern(cx, cy, r, color, t) {
  ctx.save();
  ctx.translate(cx, cy);
  
  for (let i = 3; i >= 1; i--) {
    const size = r * (0.4 + i * 0.2);
    const rotation = (t * 0.2 + i * 0.3);
    ctx.save();
    ctx.rotate(rotation);
    drawHexagon(0, 0, size, color + (40 + i * 10).toString(16).padStart(2, '0'));
    ctx.restore();
  }
  
  ctx.fillStyle = color;
  drawHexagon(0, 0, r * 0.2, color);
  ctx.restore();
}

function drawHexagon(cx, cy, r, color) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const angle = (i * Math.PI * 2) / 6 - Math.PI / 2;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fill();
}

function drawWavePattern(cx, cy, r, color, t) {
  ctx.beginPath();
  ctx.moveTo(cx - r * 1.5, cy);
  
  for (let x = cx - r * 1.5; x <= cx + r * 1.5; x += 10) {
    const y = cy + Math.sin((x - cx) * 0.02 + t * 3) * (r * 0.3);
    ctx.lineTo(x, y);
  }
  
  ctx.strokeStyle = color + '80';
  ctx.lineWidth = 3;
  ctx.stroke();
  
  ctx.beginPath();
  ctx.moveTo(cx - r * 1.5, cy);
  for (let x = cx - r * 1.5; x <= cx + r * 1.5; x += 10) {
    const y = cy + Math.sin((x - cx) * 0.02 + t * 3 + Math.PI) * (r * 0.2);
    ctx.lineTo(x, y);
  }
  ctx.strokeStyle = color + '50';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function wrapText(ctx, text, maxW) {
  const words = text.split('');
  const lines = [];
  let line = '';
  for (let c of words) {
    const test = line + c;
    if (ctx.measureText(test).width > maxW && line.length > 0) {
      lines.push(line);
      line = c;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, 4);
}

function buildDots() {
  const dots = scenes.map((_,i) => '<div class="step-dot ' + (i===cur?'active':'') + '" onclick="goTo(' + i + ')"></div>').join('');
  document.getElementById('stepOverlay').innerHTML = dots;
  document.getElementById('totalSteps').textContent = scenes.length;
}

function updateUI() {
  drawScene(cur);
  document.querySelectorAll('.step-dot').forEach((d,i) => d.classList.toggle('active', i===cur));
  document.getElementById('progressFill').style.width = ((cur+1)/scenes.length*100)+'%';
  document.getElementById('stepNumber').textContent = cur + 1;
  
  const s = scenes[cur];
  if (s.keywords && s.keywords.length > 0) {
    document.getElementById('keywords').innerHTML = s.keywords.map(k => '<span class="keyword-tag">' + k + '</span>').join('');
  } else {
    document.getElementById('keywords').innerHTML = '';
  }
}

function nextScene() { cur = (cur + 1) % scenes.length; updateUI(); }
function prevScene() { cur = (cur - 1 + scenes.length) % scenes.length; updateUI(); }
function goTo(i) { cur = i; updateUI(); }
function seekScene(e) { 
  const r = e.target.getBoundingClientRect(); 
  cur = Math.min(Math.floor((e.clientX-r.left)/r.width*scenes.length), scenes.length-1); 
  updateUI(); 
}
function togglePlay() {
  playing = !playing;
  document.getElementById('playBtn').innerHTML = playing ? '&#x23F8;' : '&#x25B6;';
  if (playing) {
    timer = setInterval(nextScene, 5000);
  } else {
    clearInterval(timer);
  }
}

function animateLoop() {
  drawScene(cur);
  requestAnimationFrame(animateLoop);
}

initCanvas();
buildDots();
updateUI();
requestAnimationFrame(animateLoop);
</script>
</body>
</html>'''

    def _extract_teaching_scenes(self, topic: str, content: str) -> List[Dict]:
        """从教学内容中自动提取教学步骤"""
        scenes = []
        lines = content.replace('\r', '\n').split('\n')
        step_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[\d一二三四五六七八九十]+[\.、．)）\s]', line) or \
               re.match(r'^[\(（]?[\d一二三四五六七八九十]+[\)）]', line) or \
               re.match(r'^[步骤][\d一二三四五六七八九十]', line):
                step_lines.append(line)
            elif step_lines:
                step_lines[-1] += '\n' + line

        if step_lines and len(step_lines) >= 2:
            colors = ['#38bdf8', '#a78bfa', '#f472b6', '#34d399', '#fb923c', '#fbbf24', '#60a5fa', '#c084fc']
            for i, line in enumerate(step_lines[:8]):
                parts = line.split('\n', 1)
                title = re.sub(r'^[\d一二三四五六七八九十]+[\.、．)）\s]+', '', parts[0]).strip()[:35]
                desc = (parts[1] if len(parts) > 1 else parts[0])[:120]
                kws = [w for w in re.findall(r'[\u4e00-\u9fff\w]{2,10}', desc) if len(w) >= 2][:5]
                scenes.append({
                    "title": title or "步骤" + str(i+1),
                    "desc": desc or "教学步骤 " + str(i+1),
                    "keywords": kws or [topic[:10]],
                    "color": colors[i % len(colors)]
                })
            return scenes

        sentences = [s.strip() for s in content.replace('\n', '。').split('。') if len(s.strip()) > 4]
        colors = ['#38bdf8', '#a78bfa', '#f472b6', '#34d399', '#fb923c', '#fbbf24']
        titles = ['引入概念', '核心讲解', '关键要点', '知识应用', '练习巩固', '总结回顾']
        
        for i, sent in enumerate(sentences[:6]):
            kws = [w for w in re.findall(r'[\u4e00-\u9fff\w]{2,10}', sent) if len(w) >= 2][:5]
            scenes.append({
                "title": titles[min(i, len(titles)-1)],
                "desc": sent[:120],
                "keywords": kws or [topic[:10]],
                "color": colors[i % len(colors)]
            })

        if not scenes:
            scenes = [
                {"title": "概念引入", "desc": "介绍" + topic + "的基本概念和定义", "keywords": [topic, "定义", "背景", "概述"], "color": "#38bdf8"},
                {"title": "核心原理", "desc": "深入讲解" + topic + "的核心原理和关键知识点", "keywords": ["原理", "核心", "知识点", "要点"], "color": "#a78bfa"},
                {"title": "实例分析", "desc": topic + "的实际应用案例分析", "keywords": ["案例", "实例", "应用", "实践"], "color": "#f472b6"},
                {"title": "总结归纳", "desc": topic + "学习要点回顾与总结", "keywords": ["总结", "回顾", "要点", "复习"], "color": "#34d399"},
            ]

        return scenes

    def _generate_animation_content_v2(self, topic: str, audience: str, teaching_content: str) -> Dict:
        """使用AI生成分镜JSON（回退方案）"""
        tc = (teaching_content or topic or "本课内容")[:3000]

        prompt = f"""你是教学视频编导。请为主题「{topic}」设计一套HTML5动画分镜方案。
面向：{audience}
教学内容：{tc}

请输出JSON对象：
{{
    "title": "动画标题",
    "description": "简介",
    "scenes": [
        {{"scene_id": 1, "title": "场景标题", "duration": "约XX秒",
         "description": "画面描述", "visual_elements": ["元素"], "script": "口播词"}}
    ],
    "characters": [{{"name": "角色名", "role": "角色职责"}}],
    "estimated_time": "预估"
}}
要求：scenes至少4个，每场景紧扣教学内容。"""

        try:
            result = llm_service.chat(prompt, purpose="animation_code")
            start = result.find('{')
            if start >= 0:
                depth = 0
                for i in range(start, len(result)):
                    if result[i] == '{': depth += 1
                    elif result[i] == '}':
                        depth -= 1
                        if depth == 0:
                            data = json.loads(result[start:i+1])
                            if isinstance(data, dict) and data.get("scenes"):
                                return data
                            break
        except Exception as e:
            print(f"[动画生成] 动画分镜JSON解析失败: {e}")

        return {
            "title": topic + "动画演示",
            "description": "面向" + audience + "的" + topic + "教学动画",
            "scenes": [
                {"scene_id": 1, "title": "引入", "duration": "30秒",
                 "description": "通过生动的动画引入" + topic + "概念", "visual_elements": ["标题动画", "背景渐变"], "script": "同学们好，今天我们来学习" + topic},
                {"scene_id": 2, "title": "核心讲解", "duration": "2分钟",
                 "description": "详细讲解" + topic + "的核心原理和知识点", "visual_elements": ["流程图", "示意图"], "script": topic + "的核心要点包括..."},
                {"scene_id": 3, "title": "实例演示", "duration": "1分钟",
                 "description": topic + "的实际应用案例演示", "visual_elements": ["案例视频", "数据图表"], "script": "让我们来看一个实际应用案例"},
                {"scene_id": 4, "title": "总结回顾", "duration": "30秒",
                 "description": "回顾本课程的重点内容", "visual_elements": ["思维导图", "要点列表"], "script": "今天的学习就到这里，总结一下..."},
            ],
            "characters": [{"name": "讲师", "role": "知识引导者"}],
            "estimated_time": "2-3小时"
        }

    def _create_animation_preview(self, topic: str, audience: str, animation_data: Dict, task_dir: str) -> Optional[str]:
        """创建分镜脚本预览HTML（最终回退方案）"""
        try:
            anim_title = animation_data.get('title', '动画演示')
            scenes_json = json.dumps(animation_data.get('scenes', []), ensure_ascii=False)
            characters_json = json.dumps(animation_data.get('characters', []), ensure_ascii=False)

            html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>''' + anim_title + '''</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);min-height:100vh;color:#fff}}
.container{{max-width:960px;margin:0 auto;padding:24px}}
.header{{text-align:center;padding:30px 0}}
.header h1{{font-size:32px;background:linear-gradient(135deg,#38bdf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header p{{color:#94a3b8;margin-top:8px}}
.card{{background:rgba(255,255,255,0.05);border-radius:16px;padding:24px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.08)}}
.card h2{{font-size:18px;margin-bottom:16px}}
.scene-player{{background:#000;border-radius:12px;overflow:hidden;margin-bottom:16px}}
.player-stage{{height:360px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;background:linear-gradient(180deg,#1e293b,#0f1724)}}
.scene-content{{text-align:center;z-index:1;padding:24px;max-width:80%}}
.scene-title{{font-size:32px;margin-bottom:16px;color:#fff}}
.scene-desc{{font-size:16px;color:#94a3b8;line-height:1.6}}
.controls{{display:flex;align-items:center;gap:12px;padding:14px 20px;background:rgba(0,0,0,0.3)}}
.play-btn{{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#38bdf8,#a78bfa);border:none;cursor:pointer;font-size:20px;color:#fff}}
.progress-bar{{flex:1;height:6px;background:rgba(255,255,255,0.15);border-radius:3px;cursor:pointer}}
.progress-fill{{height:100%;background:linear-gradient(90deg,#38bdf8,#a78bfa);border-radius:3px;width:0;transition:width 0.3s}}
.nav-dots{{display:flex;justify-content:center;gap:8px;padding:12px}}
.dot{{width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,0.2);cursor:pointer;transition:all 0.3s}}
.dot.active{{background:#38bdf8;transform:scale(1.4)}}
.scene-card{{background:rgba(255,255,255,0.05);padding:20px;border-radius:12px;margin-bottom:12px;cursor:pointer;border:2px solid transparent;transition:all 0.3s}}
.scene-card:hover{{background:rgba(255,255,255,0.1)}}
.scene-card.active{{border-color:#38bdf8}}
.scene-header{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.scene-number{{background:#38bdf8;color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600}}
.scene-title-text{{font-weight:600;color:#fff}}
.scene-duration{{background:rgba(255,255,255,0.1);padding:4px 10px;border-radius:10px;font-size:12px;color:#94a3b8}}
.scene-desc-text{{color:#94a3b8;font-size:14px;line-height:1.5;margin-bottom:8px}}
.scene-script{{background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;font-size:13px;color:#cbd5e1;line-height:1.5}}
.characters-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}}
.character-card{{background:rgba(255,255,255,0.05);padding:20px;border-radius:12px;text-align:center}}
.char-avatar{{font-size:40px;margin-bottom:10px}}
.char-name{{font-weight:600;color:#fff;margin-bottom:4px}}
.char-role{{font-size:12px;color:#94a3b8}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>''' + anim_title + '''</h1><p>面向''' + audience + ''' | HTML5教学动画分镜方案</p></div>
<div class="card">
<h2>🎬 预览播放</h2>
<div class="scene-player">
<div class="player-stage"><div class="scene-content" id="stageContent"></div></div>
<div class="controls">
<button class="play-btn" id="playBtn" onclick="togglePlay()">▶</button>
<div class="progress-bar" onclick="seekScene(event)"><div class="progress-fill" id="progressFill"></div></div>
</div>
</div>
<div class="nav-dots" id="navDots"></div>
</div>
<div class="card"><h2>🎞️ 分镜脚本</h2><div id="scenesList"></div></div>
<div class="card"><h2>👤 角色设计</h2><div id="charactersGrid"></div></div>
</div>
<script>
const scenes=''' + scenes_json + ''';
const characters=''' + characters_json + ''';
let cur=0,playing=false,timer=null;

function renderScenes(){
document.getElementById('scenesList').innerHTML=scenes.map((s,i)=>'<div class="scene-card '+(i===cur?'active':'')+'" onclick="goTo('+i+')">'+
'<div class="scene-header">'+
'<span class="scene-number">'+(s.scene_id||i+1)+'</span>'+
'<span class="scene-title-text">'+s.title+'</span>'+
'<span class="scene-duration">'+(s.duration||'30秒')+'</span>'+
'</div>'+
'<div class="scene-desc-text">'+s.description+'</div>'+
'<div class="scene-script">'+(s.script||'暂无台词')+'</div>'+
'</div>').join('');
}

function renderCharacters(){
document.getElementById('charactersGrid').innerHTML=characters.length?characters.map(c=>'<div class="character-card">'+
'<div class="char-avatar">👨‍🏫</div><div class="char-name">'+c.name+'</div><div class="char-role">'+(c.role||'')+'</div>'+
'</div>').join(''):'<p style="color:#94a3b8;text-align:center;padding:20px">暂无角色设计</p>';
}

function updateStage(){
const s=scenes[cur];
document.getElementById('stageContent').innerHTML='<div class="scene-title">'+s.title+'</div><div class="scene-desc">'+s.description+'</div>';
document.querySelectorAll('.dot').forEach((d,i)=>d.classList.toggle('active',i===cur));
document.querySelectorAll('.scene-card').forEach((c,i)=>c.classList.toggle('active',i===cur));
document.getElementById('progressFill').style.width=((cur+1)/scenes.length*100)+'%';
}

function buildNav(){
document.getElementById('navDots').innerHTML=scenes.map((_,i)=>'<div class="dot '+(i===0?'active':'')+'" onclick="goTo('+i+')"></div>').join('');
}

function goTo(i){cur=i;updateStage();}
function togglePlay(){playing=!playing;document.getElementById('playBtn').textContent=playing?'⏸':'▶';if(playing)timer=setInterval(()=>{cur=(cur+1)%scenes.length;updateStage()},4000);else clearInterval(timer);}
function seekScene(e){const r=e.target.getBoundingClientRect();cur=Math.min(Math.floor((e.clientX-r.left)/r.width*scenes.length),scenes.length-1);updateStage();}

renderScenes();renderCharacters();buildNav();updateStage();
</script>
</body>
</html>'''
            filename = self._clean_filename(topic) + "_storyboard.html"
            filepath = os.path.join(task_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            return filepath
        except Exception as e:
            print(f"[动画生成] 分镜预览创建失败: {e}")
            return None

    def _clean_filename(self, filename: str) -> str:
        for c in '<>:"/\\|?*':
            filename = filename.replace(c, '_')
        return filename[:50]

    def get_animation_styles(self) -> List[Dict]:
        """获取动画类型（简化为单一智能生成模式）"""
        return [{"id": "auto", "name": "智能生成", "description": "AI自动分析教学内容，生成最适合的HTML5动画演示"}]