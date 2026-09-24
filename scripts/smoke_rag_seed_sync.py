"""种子索引同步与来源标记的冒烟测试（临时目录 + 内存索引，秒级）。

为什么这三件事必须有测试 —— 它们的失败形态都是"操作成功、数据没了/没变"：

  1. `POST /api/rag/reindex` 曾调用 `clear()`，把用户上传的资料一并删掉，
     而接口返回 success。教师重启一次服务，课件与资料全没了，毫无提示。
  2. 来源标记曾有两个字段（种子写 `source="seed"`、上传写 `origin="upload"`），
     而"能不能删"是按 `origin` 判定的 —— 种子靠"恰好没有 origin"侥幸存活，
     任何一处改字段名就会误删或漏删。
  3. 启动播种曾只看"id 在不在"，于是改了文件不更新、删了文件不移除，
     都静默发生：改了查不到新的，删了还在检索旧的。
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.retriever import (  # noqa: E402
    ORIGIN_SEED, ORIGIN_UPLOAD, is_seed_metadata,
)
from app.rag.seed_sync import (  # noqa: E402
    content_hash, seed_metadata, seed_files, sync_seed_index,
)

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


# ---------------------------------------------------------------------------
# 一个够用的假检索器：只实现同步逻辑需要的接口，避免动真实索引
# ---------------------------------------------------------------------------
class FakeRetriever:
    def __init__(self) -> None:
        self.documents: dict = {}
        self.chunks: dict = {}
        self.calls: list = []

    def add_document(self, doc_id, content, metadata=None, **kw):
        self.calls.append(("add", doc_id))
        n = max(1, len(content) // 300)
        self.documents[doc_id] = {
            "document_id": doc_id,
            "chunks": n,
            "chars": len(content),
            "metadata": dict(metadata or {}),
        }
        for i in range(n):
            self.chunks[f"{doc_id}_{i}"] = {"source": doc_id}
        return {"document_id": doc_id, "chunks": n}

    def delete_document(self, doc_id, save=True):
        self.calls.append(("del", doc_id))
        for cid in [c for c, v in self.chunks.items() if v["source"] == doc_id]:
            self.chunks.pop(cid)
        self.documents.pop(doc_id, None)
        return 1

    def clear_seed(self):
        ids = [d for d, doc in self.documents.items() if is_seed_metadata(doc.get("metadata"))]
        for d in ids:
            self.delete_document(d)
        return len(ids)

    def clear(self):
        self.documents.clear()
        self.chunks.clear()


print("\n=== 1. origin 标记：单一口径 ===")
check("种子与上传两个常量不同", ORIGIN_SEED != ORIGIN_UPLOAD)
check("seed metadata 的 origin 是 seed",
      seed_metadata("a.md", "x")["origin"] == ORIGIN_SEED)
check("seed metadata 带 filename 与 hash",
      {"filename", "content_hash"} <= set(seed_metadata("a.md", "x")))
check("判定：origin=seed 算种子", is_seed_metadata({"origin": ORIGIN_SEED}))
check("判定：历史遗留 source=seed 也算种子（否则会变成孤儿）",
      is_seed_metadata({"source": ORIGIN_SEED}))
check("判定：origin=upload 不算种子", not is_seed_metadata({"origin": ORIGIN_UPLOAD}))
check("判定：空 metadata 不算种子", not is_seed_metadata(None) and not is_seed_metadata({}))

print("\n=== 2. 内容 hash ===")
check("同样内容同 hash", content_hash("浮力") == content_hash("浮力"))
check("不同内容不同 hash", content_hash("浮力") != content_hash("压强"))
check("空串不炸", isinstance(content_hash(""), str))
check("长度固定 16", len(content_hash("任意")) == 16)

# ---------------------------------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="kb_sync_"))
try:
    (tmp / "aaa.md").write_text("# 甲\n\n内容甲", encoding="utf-8")
    (tmp / "bbb.md").write_text("# 乙\n\n内容乙", encoding="utf-8")

    print("\n=== 3. 首次同步：全部新增 ===")
    r = FakeRetriever()
    out = sync_seed_index(r, tmp)
    check("两篇都被加入", set(r.documents) == {"aaa", "bbb"}, str(sorted(r.documents)))
    check("报告为新增", out["added"] and not out["updated"] and not out["removed"])
    check("metadata 带 origin=seed", r.documents["aaa"]["metadata"]["origin"] == ORIGIN_SEED)

    print("\n=== 4. 内容没变 → 不重建（省时间也省额度）===")
    before = list(r.calls)
    out = sync_seed_index(r, tmp)
    check("没有 add 也没有 del", not out["added"] and not out["updated"] and not out["removed"])
    check("未变计数为 2", out["unchanged"] == 2, str(out["unchanged"]))
    check("确实没调用 add", ("add", "aaa") not in [c for c in r.calls if c not in before]
          or len(r.calls) == len(before))

    print("\n=== 5. 改了文件 → 重建（这是原先静默失效的地方）===")
    (tmp / "aaa.md").write_text("# 甲\n\n内容甲改过了，改了很多", encoding="utf-8")
    out = sync_seed_index(r, tmp)
    check("aaa 被判为更新", out["updated"] == ["aaa"], str(out["updated"]))
    check("bbb 不受影响", "bbb" not in out["updated"])
    check("新 hash 已写回",
          r.documents["aaa"]["metadata"]["content_hash"] == content_hash(
              (tmp / "aaa.md").read_text(encoding="utf-8")))

    print("\n=== 6. 删了文件 → 移除索引（原先会继续被检索出来）===")
    (tmp / "bbb.md").unlink()
    out = sync_seed_index(r, tmp)
    check("bbb 被移除", out["removed"] == ["bbb"], str(out["removed"]))
    check("索引里已没有 bbb", "bbb" not in r.documents)

    print("\n=== 7. 用户上传的内容：同步与 reindex 都不许碰 ===")
    r.documents["我的课件"] = {"document_id": "我的课件", "chunks": 1, "chars": 10,
                              "metadata": {"origin": ORIGIN_UPLOAD, "filename": "浮力课件.pdf"}}
    r.chunks["我的课件_0"] = {"source": "我的课件"}
    # reindex 用的是 clear_seed
    removed = r.clear_seed()
    check("clear_seed 只删种子", "我的课件" in r.documents, f"删了 {removed} 篇")
    check("clear_seed 确实删掉了种子", "aaa" not in r.documents)
    # 同步（改名加回文件）同样不能碰上传
    out = sync_seed_index(r, tmp)
    check("同步后上传内容仍在", "我的课件" in r.documents)

    print("\n=== 8. 反向对照：clear 是全清，clear_seed 不是 ===")
    r2 = FakeRetriever()
    r2.add_document("s", "种子内容" * 200, seed_metadata("s.md", "种子内容"))
    r2.add_document("u", "上传内容" * 200, {"origin": ORIGIN_UPLOAD})
    r2.clear_seed()
    check("clear_seed 后种子没了、上传还在",
          "s" not in r2.documents and "u" in r2.documents)
    r2.clear()
    check("clear 后全部没了（所以它绝不能被 reindex 调用）",
          not r2.documents and not r2.chunks)

    print("\n=== 9. 目录不存在 / 空目录 / 空文件 都不炸 ===")
    r3 = FakeRetriever()
    out = sync_seed_index(r3, tmp / "不存在的目录")
    check("目录不存在返回空同步", out["added"] == [] and not out["errors"])
    empty = Path(tempfile.mkdtemp(prefix="kb_empty_"))
    try:
        out = sync_seed_index(r3, empty)
        check("空目录不炸", out["documents"] == 0)
        (empty / "blank.md").write_text("   \n\n", encoding="utf-8")
        out = sync_seed_index(r3, empty)
        check("空文件被跳过（不产生空文档）", "blank" not in r3.documents)
    finally:
        shutil.rmtree(empty, ignore_errors=True)

    print("\n=== 10. 只认 md / txt ===")
    (tmp / "ignored.pdf").write_text("不该被索引", encoding="utf-8")
    stems = [f.stem for f in seed_files(tmp)]
    check("pdf 不在种子文件里", "ignored" not in stems, str(stems))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
