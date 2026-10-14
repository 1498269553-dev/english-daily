# -*- coding: utf-8 -*-
"""兜底素材源：英美权威媒体。

优先级：
  1. Guardian Open Platform API（有 key 时启用，免费 500 次/天，含 bodyText 全文）
  2. 各家官方 RSS —— 零配置、零 key。
     ⚠️ 实测（2026-10-14）：RSS 的 <description> 长度差异极大。
        Guardian 的 RSS 描述带近全文（实测 1800~1950 字符，非常适合作精读素材），
        BBC / NYT / FT 只有 150~220 字符的导语，CNN / Independent 居中。
        因此这里把 Guardian 放在最前，并优先挑「长描述」的条目；
        短描述条目仍可用，但正文由 LLM 基于导语合理扩写，文末会标注说明。

历史教训：早期版本要求 summary >= 300 字符才算合格，结果 **所有 RSS 源被打光**
（BBC 最长 181、NYT 最长 217、FT 最长 173），首次部署直接以 exit code 3 失败。
现在阈值降到 120，并且区分「近全文」与「仅导语」两档，不再一刀切。
"""
from __future__ import annotations

import logging
import random
import re
import socket
from dataclasses import dataclass
from typing import Any

import feedparser
import requests

log = logging.getLogger(__name__)

# 顺序即优先级：越靠前越先被探测，也越可能被选中。
DEFAULT_FEEDS: dict[str, str] = {
    # ---- 一档：RSS 自带近全文，素材质量最好 ----
    "guardian-intl": "https://www.theguardian.com/international/rss",
    "guardian-world": "https://www.theguardian.com/world/rss",
    # ---- 二档：正文需 LLM 扩写，但来源权威且稳定 ----
    "bbc-world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc-business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc-science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "nyt-world": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "nyt-tech": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "cnn-world": "http://rss.cnn.com/rss/edition_world.rss",
    "independent-world": "https://www.independent.co.uk/news/world/rss",
    "telegraph-news": "https://www.telegraph.co.uk/news/rss.xml",
    "npr-world": "https://feeds.npr.org/1004/rss.xml",
    "ft-world": "https://www.ft.com/world?format=rss",
    # ---- 三档：2026-10 实测失效，保留以便自行恢复；探测成本低，放最后 ----
    #   wapo 返回 502（疑似对部分网络/机房 IP 做了拦截）
    #   times / reuters 返回 301，RSS 已下线
    "wapo-world": "https://feeds.washingtonpost.com/rss/world",
    "times-world": "https://www.thetimes.co.uk/rss/world",
    "reuters-world": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
}

# 学习价值偏低、容易踩雷的分类直接不采
BLOCK_KEYWORDS = {
    "horoscope", "puzzle", "crossword", "recipe", "deaths", "obituary",
    "celebrity", "royal family", "kardashian", "nfl", "nba", "nhl",
    "tv review", "film review", "shopping", "deals of the day",
}

MIN_SUMMARY = 120    # 低于这个长度连导语都不完整，做不了学习材料
RICH_SUMMARY = 600   # 达到这个长度视为「近全文」，优先选用
MAX_SOURCES = 8      # 最多探测这么多个源，避免 Actions 上耗时失控
ENOUGH_RICH = 6      # 攒够这么多条近全文就立即停手


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: str = ""
    summary: str = ""
    body: str = ""
    kind: str = "rss"  # rss | guardian


@dataclass
class NewsFetcher:
    guardian_key: str = ""
    sources: list[str] | None = None
    timeout: int = 20
    seed: int | None = None

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": "Mozilla/5.0 (compatible; EnglishDailyBot/1.0)"}

    def pick(self) -> Article | None:
        """随机挑一篇。先试 Guardian（有 key），失败或无 key 则走 RSS 池。"""
        return self.pick_with_seed(self.seed)

    def pick_with_seed(self, seed: int | None) -> Article | None:
        """按指定随机种子挑一篇——调用方换种子即可拿到不同结果。"""
        rng = random.Random(seed)
        attempts: list[Article] = []
        if self.guardian_key:
            g = self._from_guardian()
            if g:
                attempts.extend(g)
        rss = self._from_rss()
        attempts.extend(rss)
        if not attempts:
            log.error("所有兜底源均无数据")
            return None
        art = rng.choice(attempts)
        log.info(
            "兜底选中：%s（%s，材料 %d 字符）",
            art.title[:60],
            art.source,
            len(art.body or art.summary),
        )
        return art

    # ---------- Guardian ----------

    def _from_guardian(self) -> list[Article]:
        url = (
            "https://content.guardianapis.com/search?"
            + f"api-key={self.guardian_key}"
            + "&order-by=newest&page-size=20&show-fields=bodyText,trailText,byline"
            + "&production-office=news&exclude-fields=headline,thumbnail"
        )
        try:
            r = requests.get(url, headers=self._headers(), timeout=self.timeout)
            if r.status_code != 200:
                log.warning("Guardian HTTP %s", r.status_code)
                return []
            results = r.json().get("response", {}).get("results", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("Guardian 请求失败: %s", exc)
            return []

        out: list[Article] = []
        for it in results:
            fields = it.get("fields") or {}
            body = fields.get("bodyText") or ""
            title = it.get("webTitle") or ""
            if not body or len(body) < RICH_SUMMARY:
                continue  # 太短的做不了学习材料
            if self._blocked(title) or self._blocked(body[:400]):
                continue
            out.append(
                Article(
                    title=title,
                    url=it.get("webUrl") or "",
                    source="The Guardian",
                    published=it.get("webPublicationDate") or "",
                    summary=(fields.get("trailText") or "").strip(),
                    body=self._clean(body),
                    kind="guardian",
                )
            )
        if not out:
            log.warning("Guardian API 返回了结果，但没有长度达标的条目")
        return out

    # ---------- RSS ----------

    def _from_rss(self) -> list[Article]:
        names = list(self.sources or DEFAULT_FEEDS)
        rng = random.Random(self.seed)
        # 不打乱顺序：DEFAULT_FEEDS 的顺序就是质量优先级，好东西在前面先探到就停。
        # 只有同一档内（都长/都短）才用 rng 决定挑哪条，避免风格忽长忽短。

        socket.setdefaulttimeout(self.timeout)  # 防止某个挂死的源拖住整个工作流

        rich: list[Article] = []
        thin: list[Article] = []
        for name in names[:MAX_SOURCES]:
            url = DEFAULT_FEEDS.get(name, name)  # 允许直接填 URL
            try:
                d = feedparser.parse(url, request_headers=self._headers())
            except Exception as exc:  # noqa: BLE001
                log.warning("RSS 解析失败 %s: %s", name, exc)
                continue
            entries = getattr(d, "entries", []) or []
            if not entries:
                log.warning("RSS 无条目 %s（HTTP %s）", name, getattr(d, "status", "?"))
                continue

            label = self._pretty(name)
            n_rich = n_thin = 0
            for e in entries:
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                summary = self._clean(e.get("summary") or "")
                # RSS 有时把全文塞在 content:encoded 里，优先用它
                for c in e.get("content") or []:
                    val = self._clean(c.get("value") or "")
                    if len(val) > len(summary):
                        summary = val
                if not title or not link:
                    continue
                if len(summary) < MIN_SUMMARY:
                    continue
                if self._blocked(title) or self._blocked(summary[:200]):
                    continue
                art = Article(
                    title=title,
                    url=link,
                    source=label,
                    published=e.get("published", ""),
                    summary=summary,
                    kind="rss",
                )
                if len(summary) >= RICH_SUMMARY:
                    rich.append(art)
                    n_rich += 1
                else:
                    thin.append(art)
                    n_thin += 1
            log.info("RSS %-18s 可用：近全文 %d 条 / 仅导语 %d 条", name, n_rich, n_thin)
            if len(rich) >= ENOUGH_RICH:
                break

        # 有近全文就只用近全文，绝不因为源较少而退回几百字符的导语
        pool = rich or thin
        if not pool:
            log.error("RSS 池为空：所有源都没有长度 >= %d 的描述", MIN_SUMMARY)
        rng.shuffle(pool)
        return pool

    # ---------- 工具 ----------

    @staticmethod
    def _pretty(name: str) -> str:
        return {
            "guardian-intl": "The Guardian",
            "guardian-world": "The Guardian (World)",
            "bbc-world": "BBC News",
            "bbc-business": "BBC Business",
            "bbc-science": "BBC Science",
            "nyt-world": "The New York Times",
            "nyt-tech": "The New York Times (Tech)",
            "cnn-world": "CNN",
            "independent-world": "The Independent",
            "telegraph-news": "The Telegraph",
            "npr-world": "NPR",
            "wapo-world": "The Washington Post",
            "ft-world": "Financial Times",
            "times-world": "The Times",
            "reuters-world": "Reuters",
        }.get(name, name)

    @staticmethod
    def _blocked(text: str) -> bool:
        low = (text or "").lower()
        return any(k in low for k in BLOCK_KEYWORDS)

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text or "")
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
        text = text.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&hellip;", "…").replace("&#8230;", "…")
        return re.sub(r"\s{2,}", " ", text).strip()
