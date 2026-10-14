# -*- coding: utf-8 -*-
"""候选 RSS 源探测：找出能用的、并且看哪些带全文（content:encoded）。

用法：
    python tools/probe_feeds.py
"""
from __future__ import annotations

import socket
import sys

import feedparser

socket.setdefaulttimeout(15)  # 避免某个源挂死拖垮整轮探测
UA = {"User-Agent": "Mozilla/5.0 (compatible; EnglishDailyBot/1.0)"}

CANDIDATES: dict[str, str] = {
    # 当前内置
    "bbc-world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "wapo-world(old)": "https://feeds.washingtonpost.com/rss/world",
    "reuters(old)": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    # 候选：WaPo
    "wapo-rss": "https://www.washingtonpost.com/rss/world",
    "wapo-national": "https://feeds.washingtonpost.com/rss/national",
    "wapo-politics": "https://feeds.washingtonpost.com/rss/politics",
    # 候选：其他权威英美媒体
    "times-world": "https://www.thetimes.co.uk/rss/world",
    "times-news": "https://www.thetimes.co.uk/rss/news",
    "telegraph": "https://www.telegraph.co.uk/news/rss.xml",
    "guardian-world": "https://www.theguardian.com/world/rss",
    "guardian-intl": "https://www.theguardian.com/international/rss",
    "independent": "https://www.independent.co.uk/news/world/rss",
    "npr-world": "https://feeds.npr.org/1004/rss.xml",
    "ap-topnews": "https://rsshub.app/apnews/topics/apf-topnews",
    "economist": "https://www.economist.com/international/rss.xml",
    "time-world": "https://time.com/section/world/feed/",
    "cnn-world": "http://rss.cnn.com/rss/edition_world.rss",
}


def main() -> int:
    print("=" * 100)
    print(f"{'源':18s} {'HTTP':>5s} {'条目':>4s} {'摘要最长':>8s} {'摘要>=120':>9s} {'带全文':>7s} {'全文最长':>8s}")
    print("=" * 100)
    for name, url in CANDIDATES.items():
        try:
            d = feedparser.parse(url, request_headers=UA)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:18s} 异常 {exc}")
            continue
        entries = getattr(d, "entries", []) or []
        status = getattr(d, "status", "?")

        import re

        def clean(t: str) -> str:
            t = re.sub(r"<[^>]+>", " ", t or "")
            return re.sub(r"\s{2,}", " ", t).strip()

        slens = [len(clean(e.get("summary") or "")) for e in entries]
        ok120 = sum(1 for x in slens if x >= 120)

        full_lens = []
        for e in entries:
            c = e.get("content") or []
            if c:
                full_lens.append(len(clean(c[0].get("value") or "")))
        has_full = "是" if full_lens else "否"
        full_max = max(full_lens) if full_lens else 0

        print(
            f"{name:18s} {str(status):>5s} {len(entries):>4d} "
            f"{max(slens) if slens else 0:>8d} {ok120:>9d} {has_full:>7s} {full_max:>8d}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
