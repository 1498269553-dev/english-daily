# -*- coding: utf-8 -*-
"""运行状态：已推送内容 + 历史基线，避免重复推送与重复全量扫描。

state.json 结构：
{
  "pushed": ["BV...", ...],            # 已推送，按时间倒序，最多 60 条
  "baseline": {"<mid>": ["BV...", ...]},  # 首次回溯建立的历史基线（不推送，只作游标锚点）
  "last_run": "...",
  "last_bvid": "..."
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "state.json"


def load() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"pushed": [], "baseline": {}, "last_run": None, "last_bvid": None}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pushed": [], "baseline": {}, "last_run": None, "last_bvid": None}
    data.setdefault("pushed", [])
    data.setdefault("baseline", {})
    return data


def save(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def already_pushed(bvid: str) -> bool:
    return bvid in (load().get("pushed") or [])


def known_bvids(mid: str = "") -> set[str]:
    """已推送 + 对应 UP 主的历史基线。

    两者合并作为游标翻页的「已知锚点」：翻页时遇到其中任一即停止。
    """
    st = load()
    out = set(st.get("pushed") or [])
    if mid:
        out |= set((st.get("baseline") or {}).get(mid) or [])
    return out


def record(bvid: str, keep: int = 60) -> None:
    st = load()
    pushed = [x for x in (st.get("pushed") or []) if x != bvid]
    pushed.insert(0, bvid)
    st["pushed"] = pushed[:keep]
    st["last_bvid"] = bvid
    save(st)


def record_baseline(mid: str, bvids: set[str], keep: int = 500) -> None:
    """登记某个 UP 主的历史基线（不推送，仅作游标锚点）。"""
    st = load()
    baseline = st.setdefault("baseline", {})
    merged = list(bvids) + [x for x in (baseline.get(mid) or []) if x not in bvids]
    baseline[mid] = merged[:keep]
    save(st)