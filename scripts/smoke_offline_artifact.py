"""产物离线可用性检查的冒烟测试（纯规则、不联网、秒级）。

存在的理由：这个检查的失败形态是"交付之后才出事"——
模型偷偷引了个 CDN，本机开发一切正常，拷到教室的电脑上才发现打不开，
而且看起来像文件坏了而不是缺网。所以它必须有两件事被钉死：
  1. 常见的引库写法一个都不能漏（漏报 = 白做）；
  2. 注释里的示例链接、data: URI、站内相对路径一个都不能报（误报 = 提示没人看）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.offline_artifact import check_offline, scan_external_refs  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def urls(html: str):
    return [r["url"] for r in scan_external_refs(html)]


print("\n=== 1. 必须抓到的（漏报 = 白做）===")
check("script src 带引号", urls('<script src="https://cdn.jsdelivr.net/npm/three.js"></script>') != [])
check("script src 单引号", urls("<script src='https://unpkg.com/vue@3'></script>") != [])
check("script src 无引号", urls("<script src=https://cdnjs.cloudflare.com/x.js></script>") != [])
check("link href CSS", urls('<link rel="stylesheet" href="https://cdn.x.com/a.css">') != [])
check("img src", urls('<img src="https://cdn.x.com/a.png">') != [])
check("协议相对 //cdn", urls('<script src="//cdn.jsdelivr.net/npm/x.js"></script>') != [])
check("CSS url()", urls("<style>.a{background:url(https://cdn.x.com/b.png)}</style>") != [])
check("CSS url() 带引号", urls("<style>.a{background:url('https://cdn.x.com/b.png')}</style>") != [])
check("@import", urls("<style>@import 'https://fonts.googleapis.com/css?x';</style>") != [])
check("http 明文也算", urls('<script src="http://cdn.x.com/a.js"></script>') != [])

print("\n=== 2. 不能误报的（误报 = 提示没人看）===")
check("HTML 注释里的示例", urls("<!-- <script src=\"https://cdn.x.com/a.js\"></script> -->") == [])
check("data: URI", urls('<img src="data:image/png;base64,iVBORw0KGgo=">') == [])
check("站内相对路径", urls('<script src="assets/main.js"></script>') == [])
check("根相对路径", urls('<link href="/static/a.css">') == [])
check("锚点", urls('<a href="#section-2">跳</a>') == [])
check("mailto", urls('<a href="mailto:a@b.com">联系</a>') == [])
check("干净的产物", check_offline("<html><body><canvas id='c'></canvas></body></html>")["offline_ready"])
check("空内容视为可用", check_offline("")["offline_ready"])
check("None 视为可用", check_offline(None)["offline_ready"])
check("非字符串不炸", check_offline(123)["offline_ready"])

print("\n=== 3. 报告形态 ===")
r = check_offline('<script src="https://cdn.x.com/a.js"></script>')
check("offline_ready=False", r["offline_ready"] is False)
check("checked=True", r["checked"] is True)
check("count 正确", r["count"] == 1, str(r["count"]))
check("kind 识别为 script", r["refs"][0]["kind"] == "script", r["refs"][0]["kind"])
check("给了可操作的 message", "打不开" in r["message"])
check("重复引用只算一次", len(urls(
    '<script src="https://cdn.x.com/a.js"></script>'
    '<script src="https://cdn.x.com/a.js"></script>'
)) == 1)
check("最多返回 10 条", len(check_offline("".join(
    f'<script src="https://cdn.x.com/{i}.js"></script>' for i in range(30)
))["refs"]) == 10)

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
