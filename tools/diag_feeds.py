# -*- coding: utf-8 -*-
"""兜底源体检：逐个 RSS 抓一遍，看看到底是哪一步把素材全过滤掉了。

用法：
    python tools/diag_feeds.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # noqa: E402

from src.news import (  # noqa: E402
    DEFAULT_FEEDS,
    MIN_SUMMARY,
    RICH_SUMMARY,
    NewsFetcher,
)

UA = {"User-Agent": "Mozilla/5.0 (compatible; EnglishDailyBot/1.0)"}


def main() -> int:
    print("=" * 88)
    print(f"逐个 RSS 体检（门槛：近全文 >= {RICH_SUMMARY}，可用 >= {MIN_SUMMARY}）")
    print("=" * 88)
    total_rich = total_ok = 0
    for name, url in DEFAULT_FEEDS.items():
        try:
            d = feedparser.parse(url, request_headers=UA)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:18s} 解析异常: {exc}")
            continue
        entries = getattr(d, "entries", []) or []
        status = getattr(d, "status", "?")
        lengths, rich, ok = [], 0, 0
        for e in entries:
            s = NewsFetcher._clean(e.get("summary") or "")
            for c in e.get("content") or []:
                val = NewsFetcher._clean(c.get("value") or "")
                if len(val) > len(s):
                    s = val
            lengths.append(len(s))
            if len(s) >= RICH_SUMMARY:
                rich += 1
            if len(s) >= MIN_SUMMARY and not NewsFetcher._blocked(e.get("title") or ""):
                ok += 1
        total_rich += rich
        total_ok += ok
        mx = max(lengths) if lengths else 0
        avg = int(sum(lengths) / len(lengths)) if lengths else 0
        flag = "OK " if rich else ("~  " if ok else "XX ")
        print(
            f"{flag}{name:18s} HTTP={str(status):4s} 条目={len(entries):3d} "
            f"最长={mx:4d} 平均={avg:4d} 近全文={rich:3d} 可用={ok:3d}"
        )
    print("-" * 88)
    print(f"近全文素材合计 {total_rich} 条；可用素材合计 {total_ok} 条")
    if total_rich == 0:
        print(">>> 一条近全文都没有，素材质量会明显下降（但仍可用导语扩写）。")
    if total_ok == 0:
        print(">>> 这就是 exit code 3 的原因：兜底源一条都没过筛。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
