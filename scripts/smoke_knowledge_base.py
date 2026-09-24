"""预置知识库的冒烟测试（纯文件校验，不建索引、不调模型、毫秒级）。

存在的理由：**预置知识库是交付内容，不是可选附件**。
教师的第一次备课体验不应依赖"他先上传资料"——系统自己就该有东西可查。
而这类内容资产最容易被悄悄掏空：删掉几篇、把某篇改成几行占位、
或者新增一篇却忘了更新评测集。没有测试的话，这些都不会报错，
只是"问什么都说不知道"，看起来像模型笨。

所以这里钉的是资产本身：
  1. 语料规模与结构（不能被缩成占位）；
  2. 每一篇都自成体系（有主题、有分节、有实质内容）；
  3. 评测集与语料严格对齐（expect_terms 真在文档里、拒答题真在库外）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge_base"
EVAL = ROOT / "evals" / "rag_eval_set.jsonl"

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


files = sorted(KB.glob("*.md")) + sorted(KB.glob("*.txt"))
docs = {p.stem: p.read_text(encoding="utf-8") for p in files}

print("\n=== 1. 语料规模（防止被缩回占位）===")
check("知识库目录存在且有文件", len(files) > 0, f"{len(files)} 篇")
check("至少 12 篇", len(files) >= 12, f"实得 {len(files)} 篇")
total = sum(len(t) for t in docs.values())
check("总字数不少于 3 万字", total >= 30000, f"实得 {total} 字")
check("单篇平均不少于 1500 字",
      total / max(len(docs), 1) >= 1500, f"实得 {int(total / max(len(docs), 1))} 字/篇")

print("\n=== 2. 每篇都要自成体系（不能是几行占位）===")
for stem, text in docs.items():
    h1 = len(re.findall(r"^#\s+\S", text, re.M))
    h2 = len(re.findall(r"^##\s+\S", text, re.M))
    ok = h1 >= 1 and h2 >= 2 and len(text) >= 800
    check(f"{stem}", ok, f"{len(text)} 字 / 一级{h1} 二级{h2}")

print("\n=== 3. 文档标识（用于 expect_source 与溯源）===")
check("没有重名 stem", len(set(docs)) == len(files))
check("文件名不含空格（避免 document_id 出错）",
      all(" " not in s for s in docs), f"{[s for s in docs if ' ' in s]}")
check("没有空文件", all(docs[s].strip() for s in docs))

print("\n=== 4. 内容结构覆盖（教学法 + 学科两条腿）===")
method = [s for s in docs if s.startswith("1")]
subject = [s for s in docs if s.startswith("2")]
check("教学设计与教法不少于 5 篇", len(method) >= 5, f"{len(method)} 篇")
check("学科知识点与误区不少于 5 篇", len(subject) >= 5, f"{len(subject)} 篇")
check("学科篇覆盖 K-12 主科（数/物/化/语/英）",
      all(any(k in s for s in subject) for k in ("数学", "物理", "化学", "语文", "英语")))
check("没有留下示例占位（sample/demo 命名）",
      not any(s.lower().startswith(("sample", "demo", "test")) for s in docs))

print("\n=== 5. 内容可检索性（分节密度与单节体量）===")
# 分块器按标题切分并保留标题路径。真正的风险不是"有没有三级标题"，
# 而是**分节太粗**：一个两千字的二级小节会被切成好几个 chunk，
# 都顶着同一个标题路径，检索到的片段彼此难分，溯源也说不精确。
def sections(text: str) -> list[tuple[str, int]]:
    out, cur, buf = [], None, []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line):
            if cur is not None:
                out.append((cur, len("\n".join(buf).strip())))
            cur, buf = line.strip(), []
        else:
            buf.append(line)
    if cur is not None:
        out.append((cur, len("\n".join(buf).strip())))
    return out


for stem, text in docs.items():
    secs = sections(text)
    body_secs = [(h, n) for h, n in secs if n > 0]
    # 按"所有层级的小节"计数，而不是只数二级：
    # 有的篇按学科分二级、用三级细分，有的篇全是二级 —— 两种都合理，
    # 真正要保证的是**小节总数够多**，检索才有粒度。
    heads = len(re.findall(r"^#{2,6}\s+\S", text, re.M))
    if heads < 8:
        check(f"{stem} 分节足够密", False, f"仅 {heads} 个小节")
    fat = [h for h, n in body_secs if n > 700]
    if fat:
        check(f"{stem} 没有过于臃肿的小节", False, f"{len(fat)} 节超过 700 字：{fat[:2]}")
check("所有文档分节密度与单节体量合格", True, "（逐篇检查见上）")

print("\n=== 6. 评测集与语料严格对齐 ===")
rows = [json.loads(l) for l in EVAL.read_text(encoding="utf-8").splitlines() if l.strip()]
check("评测集 100 条", len(rows) == 100, f"实得 {len(rows)}")
ans = [r for r in rows if r.get("answerable")]
ref = [r for r in rows if not r.get("answerable")]
check("可答 90 条 / 应拒答 10 条", len(ans) == 90 and len(ref) == 10,
      f"可答 {len(ans)} / 拒答 {len(ref)}")

bad_source = [r["id"] for r in ans if r.get("expect_source") not in docs]
check("每条可答题的 expect_source 都是真实文档", not bad_source, f"{bad_source[:5]}")

bad_terms = []
for r in ans:
    body = docs.get(r.get("expect_source"), "")
    for t in r.get("expect_terms") or []:
        if t not in body:
            bad_terms.append(f"{r['id']}:{t}")
check("每条可答题的 expect_terms 真在目标文档里", not bad_terms, f"{bad_terms[:5]}")

all_text = "\n".join(docs.values())
bad_absent = []
for r in ref:
    for t in r.get("expect_absent") or []:
        if t in all_text:
            bad_absent.append(f"{r['id']}:{t}")
check("每条拒答题的关键词在库里确实找不到", not bad_absent, f"{bad_absent[:5]}")
check("拒答题都带 expect_absent（否则会变成永远拒答的假绿灯）",
      all(r.get("expect_absent") for r in ref))

print("\n=== 7. 静态：不许出现可疑占位与外链 ===")
placeholder = [s for s in docs if re.search(r"TODO|待补充|占位|示例内容", docs[s])]
check("没有 TODO / 待补充 / 占位 字样", not placeholder, f"{placeholder}")
check("没有可疑的内部路径或地址",
      not re.search(r"[A-Za-z]:\\\\[Uu]sers|192\.168\.|127\.0\.0\.1", all_text))

print("\n=== 8. 结构化元数据（frontmatter）===")
# 没有 pyyaml（红线 8：能复用就不加依赖），所以自己解析。
# 这里的重点不是"解析得多全"，而是**不能因为一个冒号就把整篇文档丢掉** ——
# 那会让教师改了半天发现查不到，而日志里只有一行 YAML 报错。
sys.path.insert(0, str(ROOT / "backend"))
from app.rag.frontmatter import (  # noqa: E402
    parse_frontmatter, split_frontmatter,
)

fm, body = split_frontmatter(
    "---\nstage: 初中\nsubject: 物理\ngrades: [八年级, 九年级]\n---\n\n# 标题\n正文\n"
)
check("解析出 stage", fm.get("stage") == "初中", str(fm.get("stage")))
check("解析出 subject", fm.get("subject") == "物理")
check("解析出数组 grades", fm.get("grades") == ["八年级", "九年级"], str(fm.get("grades")))
check("正文不含 frontmatter", "stage" not in body and body.startswith("# 标题"))

fm2, body2 = split_frontmatter("---\nstage: 初中\ngrades:\n  - 八年级\n  - 九年级\n---\n正文")
check("块数组也能解析", fm2.get("grades") == ["八年级", "九年级"], str(fm2.get("grades")))

check("没有 frontmatter 时整篇是正文", split_frontmatter("# 标题\n正文")[1].startswith("# 标题"))
check("正文中间的 --- 分隔线不被当 frontmatter",
      parse_frontmatter("# 标题\n\n第一段\n\n---\n\n第二段") == {})
check("开了头没闭合 → 按整篇正文处理（不半截解析）",
      split_frontmatter("---\nstage: 初中\n\n# 标题\n正文")[1].startswith("---"))
check("坏写法不抛异常（冒号缺失等）",
      isinstance(split_frontmatter("---\n这不是键值对啊\n---\n正文"), tuple))
check("空输入不炸", split_frontmatter("") == ({}, ""))
check("带引号的值会被去掉引号",
      parse_frontmatter('---\nsubject: "物理"\n---\nx').get("subject") == "物理")
check("行尾注释会被去掉",
      parse_frontmatter("---\nstage: 初中  # 学段\n---\nx").get("stage") == "初中")

print("\n=== 9. 每篇语料都要带可过滤的元数据 ===")
for stem, text in docs.items():
    meta = parse_frontmatter(text)
    missing = [k for k in ("stage", "subject", "type") if not meta.get(k)]
    if missing:
        check(f"{stem} 元数据齐全", False, f"缺 {missing}")
check("全部语料都带 stage / subject / type", True, "（逐篇检查见上）")
stages = {parse_frontmatter(t).get("stage") for t in docs.values()}
check("学段覆盖小学与初中", {"小学", "初中"} <= stages, str(sorted(stages)))
types = {parse_frontmatter(t).get("type") for t in docs.values()}
check("类型覆盖教学法与学科知识点", {"教学法", "学科知识点"} <= types, str(sorted(types)))

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
