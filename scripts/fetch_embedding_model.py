#!/usr/bin/env python
"""下载 RAG 所需的两个本地模型。

    --model embedding   bge-small-zh-v1.5   中文向量化   ~95MB
    --model rerank      bge-reranker-base   本地重排序   ~1.0GB
    --model all         两者都要

为什么需要这个脚本，而不是直接 `SentenceTransformer('BAAI/xxx')`
------------------------------------------------------------------------------
实测（2026-09-02，国内网络）：

  1. `huggingface.co` 直连经常 502；社区镜像 `hf-mirror.com` 可用。
  2. 但 **huggingface_hub 经镜像下载会静默产生 0 字节文件** ——
     `modules.json`、`config_sentence_transformers.json`、`model.safetensors`
     都出现过下载"成功"但内容为空的情况，随后报
     `json.decoder.JSONDecodeError: Expecting value` 或
     `safetensors_rust.SafetensorError: header too small`。
     这类错误极具迷惑性：看起来是模型坏了，实际是网络层截断。

因此本脚本改用**直连 HTTP 逐个文件下载 + Content-Length 校验**，
失败自动重试，最后再验证模型能真正加载。

用法
----
    python scripts/fetch_embedding_model.py                  # 下载并验证（默认 embedding）
    python scripts/fetch_embedding_model.py --model rerank    # 下载 rerank 模型
    python scripts/fetch_embedding_model.py --model all
    python scripts/fetch_embedding_model.py --check --model all   # 只检查本地是否就绪
"""

from __future__ import annotations

import argparse
import os
import ssl
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

MIRRORS = [
    "https://hf-mirror.com",
    "https://huggingface.co",
]


@dataclass
class Spec:
    """一个模型的下载规格。"""

    key: str
    model_id: str
    files: list[str]
    min_size: dict[str, int] = field(default_factory=dict)  # 空文件检测下限（字节）
    loader: str = "sbert"      # sbert=SentenceTransformer, cross=CrossEncoder

    @property
    def dir_name(self) -> str:
        return "models--" + self.model_id.replace("/", "--")


SPECS: dict[str, Spec] = {
    "embedding": Spec(
        key="embedding",
        model_id="BAAI/bge-small-zh-v1.5",
        files=[
            "config.json",
            "config_sentence_transformers.json",
            "modules.json",
            "sentence_bert_config.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.txt",
            "1_Pooling/config.json",
            "model.safetensors",
        ],
        min_size={
            "model.safetensors": 10 * 1024 * 1024,
            "tokenizer.json": 10 * 1024,
            "vocab.txt": 10 * 1024,
        },
        loader="sbert",
    ),
    # bge-reranker-base：XLMRoberta cross-encoder，中文重排序。
    # 选它而不是 v2-m3（2.2GB）是为了让"本地可跑"这件事在普通机器上成立。
    # 注意：该仓库没有 modules.json，CrossEncoder 直接走 transformers 加载。
    "rerank": Spec(
        key="rerank",
        model_id="BAAI/bge-reranker-base",
        files=[
            "config.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "sentencepiece.bpe.model",
            "model.safetensors",
        ],
        min_size={
            "model.safetensors": 500 * 1024 * 1024,
            "tokenizer.json": 10 * 1024,
            "sentencepiece.bpe.model": 100 * 1024,
        },
        loader="cross",
    ),
}


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def model_dir(root: Path, spec: Spec) -> Path:
    return root / "backend" / "models_cache" / spec.dir_name


def snapshot_dir(root: Path, spec: Spec) -> Path | None:
    d = model_dir(root, spec) / "snapshots"
    if not d.exists():
        return None
    for c in sorted(d.iterdir()):
        if c.is_dir() and (c / "config.json").exists():
            return c
    return None


def is_ready(root: Path, spec: Spec) -> tuple[bool, str]:
    snap = snapshot_dir(root, spec)
    if snap is None:
        return False, "未找到模型快照"
    for f in spec.files:
        p = snap / f
        if not p.exists():
            return False, f"缺少文件 {f}"
        size = p.stat().st_size
        if size == 0 or size < spec.min_size.get(f, 1):
            return False, f"文件不完整 {f}（{size} 字节）"
    return True, str(snap)


def _download_one(
    url: str, dest: Path, expected_total: int, min_size: int, ctx: ssl.SSLContext
) -> bool:
    """流式下载单个文件，支持断点续传。

    为什么不用"全部读进内存再一次性写盘"：
     rerank 模型权重 1GB，全部缓存到内存里既看不到进度、也无法续传 ——
     实测过一次连接挂死，进程内存不再增长但一直不返回，只能杀掉重来，
     前 20 分钟白等。流式写盘 + Range 续传可以让重试从断点继续。
    """
    have = dest.stat().st_size if dest.exists() else 0
    headers = {"User-Agent": "Mozilla/5.0"}
    mode = "wb"
    if have and expected_total and have < expected_total:
        headers["Range"] = f"bytes={have}-"
        mode = "ab"
        print(f"  [续传] 从 {have / 1024 / 1024:.1f} MB 继续")
    elif have:
        dest.unlink()          # 大小异常，重下
        have = 0

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        # 服务器不支持 Range 时会返回 200 而非 206，此时必须从头写
        if mode == "ab" and r.status != 206:
            mode = "wb"
            have = 0
        total = int(r.headers.get("Content-Length") or 0)
        if mode == "wb":
            expected_total = total or expected_total
        else:
            expected_total = expected_total or (have + total)

        written = have
        last_report = time.time()
        with dest.open(mode) as f:
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
                now = time.time()
                if now - last_report >= 5.0:      # 每 5 秒报一次，便于判断是否卡死
                    last_report = now
                    mb = written / 1024 / 1024
                    if expected_total:
                        print(f"    … {mb:.0f}/{expected_total / 1024 / 1024:.0f} MB "
                              f"({written / expected_total * 100:.0f}%)")
                    else:
                        print(f"    … {mb:.0f} MB")

    if expected_total and written != expected_total:
        raise ValueError(f"长度不符 已写 {written} != 期望 {expected_total}")
    if written < min_size:
        raise ValueError(f"内容过小 {written} 字节，疑似被截断")
    return True


def download(root: Path, spec: Spec, *, force: bool = False) -> int:
    snap = snapshot_dir(root, spec)
    if snap is None:
        snap = model_dir(root, spec) / "snapshots" / "main"
    snap.mkdir(parents=True, exist_ok=True)

    ctx = _ssl_ctx()
    ok = True
    for fname in spec.files:
        dest = snap / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not force and dest.exists() and dest.stat().st_size >= spec.min_size.get(fname, 1):
            print(f"  [跳过] {fname}（已存在 {dest.stat().st_size} 字节）")
            continue

        expected_total = 0
        got = False
        for base in MIRRORS:
            url = f"{base}/{spec.model_id}/resolve/main/{fname}"
            for attempt in range(1, 6):
                try:
                    _download_one(url, dest, expected_total,
                                  spec.min_size.get(fname, 1), ctx)
                    mb = dest.stat().st_size / 1024 / 1024
                    print(f"  [完成] {fname}  {mb:.1f} MB  ({base})")
                    got = True
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"  [重试{attempt}] {fname} 失败：{e}")
                    time.sleep(2.0 * attempt)
            if got:
                break
        if not got:
            print(f"  [失败] {fname} —— 所有源均不可用"
                  f"（已下载部分会保留，重跑本脚本可续传）")
            ok = False

    return 0 if ok else 1


def verify(root: Path, spec: Spec, snap: str) -> int:
    t = time.time()
    try:
        if spec.loader == "cross":
            from sentence_transformers import CrossEncoder

            m = CrossEncoder(snap)
            pairs = [
                ("配方法的步骤是什么", "配方法步骤：移项、二次项系数化为1、配方、开方、求解"),
                ("配方法的步骤是什么", "您好，欢迎光临本酒店，请问有什么可以帮您？"),
            ]
            scores = m.predict(pairs)
            print(f"  CrossEncoder 加载成功（{time.time() - t:.1f}s）")
            print(f"    相关={float(scores[0]):.3f}  无关={float(scores[1]):.3f}  "
                  f"区分度={float(scores[0]) - float(scores[1]):.3f}")
            if float(scores[0]) <= float(scores[1]):
                print("  [警告] 相关分未高于无关分，模型可能损坏")
                return 1
        else:
            from sentence_transformers import SentenceTransformer

            m = SentenceTransformer(snap)
            dim = int((getattr(m, "get_embedding_dimension", None)
                       or m.get_sentence_embedding_dimension)())
            v = m.encode(["牛顿第二定律", "古诗教学方法"])
            print(f"  SentenceTransformer 加载成功（{time.time() - t:.1f}s）："
                  f"dim={dim} 编码={v.shape}")
    except ImportError:
        print("  sentence-transformers 未安装，跳过加载验证")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  模型加载失败：{type(e).__name__}: {e}")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 RAG 本地模型")
    ap.add_argument("--model", choices=["embedding", "rerank", "all"],
                    default="embedding", help="要处理的模型（默认 embedding）")
    ap.add_argument("--check", action="store_true", help="只检查本地是否就绪")
    ap.add_argument("--force", action="store_true", help="强制重新下载")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("HF_ENDPOINT", MIRRORS[0])

    keys = ["embedding", "rerank"] if args.model == "all" else [args.model]
    rc = 0

    for key in keys:
        spec = SPECS[key]
        print(f"\n=== {spec.model_id} ===")
        if args.check:
            ready, detail = is_ready(root, spec)
            print(f"{'就绪' if ready else '未就绪'}：{detail}")
            rc |= 0 if ready else 1
            continue

        print(f"下载到 {model_dir(root, spec)}")
        rc |= download(root, spec, force=args.force)
        ready, detail = is_ready(root, spec)
        if not ready:
            print(f"下载未完整：{detail}")
            rc |= 1
            continue
        print("校验模型可加载：")
        rc |= verify(root, spec, detail)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
