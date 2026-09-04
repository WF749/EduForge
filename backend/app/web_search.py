"""Fetch short reference snippets for teaching (no API keys; best-effort)."""
from __future__ import annotations

import asyncio
import re
from typing import List

import httpx

_UA = "Mozilla/5.0 (compatible; A04TeachingAgent/1.0; education)"
_TIMEOUT = 3  # 进一步减少超时时间


async def _ddg_abstract(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "no_redirect": 1},
                headers={"User-Agent": _UA},
            )
            j = r.json()
            ab = (j.get("AbstractText") or j.get("Abstract") or "").strip()
            if ab:
                return ab
            for t in j.get("RelatedTopics") or []:
                if isinstance(t, dict) and t.get("Text"):
                    return str(t["Text"])[:1200]
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
    return ""


async def _wiki_snippets(lang: str, query: str, max_items: int) -> List[str]:
    out: List[str] = []
    host = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as client:
            r = await client.get(
                host,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_items,
                    "format": "json",
                },
                headers={"User-Agent": _UA},
            )
            titles = [x["title"] for x in r.json().get("query", {}).get("search", [])][:max_items]
            for title in titles:
                try:
                    r2 = await client.get(
                        host,
                        params={
                            "action": "query",
                            "prop": "extracts",
                            "explaintext": 1,
                            "exintro": 1,
                            "titles": title,
                            "format": "json",
                        },
                        headers={"User-Agent": _UA},
                    )
                    pages = (r2.json().get("query") or {}).get("pages") or {}
                    for _pid, page in pages.items():
                        ex = (page.get("extract") or "").strip()
                        if ex:
                            out.append(f"【{title}】\n{ex[:1800]}")
                            break
                except Exception:
                    continue
    except Exception as e:
        print(f"Wikipedia search failed for {lang}: {e}")
    return out


async def search_snippets_async(query: str, max_chars: int = 4000) -> str:
    """Return concatenated snippets for RAG-style injection into the LLM prompt."""
    q = (query or "").strip()
    if len(q) < 2:
        return ""
    
    # 并行执行多个搜索，减少总等待时间
    ddg_task = asyncio.create_task(_ddg_abstract(q))
    wiki_zh_task = asyncio.create_task(_wiki_snippets("zh", q, 2))
    
    # 等待所有任务完成，最多等待总超时时间
    done, _ = await asyncio.wait(
        [ddg_task, wiki_zh_task],
        timeout=_TIMEOUT * 2  # 总超时时间
    )
    
    parts: List[str] = []
    
    # 收集完成的任务结果
    for task in done:
        try:
            result = task.result()
            if result:
                if isinstance(result, list):
                    parts.extend(result)
                else:
                    parts.append(f"[DuckDuckGo 摘要]\n{result[:2000]}")
        except Exception:
            pass
    
    # 如果中文维基结果不够，尝试英文维基
    if len("\n\n".join(parts)) < 400:
        try:
            wiki_en_result = await _wiki_snippets("en", q, 1)
            parts.extend(wiki_en_result)
        except Exception:
            pass
    
    text = "\n\n".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[资料过长已截断]"
    return text


def search_snippets(query: str, max_chars: int = 4000) -> str:
    """同步包装器"""
    return asyncio.run(search_snippets_async(query, max_chars))
