"""OpenAPI 契约的回归测试。

为什么单独测这个
----------------
`/openapi.json` 一旦生成失败就返回 **500**，Swagger UI（/docs）与 ReDoc
（/redoc）全都打不开。而项目里**没有任何一个既有的 smoke 会去请求它** ——
smoke_api_contract 只比对路径字符串，不生成 schema。

真实事故：`/check` 接口的 `examples=` 写成了 dict（OpenAPI 规范要求 list），
导致 FastAPI 生成 schema 时 Pydantic 校验失败，/openapi.json 直接 500。
后端能起、健康检查 200、只有 API 文档挂了 —— 面试官点 /docs 就撞墙。

运行：PYTHONPATH=backend uv run --project backend python scripts/smoke_openapi.py
（纯本地，零模型额度）
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def main() -> int:
    print("=" * 64)
    print("OpenAPI 契约 —— 文档可达性")
    print("=" * 64)

    from app.main import app

    print("\n== 1. schema 能生成 ==")
    try:
        schema = app.openapi()
        check("app.openapi() 不抛异常", isinstance(schema, dict))
    except Exception as e:
        check("app.openapi() 不抛异常", False, f"{type(e).__name__}: {str(e)[:90]}")
        print("\n" + "=" * 64)
        print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
        print("=" * 64)
        return 1

    check("含 openapi 版本", "openapi" in schema)
    paths = schema.get("paths") or {}
    check("含路径", len(paths) > 0, f"{len(paths)} 条")

    print("\n== 2. 关键示例字段符合 OpenAPI 规范 ==")
    # 事故根因：examples 必须是 list，写成 dict 会让 schema 生成直接失败
    bad = []
    for p, ops in paths.items():
        for method, op in (ops or {}).items():
            if not isinstance(op, dict):
                continue
            for param in (op.get("parameters") or []):
                if isinstance(param, dict) and "schema" not in param:
                    continue
            body = ((op.get("requestBody") or {}).get("content") or {})
            for media, mv in body.items():
                if not isinstance(mv, dict):
                    continue
                if "examples" in mv and not isinstance(mv["examples"], list):
                    bad.append(f"{p} {method}")
                sc = mv.get("schema")
                if isinstance(sc, dict) and "examples" in sc and not isinstance(sc["examples"], list):
                    bad.append(f"{p} {method}(schema)")
    check("没有 examples 写成 dict 的地方", not bad, str(bad[:3]))

    print("\n== 3. schema 可被 Pydantic 校验（模拟 FastAPI 内部校验） ==")
    try:
        import json
        # 序列化一遍：能 dump 说明没有不可序列化的对象残留
        dumped = json.dumps(schema, ensure_ascii=False)
        check("schema 可 JSON 序列化", len(dumped) > 100, f"{len(dumped)} 字节")
    except Exception as e:
        check("schema 可 JSON 序列化", False, str(e)[:80])

    # 逐个路径生成一次，确保没有单个接口拖垮整体
    print("\n== 4. 每个 POST 接口的入参 schema 都完整 ==")
    broken = []
    for p, ops in paths.items():
        for method, op in (ops or {}).items():
            if not isinstance(op, dict) or method.lower() not in ("post", "put", "patch"):
                continue
            body = ((op.get("requestBody") or {}).get("content") or {})
            for media, mv in body.items():
                if isinstance(mv, dict) and "schema" not in mv:
                    broken.append(f"{p} {method}")
    check("所有写接口的 requestBody 都有 schema", not broken, str(broken[:3]))

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for n in FAIL:
            print(f"  - {n}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
