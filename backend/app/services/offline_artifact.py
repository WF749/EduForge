"""产物离线可用性检查（纯规则、零依赖、不联网）。

存在的理由：项目定位是"本地优先"，教师会把生成的动画/游戏 HTML 拷到教室电脑上
放给全班看 —— 那台机器很可能没网，或者只通校园内网不通公网。
如果模型偷偷在 HTML 里引了一个 CDN（prompt 里明确禁了，但模型不总听话），
产物在本机开发时一切正常，**拷到教室才发现打不开**，而且看起来像"文件坏了"
而不是"缺网"。这种失败发生在交付之后，最难排查。

所以这里在产物落盘后扫一遍外部引用，**只报告、不阻断**（与教学合规闸门同一个约定）：
不删内容、不改产物、不让生成失败。发现外链就把 URL 和类型如实列出来，
让教师当场就知道"这份要联网才能看"。

刻意不做什么：
  - 不去下载这些资源内联成 data: URI。那会让"生成"这个动作依赖外网连通性，
    与本地优先自相矛盾；而且版权上也不该替教师把第三方库打包进产物。
  - 不扫 JS 里的动态 fetch/XHR。模型生成的 HTML 里这类写法占比极低，
    为它做字符串匹配会引入大量误报（正文里写个网址就被判离线不可用），
    误报一多，这个提示就没人看了。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# HTML 注释里的示例链接不会真的加载，先剥掉再扫，否则必误报
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# src= / href=：带引号与不带引号两种 HTML 都合法
_ATTR_QUOTED = re.compile(
    r"\b(src|href)\s*=\s*([\"'])\s*((?:https?:)?//[^\"'>\s]+)\2", re.IGNORECASE
)
_ATTR_BARE = re.compile(
    r"\b(src|href)\s*=\s*((?:https?:)?//[^\"'>\s]+)", re.IGNORECASE
)

# CSS：url(http...) 与 @import
_CSS_URL = re.compile(
    r"url\(\s*([\"']?)\s*((?:https?:)?//[^)\"']+)\1\s*\)", re.IGNORECASE
)
_CSS_IMPORT = re.compile(
    r"@import\s+(?:url\()?\s*([\"'])\s*((?:https?:)?//[^\"')]+)\1", re.IGNORECASE
)

# 站外绝对地址才算"联网依赖"；data: / mailto: / 锚点 都不算
_SCHEME_OK = re.compile(r"^(?:data|mailto|tel|javascript|blob|about):", re.IGNORECASE)

_EXT_KIND = [
    ((".js", ".mjs"), "script"),
    ((".css",), "stylesheet"),
    ((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"), "image"),
    ((".mp4", ".webm", ".mp3", ".ogg", ".wav"), "media"),
    ((".woff", ".woff2", ".ttf", ".otf", ".eot"), "font"),
]


def _kind_of(attr: str, url: str) -> str:
    low = url.lower().split("?")[0].split("#")[0]
    for exts, kind in _EXT_KIND:
        if low.endswith(exts):
            return kind
    return "script" if attr == "src" else "link"


def _clean(html: str) -> str:
    return _COMMENT.sub(" ", html or "")


def _normalize(url: str) -> str:
    """协议相对 //cdn.x/y 补成 https://cdn.x/y，显示时也更好认"""
    if url.startswith("//"):
        return "https:" + url
    return url


def scan_external_refs(html: str) -> List[Dict[str, str]]:
    """扫出 HTML 里会发起联网请求的外部引用。

    @param html 产物 HTML 源码
    @returns [{"url", "kind", "attr"}]，按出现顺序去重
    """
    text = _clean(html)
    found: List[Dict[str, str]] = []
    seen = set()

    def add(attr: str, url: str) -> None:
        url = url.strip()
        if not url or _SCHEME_OK.match(url):
            return
        full = _normalize(url)
        key = (full, attr)
        if key in seen:
            return
        seen.add(key)
        found.append({"url": full, "kind": _kind_of(attr, full), "attr": attr})

    for m in _ATTR_QUOTED.finditer(text):
        add(m.group(1), m.group(3))
    # 不带引号的写法与上面会重复，靠 seen 去重
    for m in _ATTR_BARE.finditer(text):
        add(m.group(1), m.group(2))
    for m in _CSS_URL.finditer(text):
        add("css", m.group(2))
    for m in _CSS_IMPORT.finditer(text):
        add("css", m.group(2))

    return found


def check_offline(html: Optional[str]) -> Dict[str, Any]:
    """产物能不能离线打开。只报告不阻断，异常一律吞掉返回"未知"。

    @returns {"offline_ready","checked","count","refs","message"}
    """
    if not html or not isinstance(html, str):
        return {
            "offline_ready": True,
            "checked": False,
            "count": 0,
            "refs": [],
            "message": "",
        }

    try:
        refs = scan_external_refs(html)
    except Exception:
        # 扫描失败绝不能影响生成（与 run_compliance_gate 同约定）
        return {
            "offline_ready": True,
            "checked": False,
            "count": 0,
            "refs": [],
            "message": "",
        }

    if not refs:
        return {
            "offline_ready": True,
            "checked": True,
            "count": 0,
            "refs": [],
            "message": "",
        }

    kinds = sorted({r["kind"] for r in refs})
    return {
        "offline_ready": False,
        "checked": True,
        "count": len(refs),
        "refs": refs[:10],
        "message": (
            f"这份产物引用了 {len(refs)} 个外部资源（{'/'.join(kinds)}），"
            f"断网或只通内网的教室电脑上会打不开。"
            f"建议重新生成，或手动去掉这些外链后再带到课堂。"
        ),
    }
