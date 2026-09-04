"""Resolve generated artifact folders (absolute paths, folder name, or mixed slashes)."""
from pathlib import Path
from typing import List, Optional


def resolve_under_roots(task_dir: str, roots: List[Path]) -> Optional[Path]:
    if not task_dir or not str(task_dir).strip():
        return None
    raw = str(task_dir).strip().strip('"')
    norm = raw.replace("/", "\\")

    # 1) Folder name only -> look under each root
    name = Path(norm).name
    for root in roots:
        if not root:
            continue
        try:
            br = root.resolve()
        except Exception:
            br = root
        cand = (br / name)
        if cand.is_dir():
            return cand

    # 2) Full path as given
    p = Path(norm)
    try:
        if p.is_dir():
            pr = p.resolve()
            for root in roots:
                try:
                    br = root.resolve()
                    pr.relative_to(br)
                    return pr
                except ValueError:
                    continue
            return pr
    except Exception:
        pass

    return None
