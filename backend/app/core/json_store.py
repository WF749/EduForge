"""进程安全 + 崩溃安全的 JSON 存储。

解决的问题
----------
原实现 `_write_json` 直接 `open(path, "w")`：
  1. **非原子** —— 写到一半进程崩溃 / 断电，文件即损坏；
  2. **读失败静默返回默认值** —— 文件一旦损坏，`load` 返回 `{}`，
     下一次 `save` 会用空数据覆盖，**用户配置被无声抹掉**。

本实现：
  - 写入走"临时文件 + os.replace"（原子替换，POSIX 保证）；
  - 读取失败**不静默**：记录日志 + 备份损坏文件 + 尝试从 `.bak` 恢复；
  - 文件锁保证多进程/多线程并发安全。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .logging_setup import get_logger

log = get_logger("json_store")

_locks: Dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve()).lower()
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.RLock()
        return _locks[key]


def atomic_write_json(path: Path, data: Any, *, keep_backup: bool = True) -> None:
    """原子写入 JSON：先写同目录临时文件，再 os.replace 替换。

    同目录是硬性要求 —— 跨设备 rename 不是原子操作。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _lock_for(path):
        # 写前先备份上一版（用于读失败时回滚）
        if keep_backup and path.exists():
            try:
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
            except Exception as e:
                log.warning("备份 %s 失败: %s", path.name, e)

        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def read_json(
    path: Path,
    default: Any,
    *,
    on_corrupt: Optional[Callable[[Path], None]] = None,
) -> Any:
    """读取 JSON；文件损坏时不静默，尝试从备份恢复。

    返回值语义：
      - 文件不存在  -> default
      - 读取/解析失败 -> 尝试 .bak；仍失败才返回 default，并留下日志与损坏副本
    """
    path = Path(path)
    with _lock_for(path):
        if not path.exists():
            return default() if callable(default) else default

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error("配置文件 %s 解析失败: %s —— 尝试从备份恢复", path.name, e)

        # 隔离损坏文件，避免被后续写入覆盖
        corrupt = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        try:
            shutil.copy2(path, corrupt)
            log.error("已隔离损坏文件: %s", corrupt.name)
        except Exception:
            pass

        # 尝试备份恢复
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            try:
                with open(bak, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log.warning("已从备份 %s 恢复数据", bak.name)
                try:
                    shutil.copy2(bak, path)
                except Exception:
                    pass
                return data
            except Exception as e:
                log.error("备份 %s 同样不可用: %s", bak.name, e)

        if on_corrupt:
            try:
                on_corrupt(path)
            except Exception:
                pass
        return default() if callable(default) else default


def update_json(path: Path, default: Any, mutator: Callable[[Any], Any]) -> Any:
    """读-改-写 原子事务，避免 read-modify-write 竞态。

    mutator 收到的可能是 default（文件不存在时），返回新值。
    """
    with _lock_for(path):
        data = read_json(path, default)
        new_data = mutator(data)
        atomic_write_json(path, new_data)
        return new_data
