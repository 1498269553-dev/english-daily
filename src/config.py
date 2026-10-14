# -*- coding: utf-8 -*-
"""配置加载：从环境变量 + config.yaml 读取，env 优先。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _int(key: str, default: int) -> int:
    try:
        return int(_env(key) or default)
    except ValueError:
        return default


@dataclass
class Uploader:
    """一个 B 站 UP 主。mid 为空时会在运行时通过搜索接口解析。"""

    name: str
    mid: str = ""
    # 只关心最近 N 天内发布的内容
    recent_days: int = 3
    # 首次运行时回溯多少天建立历史基线（之后靠 state.json 的游标增量推进）。
    # 设成较大值即可覆盖 UP 主从最早一期到现在的全部视频。
    backfill_days: int = 3650

    def resolve_mid(self) -> str:
        return self.mid


@dataclass
class Config:
    uploaders: list[Uploader] = field(default_factory=list)
    fallback_enabled: bool = True
    fallback_sources: list[str] = field(default_factory=list)
    timezone_offset: int = 8

    # LLM（OpenAI 兼容接口，DeepSeek / 通义 / OpenAI 均可）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: int = 120

    # B 站 Cookie（可选但强烈建议配置，用于降低风控概率）
    bili_cookie: str = ""
    # 请求节流：两次请求间最小间隔（秒）与随机抖动上限。
    # GitHub Actions 的 runner 是数据中心 IP，对高频请求更敏感，
    # 建议保持默认；本机调试时可临时调大到 3/2。
    bili_min_interval: float = 1.5
    bili_jitter: float = 0.8
    bili_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # 邮件
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True
    mail_from: str = ""
    mail_to: list[str] = field(default_factory=list)

    # Guardian Open Platform
    guardian_api_key: str = ""

    # 运行
    dry_run: bool = False
    force_fallback: bool = False
    skip_mail: bool = False


def load_config() -> Config:
    raw: dict[str, Any] = {}
    cfg_path = ROOT / "config.yaml"
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    ups = [
        Uploader(
            name=item.get("name", ""),
            mid=str(item.get("mid", "") or ""),
            recent_days=int(item.get("recent_days", 3)),
            backfill_days=int(item.get("backfill_days", 3650)),
        )
        for item in raw.get("uploaders", [])
        if item.get("name")
    ]

    mail_to = [x.strip() for x in _env("MAIL_TO").split(",") if x.strip()]
    if not mail_to and raw.get("mail_to"):
        mail_to = list(raw["mail_to"])

    return Config(
        uploaders=ups,
        fallback_enabled=_env("FALLBACK_ENABLED", "1") not in ("0", "false", "False"),
        fallback_sources=[
            s.strip()
            for s in _env("FALLBACK_SOURCES", ",".join(raw.get("fallback_sources", []))).split(",")
            if s.strip()
        ],
        timezone_offset=_int("TIMEZONE_OFFSET", raw.get("timezone_offset", 8)),
        llm_base_url=_env("LLM_BASE_URL", raw.get("llm_base_url", "")),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", raw.get("llm_model", "")),
        llm_timeout=_int("LLM_TIMEOUT", 120),
        bili_cookie=_env("BILI_COOKIE"),
        bili_min_interval=float(_env("BILI_MIN_INTERVAL", "1.5") or 1.5),
        bili_jitter=float(_env("BILI_JITTER", "0.8") or 0.8),
        bili_user_agent=_env("BILI_USER_AGENT", raw.get("bili_user_agent", "")),
        smtp_host=_env("SMTP_HOST"),
        smtp_port=_int("SMTP_PORT", 465),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD"),
        smtp_use_ssl=_env("SMTP_USE_SSL", "1") not in ("0", "false", "False"),
        mail_from=_env("MAIL_FROM", _env("SMTP_USER")),
        mail_to=mail_to,
        guardian_api_key=_env("GUARDIAN_API_KEY"),
        dry_run=_env("DRY_RUN", "0") not in ("0", "false", "False"),
        force_fallback=_env("FORCE_FALLBACK", "0") not in ("0", "false", "False"),
        skip_mail=_env("SKIP_MAIL", "0") not in ("0", "false", "False"),
    )