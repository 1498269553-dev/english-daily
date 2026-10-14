# -*- coding: utf-8 -*-
"""B 站数据源。

实测结论（2026-10-14 多次验证）：
  · /x/web-interface/view       免登录可用，是唯一稳定的详情来源
  · /x/space/wbi/arc/search    需 WBI 签名，间歇可用（412/-352/799 都遇到过）
  · /x/polymer/web-dynamic/... 持续 412，实测基本不可用
  · /x/web-interface/search    免登录可用，可作 UP 主名 -> mid 的解析

策略：投稿列表只负责「发现有哪些视频」，详情一律走 view 接口；
所有路径失败都不抛异常，返回空列表交由上层判定「今日暂无新素材」。
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

log = logging.getLogger(__name__)

# 前端硬编码的 mixinKeyEncTab，约 2-4 周轮换一次，需每次从 nav 重新取密钥
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


@dataclass
class BiliItem:
    """一条归一化后的内容（视频或动态）。"""

    bvid: str = ""
    title: str = ""
    text: str = ""
    url: str = ""
    pub_ts: int = 0
    author: str = ""
    kind: str = "video"  # video | dynamic
    cover: str = ""
    duration: int = 0

    @property
    def pub_dt(self) -> datetime:
        return datetime.fromtimestamp(self.pub_ts, tz=timezone.utc)

    def is_recent(self, days: int, tz_offset: int) -> bool:
        if self.pub_ts <= 0:
            # 发布时间缺失时保守判定为「不新」，否则 1970 年的时间戳会被误判
            return False
        tz = timezone(timedelta(hours=tz_offset))
        now = datetime.now(tz)
        return (now - self.pub_dt.astimezone(tz)) <= timedelta(days=days)


@dataclass
class Fetcher:
    cookie: str = ""
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    timeout: int = 20
    # 请求节流：两次请求之间的最小间隔（秒）+ 随机抖动上限。
    # GitHub Actions 的 runner 是数据中心 IP，对高频请求比家用 IP 敏感得多，
    # 固定频率的密集请求很容易被识别为机器行为，因此必须带随机化。
    min_interval: float = 1.5
    jitter: float = 0.8

    _session: requests.Session = field(default_factory=requests.Session, init=False)
    _mixin_key: str | None = field(default=None, init=False)
    _last_request_at: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        if self.cookie:
            self._session.headers["Cookie"] = self.cookie
            log.info("已加载 B 站 Cookie（%d 字符）", len(self.cookie))
        else:
            log.warning("未配置 BILI_COOKIE：请求成功率会明显下降，建议配置")

    # ---------- 底层 ----------

    def _throttle(self) -> None:
        """请求节流：保证两次请求之间有随机间隔，避免被识别为机器行为。"""
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval + random.uniform(0, self.jitter) - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _get(self, url: str, referer: str) -> requests.Response:
        self._throttle()
        self._session.headers["Referer"] = referer
        return self._session.get(url, timeout=self.timeout)

    def _json(
        self, url: str, referer: str, allow_codes: set[int] | None = None
    ) -> dict[str, Any] | None:
        try:
            r = self._get(url, referer)
            if r.status_code != 200:
                log.warning("HTTP %s %s", r.status_code, url)
                return None
            data = r.json()
            allowed = allow_codes or set()
            if data.get("code") != 0 and data.get("code") not in allowed:
                log.warning("接口返回 code=%s message=%s", data.get("code"), data.get("message"))
                return None
            return data.get("data")
        except Exception as exc:  # noqa: BLE001 - 网络层任何异常都不应中断主流程
            log.warning("请求失败 %s: %s", url, exc)
            return None

    # ---------- WBI ----------

    def _get_mixin_key(self) -> str | None:
        if self._mixin_key:
            return self._mixin_key
        # nav 在未登录时返回 code=-101，但 wbi_img 字段依然可用，这里不能按失败处理
        data = self._json(
            "https://api.bilibili.com/x/web-interface/nav",
            "https://www.bilibili.com/",
            allow_codes={-101},
        )
        if not data:
            return None
        wbi = data.get("wbi_img") or {}
        img = (wbi.get("img_url") or "").rsplit("/", 1)[-1].split(".")[0]
        sub = (wbi.get("sub_url") or "").rsplit("/", 1)[-1].split(".")[0]
        if not img or not sub:
            return None
        self._mixin_key = "".join((img + sub)[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        return self._mixin_key

    def _wbi_sign(self, params: dict[str, Any]) -> str | None:
        key = self._get_mixin_key()
        if not key:
            return None
        params = {**params, "wts": int(time.time())}
        # 官方实现会剔除 value 中的 !'()* 并对值做 URL 编码
        cleaned = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in params.items()}
        query = urllib.parse.urlencode(sorted(cleaned.items()))
        params["w_rid"] = hashlib.md5((query + key).encode()).hexdigest()
        return urllib.parse.urlencode(sorted(params.items()))

    # ---------- 对外 ----------

    def resolve_mid(self, keyword: str) -> str | None:
        """UP 主名 -> mid，仅在 config 里没填 mid 时使用。"""
        if keyword.isdigit():
            return keyword
        url = (
            "https://api.bilibili.com/x/web-interface/search/type?"
            + urllib.parse.urlencode({"search_type": "bili_user", "keyword": keyword})
        )
        data = self._json(url, "https://search.bilibili.com/")
        items = (data or {}).get("result") or []
        if not items:
            return None
        # 优先精确匹配昵称
        for it in items:
            if (it.get("uname") or "").strip().lower() == keyword.strip().lower():
                return str(it.get("mid"))
        return str(items[0].get("mid"))

    def fetch_latest(
        self,
        mid: str,
        days: int,
        tz_offset: int,
        known: set[str] | None = None,
        backfill_days: int | None = None,
    ) -> list[BiliItem]:
        """取该 UP 主的内容，按发布时间倒序。

        known 是本地已推送 / 已入基线的 bvid 集合。传入后走「游标翻页」：
        从最新一页往前翻，遇到已知的 bvid 就停——按 pubdate 排序，后面的必然
        全是历史内容，不必深翻。稳态下每次只请求 1-2 页。

        backfill_days 传入且 known 为空时（首次运行）额外开启「全量回溯」：
        用更宽的时间窗一直翻到底，把该 UP 主从最早一期到现在的全部视频
        纳入基线。基线只作游标锚点，不会被推送。
        """
        items: list[BiliItem] = []
        seen: set[str] = set()
        known = known or set()

        first_run = not known and bool(backfill_days)
        window = backfill_days if first_run else days

        for item in self._fetch_dynamic(mid):
            if item.bvid not in seen and item.is_recent(window, tz_offset):
                seen.add(item.bvid)
                items.append(item)

        max_pages = 30 if first_run else 10
        items.extend(self._fetch_videos_cursor(mid, window, tz_offset, known, seen, max_pages))

        if first_run:
            log.info("首次运行：已回溯 %d 天内的全部内容，共 %d 条", window, len(items))

        items.sort(key=lambda x: x.pub_ts, reverse=True)
        return items

    def _fetch_videos_cursor(
        self,
        mid: str,
        days: int,
        tz_offset: int,
        known: set[str],
        seen: set[str],
        max_pages: int = 10,
        page_size: int = 30,
    ) -> list[BiliItem]:
        """游标翻页：从最新往历史翻，遇到已推送/已入基线的就停。"""
        out: list[BiliItem] = []
        for pn in range(1, max_pages + 1):
            items = self._fetch_video_page(mid, pn, page_size)
            if not items:
                break  # 拿不到数据（到底了或被风控），交由上层降级
            hit_known = False
            page_has_recent = False
            for item in items:
                if item.bvid in seen:
                    continue
                seen.add(item.bvid)
                if item.bvid in known:
                    hit_known = True
                    continue
                if item.is_recent(days, tz_offset):
                    page_has_recent = True
                    out.append(item)
            if hit_known:
                # 已遇到历史内容，后续页必然也是旧的，停在这里
                log.info("第 %d 页遇到已推送内容，游标停止", pn)
                break
            if not page_has_recent:
                # 整页都超出时间窗口，更早的只会更旧
                log.info("第 %d 页已超出时间窗口，停止翻页", pn)
                break
            if len(items) < page_size:
                break  # 最后一页
        return out

    def _fetch_video_page(
        self, mid: str, pn: int, page_size: int = 30, retries: int = 2
    ) -> list[BiliItem]:
        """取投稿列表第 pn 页，并用 view 接口补全详情。

        WBI 接口成功率波动大，412 属 IP 层风控，短间隔重试无效，
        因此退避拉长，并在每次重试前重新拉取可能已轮换的密钥。
        """
        data = None
        for attempt in range(retries + 1):
            qs = self._wbi_sign(
                {
                    "mid": mid,
                    "ps": page_size,
                    "pn": pn,
                    "order": "pubdate",
                    "platform": "web",
                }
            )
            if not qs:
                return []
            url = f"https://api.bilibili.com/x/space/wbi/arc/search?{qs}"
            data = self._json(url, f"https://space.bilibili.com/{mid}/video")
            if data:
                break
            if attempt < retries:
                delay = 8 * (attempt + 1)
                log.info("投稿列表第 %d 页被拒，%d 秒后重试（%d/%d）", pn, delay, attempt + 1, retries)
                time.sleep(delay)
                self._mixin_key = None  # 密钥可能已轮换
        if not data:
            return []

        vlist = ((data.get("list") or {}).get("vlist")) or []
        out: list[BiliItem] = []
        for v in vlist:
            bvid = v.get("bvid") or ""
            if not bvid:
                continue
            out.append(
                BiliItem(
                    bvid=bvid,
                    title=v.get("title") or "",
                    text=(v.get("description") or "").strip(),
                    url=f"https://www.bilibili.com/video/{bvid}",
                    pub_ts=int(v.get("pubdate") or 0),
                    author=(v.get("author") or ""),
                    kind="video",
                    cover=(v.get("pic") or "").replace("http://", "https://"),
                )
            )

        # vlist 的 pubdate/description 常被精简甚至置 0，view 接口才给完整值。
        # 串行补全（实测并发会瞬时打出几十个请求，极易触发风控），
        # 且只补列表里真正缺字段的条目，避免无谓请求。
        for item in out:
            if item.pub_ts > 0 and len(item.text) >= 120 and item.duration > 0:
                continue
            detail = self.fetch_detail(item.bvid)
            if not detail:
                continue
            item.pub_ts = int(detail.get("pubdate") or item.pub_ts)
            item.duration = int(detail.get("duration") or 0)
            item.author = (detail.get("owner") or {}).get("name") or item.author
            desc = (detail.get("desc") or "").strip()
            if len(desc) > len(item.text):
                item.text = desc
        return out

    def _fetch_dynamic(self, mid: str) -> list[BiliItem]:
        url = (
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?"
            + urllib.parse.urlencode({"host_mid": mid, "offset": "", "features": "itemOpusStyle"})
        )
        data = self._json(url, f"https://space.bilibili.com/{mid}/dynamic")
        if not data:
            return []
        out: list[BiliItem] = []
        for it in data.get("items") or []:
            try:
                mods = it.get("modules") or {}
                author = ((mods.get("module_author") or {}).get("name")) or ""
                pub_ts = int((mods.get("module_author") or {}).get("pub_ts") or 0)
                major = ((mods.get("module_dynamic") or {}).get("major")) or {}
                dyn_type = (mods.get("module_dynamic") or {}).get("type") or ""
                bvid = title = text = cover = ""
                if dyn_type == "MAJOR_TYPE_ARCHIVE" and major.get("archive"):
                    a = major["archive"]
                    bvid = a.get("bvid") or ""
                    title = a.get("title") or ""
                    cover = a.get("cover") or ""
                elif dyn_type == "MAJOR_TYPE_OPUS" and major.get("opus"):
                    o = major["opus"]
                    title = (o.get("title") or {}).get("text") or ""
                    text = (o.get("summary") or {}).get("text") or ""
                    cover = ((o.get("pic") or {}).get("url")) or ""
                else:
                    desc = major.get("desc") or ""
                    text = desc if isinstance(desc, str) else ""
                    bvid = f"dynamic-{it.get('id_str', '')}"
                    title = text[:40]
                if not pub_ts:
                    continue
                desc = (mods.get("module_dynamic") or {}).get("desc") or {}
                desc_text = (desc.get("text") or "") if isinstance(desc, dict) else str(desc)
                out.append(
                    BiliItem(
                        bvid=bvid,
                        title=title,
                        text="\n".join(x for x in (desc_text, text) if x).strip(),
                        url=(
                            f"https://www.bilibili.com/video/{bvid}"
                            if bvid.startswith("BV")
                            else f"https://t.bilibili.com/{it.get('id_str', '')}"
                        ),
                        pub_ts=pub_ts,
                        author=author,
                        kind="video" if bvid.startswith("BV") else "dynamic",
                        cover=cover,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("动态条目解析失败: %s", exc)
                continue
        return out

    def fetch_detail(self, bvid: str) -> dict[str, Any] | None:
        """view 接口免登录可用，是本项目唯一稳定的取详情通道。

        实测：动态接口与 WBI 投稿列表都会间歇性 412/-352，
        而 view 接口始终可用，且 pubdate / duration / desc 都比 vlist 完整。
        """
        if not bvid.startswith("BV"):
            return None
        return self._json(
            "https://api.bilibili.com/x/web-interface/view?bvid=" + bvid,
            f"https://www.bilibili.com/video/{bvid}",
        )