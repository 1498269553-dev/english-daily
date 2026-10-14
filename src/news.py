# -*- coding: utf-8 -*-
"""兜底素材源：英美权威媒体。

优先级：
  1. Guardian Open Platform API（有 key 时启用，免费 500 次/天，含 bodyText 全文）
  2. 各家官方 RSS（BBC / NYT / WaPo / FT / Reuters ...）—— 零配置、零 key
RSS 只能拿到标题+摘要，正文靠 LLM 基于摘要扩写并在文末标注「原文需订阅查看」；
Guardian API 能拿到全文，效果最好。
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

import feedparser
import requests

log = logging.getLogger(__name__)

DEFAULT_FEEDS: dict[str, str] = {
    "bbc-world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc-business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc-science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "nyt-world": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "nyt-tech": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "wapo-world": "https://feeds.washingtonpost.com/rss/world",
    "ft-world": "https://www.ft.com/world?format=rss",
    "reuters-world": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
}

# 学习价值偏低、容易踩雷的分类直接不采
BLOCK_KEYWORDS = {
    "horoscope", "puzzle", "crossword", "recipe", "deaths", "obituary",
    "celebrity", "royal family", "kardashian", "nfl", "nba", "nhl",
    "tv review", "film review", "shopping", "deals of the day",
}


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
        rng = random.Random(self.seed)
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
        return rng.choice(attempts)

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
            if not body or len(body) < 800:
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
        return out

    # ---------- RSS ----------

    def _from_rss(self) -> list[Article]:
        names = self.sources or list(DEFAULT_FEEDS)
        rng = random.Random(self.seed)
        rng.shuffle(names)
        out: list[Article] = []
        for name in names:
            url = DEFAULT_FEEDS.get(name, name)  # 允许直接填 URL
            try:
                d = feedparser.parse(url)
            except Exception as exc:  # noqa: BLE001
                log.warning("RSS 解析失败 %s: %s", name, exc)
                continue
            entries = getattr(d, "entries", []) or []
            if not entries:
                log.warning("RSS 无条目: %s", name)
                continue
            label = self._pretty(name)
            for e in entries[:8]:
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                summary = self._clean(e.get("summary") or "")
                if not title or not link:
                    continue
                if len(summary) < 300:
                    continue
                if self._blocked(title):
                    continue
                out.append(
                    Article(
                        title=title,
                        url=link,
                        source=label,
                        published=e.get("published", ""),
                        summary=summary,
                        kind="rss",
                    )
                )
            if out:
                break  # 拿到一个源的可用条目就够，跨源混合会降低风格一致性
        return out

    # ---------- 工具 ----------

    @staticmethod
    def _pretty(name: str) -> str:
        return {
            "bbc-world": "BBC News",
            "bbc-business": "BBC Business",
            "bbc-science": "BBC Science",
            "nyt-world": "The New York Times",
            "nyt-tech": "The New York Times (Tech)",
            "wapo-world": "The Washington Post",
            "ft-world": "Financial Times",
            "reuters-world": "Reuters",
        }.get(name, name)

    @staticmethod
    def _blocked(text: str) -> bool:
        low = (text or "").lower()
        return any(k in low for k in BLOCK_KEYWORDS)

    @staticmethod
    def _clean(text: str) -> str:
        import re

        text = re.sub(r"<[^>]+>", " ", text or "")
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
        text = text.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        return re.sub(r"\s{2,}", " ", text).strip()