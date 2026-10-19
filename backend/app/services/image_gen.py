"""AI 生图（通义万相 / wanx）—— 给课件配上真实示意图。

为什么单独一个模块
------------------
课件的观感差距，一半来自排版，一半来自**有没有图**。此前生成器只能画矢量色块，
教师拿到的是一份"文字排版稿"，不是课件。

为什么用异步任务接口而不是同步
------------------------------
官方文档给出的文生图接口是**异步**的：先提交任务拿 `task_id`，再轮询
`/api/v1/tasks/{task_id}` 取结果。同步接口在文档中是另一个端点（多模态生成），
字段不同，这里不混用。

接口依据（阿里云百炼官方文档，2026-10 核实）
-------------------------------------------
- 提交：POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis
    头：X-DashScope-Async: enable / Authorization: Bearer <key> / Content-Type: application/json
    体：{"model": "wanx2.1-t2i-turbo",
         "input": {"prompt": "…"},
         "parameters": {"size": "1024*1024", "n": 1}}
- 查询：GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}
    output.task_status ∈ PENDING / RUNNING / SUCCEEDED / FAILED
    SUCCEEDED 时 output.results[0].url 是图片地址
- **图片 URL 有效期 24 小时**，必须下载到本地才能进成品

成本与限制（必须让用户知道）
---------------------------
- 免费额度 500 张 / 90 天；之后按张计费（只有**成功**的图计费）
- QPS 2、并发 1 —— 所以这里强制**串行**，并做最小间隔控制
- 单张耗时通常 10–30 秒

因此本模块的设计底线是：**生图是可选增强，失败一律降级，绝不阻塞主流程。**
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx

# ---------------------------------------------------------------------------
# 常量：全部来自官方 curl 示例，字段原样保留
# ---------------------------------------------------------------------------

IMAGE_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
TASK_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

DEFAULT_IMAGE_MODEL = "wanx2.1-t2i-turbo"
DEFAULT_SIZE = "1024*1024"

SUBMIT_TIMEOUT = 30.0        # 提交任务
POLL_TIMEOUT = 15.0          # 单次轮询
POLL_INTERVAL = 3.0          # 轮询间隔
POLL_MAX_WAIT = 120.0        # 单张图最多等这么久
DOWNLOAD_TIMEOUT = 60.0      # 下载图片

# QPS 2 / 并发 1：串行是唯一安全做法
_MIN_INTERVAL = 0.6
_last_call = 0.0

# 出图目录
IMAGE_DIR = os.path.join("generated_images")


def _throttle() -> None:
    """按官方 QPS 限制做最小间隔，避免触发限流。"""
    global _last_call
    wait = _MIN_INTERVAL - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def submit(prompt: str, api_key: str, model: str = DEFAULT_IMAGE_MODEL,
           size: str = DEFAULT_SIZE) -> Optional[str]:
    """提交生图任务，返回 task_id；失败返回 None。"""
    if not api_key or not prompt:
        return None
    _throttle()
    try:
        with httpx.Client(timeout=SUBMIT_TIMEOUT, verify=False) as c:
            r = c.post(
                IMAGE_ENDPOINT,
                headers={
                    "X-DashScope-Async": "enable",
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": {"prompt": prompt},
                    "parameters": {"size": size, "n": 1},
                },
            )
            if r.status_code >= 400:
                return None
            data = r.json() or {}
            return ((data.get("output") or {}).get("task_id")) or None
    except Exception:
        return None


def poll(task_id: str, api_key: str) -> Optional[str]:
    """轮询任务，返回图片 URL；超时/失败返回 None。"""
    if not task_id:
        return None
    deadline = time.time() + POLL_MAX_WAIT
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=POLL_TIMEOUT, verify=False) as c:
                r = c.get(
                    TASK_ENDPOINT.format(task_id=task_id),
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if r.status_code >= 400:
                    return None
                out = (r.json() or {}).get("output") or {}
                status = out.get("task_status")
                if status == "SUCCEEDED":
                    results = out.get("results") or []
                    if results:
                        return results[0].get("url")
                    return None
                if status == "FAILED":
                    return None
        except Exception:
            return None
        time.sleep(POLL_INTERVAL)
    return None


def download(url: str, dest_dir: str = IMAGE_DIR) -> Optional[str]:
    """下载图片到本地。

    必须下载：官方给的图片 URL **24 小时后失效**，直接把 URL 写进 PPT
    以后打开就是坏图。
    """
    if not url:
        return None
    try:
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, f"{uuid.uuid4().hex[:12]}.png")
        with httpx.Client(timeout=DOWNLOAD_TIMEOUT, verify=False) as c:
            r = c.get(url)
            if r.status_code >= 400:
                return None
            with open(path, "wb") as f:
                f.write(r.content)
        return path
    except Exception:
        return None


def generate(prompt: str, api_key: str, *, model: str = DEFAULT_IMAGE_MODEL,
             size: str = DEFAULT_SIZE, dest_dir: str = IMAGE_DIR) -> Optional[str]:
    """一步到位：提交 → 轮询 → 下载，返回本地图片路径；任何一步失败返回 None。

    调用方必须把 None 当作"降级为无图"来处理，**不要**因此中断生成。
    """
    task_id = submit(prompt, api_key, model=model, size=size)
    if not task_id:
        return None
    url = poll(task_id, api_key)
    if not url:
        return None
    return download(url, dest_dir=dest_dir)


# ---------------------------------------------------------------------------
# 兜底：本地几何装饰图
# ---------------------------------------------------------------------------
#
# ⚠️ 为什么不用 services/image_service 的装饰图：它在图上渲染中文主题文字，
# 而 **PIL 的 `draw.text()` 渲染中文在本机会直接 segfault**（实测：几何绘制与
# 字体加载都正常，唯独 `d.text()` 一调用进程就崩，且 try/except 拦不住 ——
# segfault 不是异常）。崩溃会杀掉整个后端进程，那是比"没图"严重得多的事故。
#
# 所以这里的兜底图**只画几何形状，不画任何文字**。

_SUBJECT_SHAPE = {
    "物理": "wave", "数学": "grid", "化学": "hexagon",
    "生物": "leaf", "语文": "lines", "英语": "lines",
    "地理": "layers", "历史": "layers", "编程": "blocks",
}


def decorative(topic: str = "", subject: str = "general",
               width: int = 800, height: int = 600,
               dest_dir: str = IMAGE_DIR) -> Optional[str]:
    """画一张不含文字的几何装饰图，返回本地路径；失败返回 None。

    只做兜底用：让版面有视觉锚点，但不假装它是"教学示意图"。
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    try:
        import os
        import random
        os.makedirs(dest_dir, exist_ok=True)
        rng = random.Random(hash(topic) & 0xFFFF)

        bg_top = (20, 60, 110)
        bg_bot = (232, 242, 252)
        img = Image.new("RGB", (width, height), bg_bot)
        d = ImageDraw.Draw(img)
        # 竖向渐变
        for y in range(height):
            r = y / max(height - 1, 1)
            d.line([(0, y), (width, y)], fill=(
                int(bg_top[0] + (bg_bot[0] - bg_bot[0]) * r * 0.35),
                int(bg_top[1] + (bg_bot[1] - bg_bot[1]) * r * 0.35),
                int(bg_top[2] + (bg_bot[2] - bg_bot[2]) * r * 0.35),
            ))

        accent = (46, 139, 214)
        gold = (242, 166, 44)

        # 背景大圆：撑住版面，避免全空白
        d.ellipse([width * 0.45, -height * 0.25, width * 1.25, height * 0.55],
                  fill=(30, 90, 150))
        d.ellipse([-width * 0.2, height * 0.55, width * 0.5, height * 1.25],
                  fill=(28, 78, 132))

        shape = _SUBJECT_SHAPE.get(subject, "wave")
        if shape == "wave":
            pts = []
            for i in range(0, width, 8):
                y = height * 0.62 + 42 * _sin(i / 46.0)
                pts.append((i, y))
            d.line(pts, fill=gold, width=6)
            d.line([(p[0], p[1] + 26) for p in pts], fill=(255, 255, 255), width=3)
        elif shape == "grid":
            for i in range(0, width, 56):
                d.line([(i, 0), (i, height)], fill=(255, 255, 255), width=1)
            for j in range(0, height, 56):
                d.line([(0, j), (width, j)], fill=(255, 255, 255), width=1)
        elif shape == "hexagon":
            cx, cy, r = width * 0.5, height * 0.5, min(width, height) * 0.26
            pts = [(cx + r * _cos(3.14159 / 3 * k), cy + r * _sin(3.14159 / 3 * k))
                   for k in range(6)]
            d.polygon(pts, outline=gold, width=6)
        elif shape == "blocks":
            for k in range(4):
                x = width * (0.18 + 0.18 * k)
                d.rectangle([x, height * 0.42, x + 74, height * 0.42 + 74], fill=gold)
        else:  # lines / layers / leaf / 默认
            for k in range(5):
                y = height * (0.36 + 0.09 * k)
                d.rectangle([width * 0.18, y, width * (0.5 + 0.09 * k), y + 16],
                            fill=(255, 255, 255))
            d.ellipse([width * 0.62, height * 0.34, width * 0.92, height * 0.72],
                      outline=gold, width=6)

        # 底部强调条
        d.rectangle([0, height - 26, width, height], fill=accent)
        path = os.path.join(dest_dir, f"deco_{rng.randint(1000, 9999)}.png")
        img.save(path, "PNG")
        return path
    except Exception:
        return None


def _sin(x: float) -> float:
    import math
    return math.sin(x)


def _cos(x: float) -> float:
    import math
    return math.cos(x)


def build_prompt(topic: str, subject: str = "", core_topic: str = "") -> str:
    """把教学内容翻译成生图提示词。

    刻意加的约束：教学配图要**干净、可讲解**，不能是艺术化到看不懂的图。
    同时避免生成文字（模型在图上写字经常是乱码）。
    """
    focus = core_topic or topic
    subj = f"{subject}学科，" if subject and subject != "general" else ""
    # 课程大主题与本页概念都要给：只给本页概念，模型不知道这是哪门课的图，
    # 容易跑偏（"阿基米德原理" 可能被画成古希腊场景而不是课堂示意图）。
    return (
        f"{subj}一幅用于课堂投影教学的示意图。"
        f"课程主题：{topic}；本页内容：{focus}。"
        "要求：写实简洁、主体突出、背景干净、构图居中，"
        "画面中不要出现任何文字、公式或水印。"
    )[:400]
