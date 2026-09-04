"""面向具体知识点的可运行 HTML5 教学动画模板（不依赖大模型，保证比赛演示可用）"""
from typing import Dict, Any


def detect_cell_division_topic(combined_text: str) -> bool:
    """检测是否与细胞分裂/有丝分裂等相关"""
    if not combined_text:
        return False
    t = combined_text.lower()
    cn = [
        "细胞分裂", "有丝分裂", "减数分裂", "染色体", "细胞核", "纺锤体",
        "间期", "前期", "中期", "后期", "末期", "胞质分裂",
    ]
    if any(k in combined_text for k in cn):
        return True
    en = ("mitosis", "meiosis", "chromosome", "cytokinesis")
    return any(k in t for k in en)


def build_mitosis_demo_html(topic: str, audience: str, preset: Dict[str, Any]) -> str:
    """
    有丝分裂过程示意：Canvas + 分步场景，可播放自动轮播。
    纯前端，无外链。
    """
    bg = preset["bg"]
    panel = preset["panel"]
    a1 = preset["accent1"]
    a2 = preset["accent2"]
    tx = preset["text"]
    muted = preset["muted"]

    stages = [
        ("间期", "遗传物质复制，染色质呈细丝状"),
        ("前期", "染色质螺旋化；核膜、核仁消失"),
        ("中期", "染色体排列在赤道板，纺锤丝牵引"),
        ("后期", "着丝粒分裂，姐妹染色单体移向两极"),
        ("末期", "染色体解螺旋；核膜重建，胞质分裂"),
    ]

    stages_json = __import__("json").dumps(stages, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{topic} — 有丝分裂示意</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background: {bg};
  color: {tx};
  min-height: 100vh;
}}
.wrap {{ max-width: 920px; margin: 0 auto; padding: 20px; }}
h1 {{
  font-size: 26px; text-align: center; margin-bottom: 8px;
  background: linear-gradient(90deg, {a1}, {a2});
  -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.sub {{ text-align: center; color: {muted}; font-size: 14px; margin-bottom: 16px; }}
.panel {{
  background: {panel};
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,.25);
}}
canvas {{ display: block; width: 100%; max-width: 860px; height: auto; margin: 0 auto; border-radius: 12px; background: rgba(0,0,0,.15); }}
.ctrl {{
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 14px; justify-content: center;
}}
button {{
  padding: 10px 18px; border: none; border-radius: 24px; cursor: pointer; font-size: 14px;
  background: linear-gradient(135deg, {a1}, {a2}); color: #fff;
}}
button.sec {{ background: rgba(255,255,255,.08); color: {tx}; border: 1px solid rgba(255,255,255,.15); }}
.step {{
  flex: 1 1 100%; text-align: center; margin-top: 10px; font-size: 15px; line-height: 1.6; color: {tx};
}}
.progress {{ width: 100%; height: 6px; background: rgba(255,255,255,.1); border-radius: 3px; margin-top: 12px; overflow: hidden; }}
.fill {{ height: 100%; background: linear-gradient(90deg, {a1}, {a2}); width: 20%; transition: width .35s ease; }}
.dots {{ display: flex; justify-content: center; gap: 8px; margin-top: 10px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,.2); cursor: pointer; }}
.dot.on {{ background: {a1}; transform: scale(1.2); }}
.note {{ margin-top: 14px; font-size: 13px; color: {muted}; line-height: 1.7; }}
@keyframes pulse {{ 0%,100%{{opacity:.85}} 50%{{opacity:1}} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{topic}</h1>
  <p class="sub">教学动画 · 面向 {audience} · 有丝分裂过程（示意）</p>
  <div class="panel">
    <canvas id="cv" width="860" height="400"></canvas>
    <div class="progress"><div class="fill" id="pf"></div></div>
    <div class="dots" id="dots"></div>
    <div class="ctrl">
      <button type="button" class="sec" id="prev">上一步</button>
      <button type="button" id="play">播放</button>
      <button type="button" class="sec" id="next">下一步</button>
    </div>
    <div class="step" id="cap">加载中…</div>
    <p class="note">说明：本页为课堂示意动画，帮助理解染色体行为与时期划分；精细结构以教材插图为准。</p>
  </div>
</div>
<script>
const STAGES = {stages_json};
let si = 0, playing = false, t = 0, raf = null;

const canvas = document.getElementById('cv');
const ctx = canvas.getContext('2d');
const cap = document.getElementById('cap');
const pf = document.getElementById('pf');
const dots = document.getElementById('dots');

function syncDots() {{
  dots.innerHTML = STAGES.map((_, i) => '<div class="dot' + (i===si?' on':'') + '" data-i="'+i+'"></div>').join('');
  dots.querySelectorAll('.dot').forEach(d => d.onclick = () => {{ si = +d.dataset.i; t=0; }});
  cap.innerHTML = '<strong>' + STAGES[si][0] + '</strong>：' + STAGES[si][1];
  pf.style.width = ((si+1)/STAGES.length*100) + '%';
}}

function drawCell(cx, cy, r, phase, anim) {{
  ctx.save();
  ctx.translate(cx, cy);
  // 细胞膜
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,255,255,.35)';
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.fillStyle = 'rgba(100,180,255,.08)';
  ctx.fill();

  const pulse = 0.5 + 0.5 * Math.sin(anim * Math.PI * 2);

  function chrom(x, y, w, h, ang) {{
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(ang);
    ctx.fillStyle = '{a1}';
    ctx.fillRect(-w/2, -h/2, w, h);
    ctx.fillStyle = '{a2}';
    ctx.fillRect(-w/2 + 3, -h/2, w - 6, h);
    ctx.restore();
  }}

  if (phase === 0) {{
    ctx.fillStyle = 'rgba(200,220,255,.25)';
    ctx.beginPath(); ctx.arc(0, 0, r * 0.35, 0, Math.PI*2); ctx.fill();
  }}
  if (phase === 1) {{
    for (let i = 0; i < 6; i++) {{
      const ang = (i / 6) * Math.PI * 2 + anim * 0.4;
      chrom(Math.cos(ang)*r*0.25, Math.sin(ang)*r*0.25, 10, 22, ang);
    }}
  }}
  if (phase === 2) {{
    for (let i = 0; i < 8; i++) {{
      const ang = (i / 8) * Math.PI * 2;
      const rr = r * 0.55;
      chrom(Math.cos(ang)*rr, Math.sin(ang)*rr, 8, 18, ang + Math.PI/2);
    }}
    ctx.strokeStyle = 'rgba(255,200,100,.4)';
    ctx.setLineDash([6,6]);
    ctx.beginPath(); ctx.moveTo(-r*0.9, 0); ctx.lineTo(r*0.9, 0); ctx.stroke();
    ctx.setLineDash([]);
  }}
  if (phase === 3) {{
    const sep = 0.3 + 0.7 * pulse;
    for (let s of [-1, 1]) {{
      for (let i = 0; i < 4; i++) {{
        const ang = (i/4)*Math.PI*2;
        const ox = s * r * 0.45 * sep;
        chrom(ox + Math.cos(ang)*r*0.12, Math.sin(ang)*r*0.12, 8, 18, ang);
      }}
    }}
  }}
  if (phase === 4) {{
    ctx.fillStyle = 'rgba(200,220,255,.35)';
    ctx.beginPath(); ctx.arc(-r*0.35, 0, r*0.28, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(r*0.35, 0, r*0.28, 0, Math.PI*2); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.3)';
    ctx.beginPath(); ctx.moveTo(0, -r*0.2); ctx.lineTo(0, r*0.2); ctx.stroke();
  }}
  ctx.restore();
}}

function frame() {{
  t += 0.016;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawCell(canvas.width/2, canvas.height/2, Math.min(canvas.width, canvas.height)*0.38, si, t);
  raf = requestAnimationFrame(frame);
}}

function go(d) {{
  si = (si + d + STAGES.length) % STAGES.length;
  syncDots();
}}

document.getElementById('prev').onclick = () => go(-1);
document.getElementById('next').onclick = () => go(1);
let timer = null;
document.getElementById('play').onclick = function() {{
  playing = !playing;
  this.textContent = playing ? '暂停' : '播放';
  clearInterval(timer);
  if (playing) timer = setInterval(() => go(1), 3200);
}};

syncDots();
frame();
</script>
</body>
</html>"""
