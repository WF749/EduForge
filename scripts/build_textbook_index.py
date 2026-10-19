#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从本地教材 PDF 自动提取目录，生成教材索引。

用法
----
    PYTHONPATH=backend uv run --project backend python scripts/build_textbook_index.py \
        --src "C:/path/to/textbooks" --out knowledge_base/textbooks/index.json

为什么只建索引、不存正文
------------------------
教材 PDF **版权归出版社**（ChinaTextbook 仓库自身就是 All Rights Reserved），
把正文甚至 PDF 本体放进开源仓库会变成我们自己的侵权风险。
所以索引里只有**目录结构**（章/节标题 + 页码）—— 那是定位用的事实信息，
正文一律留在用户本地，不进版本控制。

生成的索引能回答的核心问题：
    「浮力」在人教版初中物理的哪一册、第几章、第几节、第几页？
答不上来（本地没有那本教材）就返回 None，生成链路降级到知识点大纲 ——
这正是"有教材参考教材，没教材从知识点出发"的落点。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

# ---------------------------------------------------------------------------
# 文件名 → 教材身份（学段 / 学科 / 年级 / 册 / 版本）
# ---------------------------------------------------------------------------

SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "道德与法治",
            "历史", "地理", "科学", "信息技术", "思想政治"]

GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
          "七年级", "八年级", "九年级", "初一", "初二", "初三",
          "高一", "高二", "高三"]

BAND_HINT = {"小学": "primary", "初中": "junior", "高中": "senior"}


def parse_identity(filename: str) -> Dict[str, str]:
    """从教材文件名解析身份信息。

    真实文件名示例：
        义务教育教科书·物理八年级上册.pdf
        普通高中教科书·数学（A版）必修第二册.pdf
    """
    name = os.path.basename(filename)
    base = os.path.splitext(name)[0]

    subject = next((s for s in SUBJECTS if s in base), "")
    grade = next((g for g in GRADES if g in base), "")

    if "普通高中" in base or "高中" in base:
        band = "senior"
    elif "义务教育" in base and any(g in base for g in ("七年级", "八年级", "九年级", "初一", "初二", "初三")):
        band = "junior"
    elif "义务教育" in base:
        band = "primary"
    else:
        band = ""

    volume = "上册" if "上册" in base else ("下册" if "下册" in base else "")
    if not volume:
        m = re.search(r"(必修[第]?[一二三四五六七八九十]?册|选择性必修[第]?[一二三四五六七八九十]?册)", base)
        volume = m.group(1) if m else ""

    version = "人教版" if ("人民教育出版社" in base or "人教版" in base or "义务教育" in base) else ""
    return {"band": band, "subject": subject, "grade": grade,
            "volume": volume, "version": version, "title": base}


# ---------------------------------------------------------------------------
# 目录页识别与解析
# ---------------------------------------------------------------------------

# 实测三套教材用了三种目录格式，解析器必须都认：
#   A 初中物理：第一章 机械运动 9 / 第1节 长度和时间的测量 10
#   B 小学数学：1 位置与方向（一）  ⏎ 2        （标题与页码**跨行**）
#   C 高中数学：第六章 平面向量及其应用…………１（全角数字 + 点线引导）
_DOTS = r"[\s…．·\.]{1,}"                      # 点线引导符（含全角）
_NUM = r"([0-9０-９]+)"                        # 半角或全角数字

_CHAPTER = re.compile(rf"^第\s*([一二三四五六七八九十百]+|\d+)\s*章\s+(.+?){_DOTS}{_NUM}\s*$")
_SECTION = re.compile(rf"^第\s*(\d+)\s*节\s+(.+?){_DOTS}{_NUM}\s*$")
# 高中式小节：６．１ 平面向量的概念……２
_SECTION_DOT = re.compile(rf"^{_NUM}[．.]\s*{_NUM}\s*(.+?){_DOTS}{_NUM}\s*$")
# 小学式：1 位置与方向（一） 2   （编号 + 标题 + 页码同行）
_ITEM = re.compile(rf"^(\d+)\s+(.+?)\s+(\d+)\s*$")
# 小学式跨行：这一行只有页码
_ONLY_PAGE = re.compile(rf"^{_NUM}\s*$")
_TOC_MARK = re.compile(r"^\s*目\s*录\s*$")

# 全角数字（０-９, U+FF10-FF19）→ 半角
_FULL2HALF = {ord(chr(0xFF10 + i)): ord(str(i)) for i in range(10)}


def _norm(s: str) -> str:
    """全角数字 → 半角，压缩空白。"""
    return re.sub(r"\s+", " ", s.translate(_FULL2HALF)).strip()

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s: str) -> int:
    if s.isdigit():
        return int(s)
    # 只处理「十一」~「二十」这种简单情形，够教材目录用
    if s.startswith("十"):
        return 10 + _CN_NUM.get(s[1], 0) if len(s) > 1 else 10
    if "十" in s:
        a, _, b = s.partition("十")
        return _CN_NUM.get(a, 1) * 10 + _CN_NUM.get(b, 0)
    return _CN_NUM.get(s, 0)


def _dedup(lines: List[str]) -> List[str]:
    """扫描版教材的文字层常把同一行输出两遍（"主 编"/"主主 编编"），去重。"""
    out, prev = [], None
    for l in lines:
        if l != prev:
            out.append(l)
        prev = l
    return out


# 「…………………… １」或单独一行的「2」——都是上一行标题的页码
_TRAILING_PAGE = re.compile(rf"^{_DOTS}{_NUM}\s*$|^{_NUM}\s*$")


def _merge_trailing_pages(lines: List[str]) -> List[str]:
    """把跨行的页码并回标题行。

    实测两种教材都把页码放到下一行：
      高中：第六章 平面向量及其应用 ⏎ ……………………… １
      小学：1 位置与方向（一）        ⏎ 2
    先合并成一行，后面的匹配规则就只需处理"同行有页码"这一种情形。
    """
    out: List[str] = []
    for line in lines:
        if out and _TRAILING_PAGE.match(line):
            m = re.search(r"(\d+)", line)
            if m:
                out[-1] = f"{out[-1]} {m.group(1)}"
                continue
        out.append(line)
    return out


def _page_text(pdf, idx: int) -> List[str]:
    try:
        txt = pdf.pages[idx].extract_text() or ""
    except Exception:
        return []
    return _dedup([l.strip() for l in txt.split("\n") if l.strip()])


def extract_toc(pdf_path: str, max_scan: int = 16) -> List[Dict[str, Any]]:
    """提取教材目录：返回 [{no, title, page, sections:[{no,title,page}]}]"""
    import pdfplumber

    # 先探一遍：这本教材的目录有没有"章"这一层
    flat_mode = False
    with pdfplumber.open(pdf_path) as _probe:
        probe_pages = min(len(_probe.pages), max_scan)
        chap_hits = 0
        for i in range(probe_pages):
            try:
                txt = _probe.pages[i].extract_text() or ""
            except Exception:
                continue
            chap_hits += sum(1 for l in txt.split("\n") if _CHAPTER.match(_norm(l.strip())))
        flat_mode = chap_hits < 2

    units: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    pending_item: Optional[Dict[str, Any]] = None   # 小学式：标题已读到，等下一行的页码

    def flush_pending(page: int):
        nonlocal pending_item
        if pending_item is not None:
            pending_item["page"] = page
            if cur is not None:
                cur["sections"].append(pending_item)
            pending_item = None

    with pdfplumber.open(pdf_path) as pdf:
        pages = min(len(pdf.pages), max_scan)
        for i in range(pages):
            lines = _merge_trailing_pages([_norm(l) for l in _page_text(pdf, i)])
            if not lines:
                continue

            # 目录页：出现「目录」标记，或本页能解析出 ≥2 个章
            has_mark = any(_TOC_MARK.match(l) for l in lines)
            ch_hits = [l for l in lines if _CHAPTER.match(l)]
            if not has_mark and len(ch_hits) < 2 and cur is None:
                continue

            for line in lines:
                # 独立的页码行 → 补到上一个待定标题
                m = _CHAPTER.match(line)
                if m:
                    flush_pending(0)
                    cur = {"no": _cn_to_int(m.group(1)),
                           "title": m.group(2).strip(),
                           "page": int(m.group(3)),
                           "sections": []}
                    units.append(cur)
                    continue

                m2 = _SECTION.match(line)
                if m2:
                    flush_pending(0)
                    if cur is not None:
                        cur["sections"].append({"no": int(m2.group(1)),
                                                "title": m2.group(2).strip(),
                                                "page": int(m2.group(3))})
                    continue

                m3 = _SECTION_DOT.match(line)
                if m3:
                    flush_pending(0)
                    if cur is not None:
                        cur["sections"].append(
                            {"no": int(m3.group(2)),
                             "title": m3.group(3).strip(),
                             "page": int(m3.group(4))})
                    continue

                # 小学式「1 位置与方向（一）」—— 页码可能在下一行
                m4 = re.match(r"^(\d+)\s+(.+?)\s+(\d+)$", line)
                if m4 and len(m4.group(2).strip()) >= 2:
                    flush_pending(0)
                    item = {"no": int(m4.group(1)),
                            "title": m4.group(2).strip(),
                            "page": int(m4.group(3))}
                    # 小学数学目录是平铺条目，没有"章"这一层
                    # （实测：1 位置与方向（一）… 2 除数是一位数的除法…）。
                    # 若压成"1 章 N 节"会丢掉单元边界，检索时定位就错了。
                    if flat_mode:
                        units.append({"no": item["no"], "title": item["title"],
                                      "page": item["page"], "sections": []})
                    elif cur is not None:
                        cur["sections"].append(item)
                    continue

            if len(units) >= 3 and has_mark and i >= 5:
                break

        flush_pending(0)
    return units


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build(src_dir: str) -> Dict[str, Any]:
    books: List[Dict[str, Any]] = []
    for root, _, files in os.walk(src_dir):
        for f in sorted(files):
            if not f.lower().endswith(".pdf"):
                continue
            path = os.path.join(root, f)
            ident = parse_identity(f)
            if not ident["subject"]:
                continue  # 不是学科教材（如平台操作指南）
            try:
                units = extract_toc(path)
            except Exception as e:
                print(f"  [跳过] {f}: {e}")
                continue
            if not units:
                print(f"  [无目录] {f}")
                continue
            ident["file"] = os.path.relpath(path, src_dir).replace("\\", "/")
            ident["units"] = units
            ident["section_count"] = sum(len(u["sections"]) for u in units)
            books.append(ident)
            print(f"  [OK] {f} → {len(units)} 章 / {ident['section_count']} 节")
    return {
        "version": 1,
        "note": "只存目录结构用于定位，不存教材正文（版权归出版社，正文不入库）",
        "books": books,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="本地教材 PDF 目录")
    ap.add_argument("--out", default=os.path.join(ROOT, "knowledge_base", "textbooks", "index.json"))
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"目录不存在: {args.src}")
        return 1
    print(f"扫描: {args.src}")
    data = build(args.src)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {args.out}（{len(data['books'])} 本教材）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
