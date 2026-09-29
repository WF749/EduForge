"""前后端接口路径契约的冒烟测试（**不调模型、不启服务**，秒级完成）。

存在的理由：前端写错一个路径，表现不是报错，而是**静默降级**。
典型一次：`lessonChat.js` 写成 `/chat/dialogue`（后端真实路由是
`/api/chat/analyze`），POST 打到 SPA 兜底路由上返回 405，
前端 catch 住只显示一句"对话服务没响应"——澄清链路整条废掉，
而页面上一切照常，没人会发现。

这类 bug 单测抓不到（两边各自都是对的），只有把两边的字符串放一起比才现形。
所以这里做一件事：**把前端代码里出现的 API 路径全扫出来，逐个去后端路由表里查**。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


# ---------------------------------------------------------------- 后端路由表

def collect_routes() -> dict:
    """收集所有 APIRoute 的 path -> methods。前缀 /api 的才算"接口"。"""
    table: dict = {}
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        if path.startswith("/api"):
            table[path] = {m for m in methods if m in {"GET", "POST", "PUT", "PATCH", "DELETE"}}
    return table


def path_matches(candidate: str, table: dict) -> bool:
    """精确匹配，或者匹配上带路径参数的路由（/api/x/{id}）。"""
    if candidate in table:
        return True
    cand = candidate.rstrip("/").split("/")
    for route in table:
        seg = route.rstrip("/").split("/")
        if len(seg) != len(cand):
            continue
        if all(s.startswith("{") and s.endswith("}") or s == c for s, c in zip(seg, cand)):
            return True
    return False


# ---------------------------------------------------------------- 前端路径扫描

# `${BASE()}/chat/analyze` —— BASE() 已含 /api（dev 下是 '/api'，生产是 http://host:8005/api）
RE_BASE = re.compile(r"\$\{BASE\(\)\}(/[A-Za-z0-9_\-/]*)")
# 直接写的 '/api/xxx' 字面量
RE_LITERAL = re.compile(r"['\"\`](/api/[A-Za-z0-9_\-/]*)['\"\`]")

# 第二种写法：axios 实例（baseURL 已指向本项目后端）+ 相对路径，如 apiClient.get('/llm/config')
RE_CLIENT = re.compile(
    r"\b(?:apiClient|api|client|instance|request)\s*\.\s*"
    r"(?:get|post|put|patch|delete)\(\s*['\"\`](/[A-Za-z0-9_\-/]*)['\"\`]"
)

# 第三种写法：api 目录里的裸辅助调用 post('/lesson-plan/xx')。
# 这些路径最终也是拼在 BASE() 后面，不扫就等于没检查 —— 项目里大部分接口其实都这么写。
RE_HELPER = re.compile(r"\b(?:post|get|put|patch|del)\(\s*'(/[A-Za-z0-9_\-/]*)'")

# 只有当文件确实指向本项目后端时才认第二、三种写法，避免把第三方地址也当自家接口
RE_POINTS_BACKEND = re.compile(r"resolveApiBaseURL|BASE\(\)")

SKIP_DIRS = {"node_modules", "dist", "dist_old", ".verify-dist", ".build-new"}


def scan_frontend() -> dict:
    """返回 {文件: [路径...]}，只收静态可判定的路径（含 ${} 变量的跳过）。"""
    found: dict = {}
    for base in ("src/api", "src/components", "src/composables", "src/views", "src/store"):
        for p in sorted((ROOT / "frontend" / base).rglob("*")):
            if not p.is_file() or p.suffix not in {".js", ".vue", ".ts"}:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            paths = []
            for m in RE_BASE.finditer(text):
                seg = m.group(1)
                # `/ppt/status/${task_id}`：静态部分被吃掉成 `/ppt/status/`，
                # 补成 `{param}` 才能对上后端的 /api/ppt/status/{task_id}
                if seg.endswith("/") and text[m.end():m.end() + 2].startswith("${"):
                    seg = seg.rstrip("/") + "/{param}"
                paths.append("/api" + seg)
            for m in RE_LITERAL.finditer(text):
                paths.append(m.group(1))
            if RE_POINTS_BACKEND.search(text):
                for m in RE_CLIENT.finditer(text):
                    paths.append("/api" + m.group(1))
                # 裸辅助调用只在 api 目录里认（那里 post/get 是拼 BASE() 的封装）
                if "/api/" in str(p.as_posix()):
                    for m in RE_HELPER.finditer(text):
                        paths.append("/api" + m.group(1))
            # 含 ${} 的动态路径拼不出来，跳过而不是猜
            paths = [x for x in paths if "${" not in x]
            if paths:
                found[str(p.relative_to(ROOT))] = sorted(set(paths))
    return found


# ---------------------------------------------------------------- 主流程

def main() -> int:
    print("\n=== 1. 后端路由表 ===")
    table = collect_routes()
    check("后端注册了 /api 前缀的接口", len(table) > 20, f"{len(table)} 条")

    print("\n=== 2. 前端引用的路径逐个校验 ===")
    found = scan_frontend()
    check("扫到了前端里的 API 路径引用", len(found) > 0, f"{len(found)} 个文件")

    # 明确登记的非接口路径：静态资源 / 外部地址 / 历史遗留但已确认的前端路由
    ALLOWED_MISS = {
        "/api/upload": "上传走分片接口，路径在别处拼装",
    }

    bad = []
    for f, paths in sorted(found.items()):
        for p in paths:
            if p in ALLOWED_MISS:
                continue
            if not path_matches(p, table):
                bad.append((f, p))

    for f, p in bad:
        print(f"    MISS  {p}   <- {f}")
    check("前端引用的每个路径后端都存在", not bad, f"{len(bad)} 个对不上" if bad else "")

    # 反向对照：故意编一条不存在的路径，必须被判缺失。
    # 否则扫描器一旦写错（比如正则匹配不到任何东西），这个测试会永远绿着。
    check("契约检查本身有效（假路径须判为缺失）", not path_matches("/api/no-such-endpoint-xyz", table))

    # 反向对照二：扫描器本身不能退化。前端大部分接口走 post('/xxx') 这种辅助函数，
    # 早期只扫 ${BASE()}/xxx 一种写法时只覆盖到 8 条，漏的比查到的还多。
    all_found = sorted({q for ps in found.values() for q in ps})
    check("扫描器没退化（至少 25 条路径）", len(all_found) >= 25, f"实得 {len(all_found)} 条")
    for must in ("/api/lesson-plan/generate-full", "/api/courseware/game/generate",
                 "/api/ppt/status/{param}", "/api/teaching-compliance/review",
                 "/api/teaching/blueprint"):
        check(f"扫到了 {must}", must in all_found)

    print("\n=== 3. 对话链路专项（出过事的那条）===")
    chat = ROOT / "frontend/src/api/lessonChat.js"
    text = chat.read_text(encoding="utf-8", errors="ignore")
    hits = [("/api" + m.group(1)) for m in RE_BASE.finditer(text)]
    check("lessonChat.js 引用了对话接口", len(hits) >= 1, ",".join(hits))
    check("对话接口路径存在于路由表", all(path_matches(h, table) for h in hits), ",".join(hits))
    check("/api/chat/analyze 支持 POST", "POST" in table.get("/api/chat/analyze", set()))
    check("/api/chat/reset-dialogue 支持 POST", "POST" in table.get("/api/chat/reset-dialogue", set()))

    print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：" + "、".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
