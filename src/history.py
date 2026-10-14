# -*- coding: utf-8 -*-
"""UP 主历史视频清单：翻页拉全量，按发布时间排序落盘。

用途：
  1. 初始化时把 UP 主的历史视频清单拉一遍，看清有哪些素材、覆盖哪些时间段
  2. 排查问题时确认某个 bvid 是否被正确抓到

用法：
  python src/history.py                      # 拉取并输出
  python src/history.py --mid xxx --out data/xxx.json
  python src/history.py --list              # 查看已保存的清单
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bili import BiliItem, Fetcher  # noqa: E402
from src.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fetch_all(
    mid: str,
    max_pages: int = 20,
    page_size: int = 30,
    gap: float = 3.0,
    max_empty: int = 4,
    min_interval: float = 2.0,
) -> list[BiliItem]:
    """翻页拉全量。

    风控是常态而非例外：实测同一 IP 短时间内可能连续多页被拒，
    且 view 接口的串行补详情本身就是上百次请求。因此：
      - 每次请求之间有 2~3 秒随机间隔（比主流程更保守）
      - 单页失败时指数退避重试，只有连续 max_empty 页彻底拿不到才判定到底
    """
    cfg = load_config()
    f = Fetcher(
        cookie=cfg.bili_cookie,
        user_agent=cfg.bili_user_agent,
        min_interval=min_interval,
        jitter=1.0,
    )
    if cfg.bili_cookie:
        print("  已加载 BILI_COOKIE")
    else:
        print("  ⚠ 未加载 BILI_COOKIE，成功率会明显下降")
    out: list[BiliItem] = []
    seen: set[str] = set()
    empty_streak = 0

    for pn in range(1, max_pages + 1):
        page: list[BiliItem] = []
        for attempt in range(4):
            page = f._fetch_video_page(mid, pn, page_size)
            if page:
                break
            delay = gap * (2**attempt)  # 3s, 6s, 12s, 24s
            print(f"  第 {pn} 页被拒，{delay:.0f} 秒后重试（{attempt + 1}/4）")
            time.sleep(delay)

        if not page:
            empty_streak += 1
            print(f"  第 {pn} 页: 空（连续 {empty_streak} 次）")
            if empty_streak >= max_empty:
                print("  连续多页无数据，判定为已到底或被全面风控")
                break
            continue

        empty_streak = 0
        new = [x for x in page if x.bvid not in seen]
        for x in new:
            seen.add(x.bvid)
        out.extend(new)
        print(f"  第 {pn} 页: {len(page)} 条（累计 {len(out)}）")
        if len(page) < page_size:
            print("  不满一页，判定为最后一页")
            break
        time.sleep(gap)
    return out


def to_records(items: list[BiliItem], tz_offset: int = 8) -> list[dict]:
    tz = timezone(timedelta(hours=tz_offset))
    rows = []
    for it in items:
        dt = datetime.fromtimestamp(it.pub_ts, tz) if it.pub_ts > 0 else None
        rows.append(
            {
                "date": dt.strftime("%Y-%m-%d") if dt else "",
                "datetime": dt.strftime("%Y-%m-%d %H:%M") if dt else "",
                "bvid": it.bvid,
                "duration_min": round(it.duration / 60, 1),
                "title": it.title,
                "author": it.author,
                "url": it.url,
            }
        )
    rows.sort(key=lambda r: (r["datetime"] or "", r["bvid"]))
    return rows


def print_table(rows: list[dict]) -> None:
    if not rows:
        print("（空）")
        return
    print(f"\n共 {len(rows)} 条\n")
    print(f"{'序号':>3}  {'发布日期':<12} {'时长':>6}  标题")
    print("-" * 78)
    for i, r in enumerate(rows, 1):
        dur = f"{r['duration_min']:.0f}分钟" if r["duration_min"] else "-"
        print(f"{i:>3}  {r['date'] or '(未知)':<12} {dur:>6}  {r['title'][:38]}")

    dates = [r["date"] for r in rows if r["date"]]
    if dates:
        print("-" * 78)
        print(f"时间跨度：{dates[0]} → {dates[-1]}")

        from collections import Counter

        c = Counter(d[:7] for d in dates)
        print("\n按月分布：")
        for k in sorted(c):
            bar = "█" * c[k]
            print(f"  {k}  {c[k]:>2} 条  {bar}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", help="UP 主 mid")
    ap.add_argument("--name", default="", help="UP 主昵称，仅用于输出")
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--out", help="清单输出路径，默认 data/history_<mid>.json")
    ap.add_argument("--list", action="store_true", help="查看已保存的清单而不重新抓取")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("src.bili").setLevel(logging.ERROR)  # 减少风控噪音

    if args.list:
        files = sorted(DATA.glob("history_*.json"))
        if not files:
            print("data/ 下还没有清单，先跑一次抓取")
            return 1
        for p in files:
            data = json.loads(p.read_text(encoding="utf-8"))
            print(f"\n=== {p.name}  ({data.get('name') or data.get('mid')}) ===")
            print_table(data.get("items") or [])
        return 0

    if not args.mid:
        print("需要 --mid 参数，或用 --list 查看已有清单")
        return 1

    print(f"正在拉取 {args.name or args.mid} 的历史视频清单……")
    items = fetch_all(args.mid, args.max_pages)
    if not items:
        print()
        print("未抓到任何视频。WBI 投稿列表接口当前被风控是常见现象，建议：")
        print("  1. 配置 BILI_COOKIE（浏览器登录 B 站后从 DevTools 复制）")
        print("  2. 放到 GitHub Actions 上跑（runner 是海外 IP）")
        print("  3. 过一段时间重试，IP 风控通常会随时间解除")
        return 2

    rows = to_records(items)
    print_table(rows)

    DATA.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else DATA / f"history_{args.mid}.json"
    out.write_text(
        json.dumps(
            {
                "mid": args.mid,
                "name": args.name,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(rows),
                "items": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n清单已保存：{out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())