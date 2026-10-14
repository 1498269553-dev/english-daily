# -*- coding: utf-8 -*-
"""英语每日精读 —— 主流程。

流程：
  1. 读取配置 -> 逐个 UP 主抓取最近内容
  2. 命中「新内容」（未推送过 且 在 recent_days 内）-> 作为素材
  3. 未命中或抓取失败 -> 标注「今日暂无新素材」并从英美权威媒体兜底
  4. 调 LLM 生成中英对照精读稿 -> 写 posts/YYYY-MM-DD.md -> 提交到仓库
  5. SMTP 推送邮件
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import news as news_mod  # noqa: E402
from src import smtp_send, state as state_mod  # noqa: E402
from src.bili import BiliItem, Fetcher  # noqa: E402
from src.config import Config, load_config  # noqa: E402
from src.llm import LLM, Material, sanitize  # noqa: E402
from src.mailer import wrap_email  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "posts"

NO_MATERIAL_BANNER = "今日暂无新素材"

PROMPT_TEMPLATE = """{style}

---

请基于下面这份素材，制作一篇英语精读短文。

{material}

---

额外要求：
- 「全文对照」小节必须放在所有小节的最前面，读者要先看到文章讲了什么，再看讲解
- 全文对照里的英文原文必须是**完整正文**。素材较长时（超过 1200 词），
  取最具学习价值的完整章节，但必须是一个自洽的完整段落组合，不要截半句话
- 行内标注要克制：只在真正超纲或值得背诵的词下方标注，不要逐词翻译
- 素材若是 BBC/Guardian 等新闻，在全文对照开头交代事件背景
- 素材若是 UP 主视频或动态，在全文对照开头交代「UP 主是谁 + 视频在讲什么 + 语言风格」
  并声明「以下英文文本基于视频主题仿写，非视频原话」
- 「长难句解析」里引用的句子必须与全文对照中的原句逐字一致
- 「背诵例句」的最后一组必须是可套用的写作模板句型
"""


def setup_log() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def now_local(offset: int) -> datetime:
    return datetime.now(timezone(timedelta(hours=offset)))


def pick_bili_material(cfg: Config, fetcher: Fetcher) -> tuple[Material | None, str]:
    """返回 (素材, 说明)。素材为 None 时说明里带原因。"""
    notes: list[str] = []
    for up in cfg.uploaders:
        mid = up.resolve_mid()
        if not mid:
            notes.append(f"{up.name}: 未配置 mid 且无法解析")
            continue
        # 游标锚点 = 已推送 + 该 UP 主的历史基线。
        # 首次运行时两者皆空，fetcher 会自动切到 backfill_days 宽窗口全量回溯，
        # 把该 UP 主从最早一期到现在的历史视频全部纳入基线。
        known = state_mod.known_bvids(mid)
        first_run = not known
        if first_run:
            notes.append(f"{up.name}: 首次运行，执行历史全量回溯")
        try:
            items = fetcher.fetch_latest(
                mid,
                up.recent_days,
                cfg.timezone_offset,
                known,
                backfill_days=up.backfill_days,
            )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{up.name}: 抓取异常 {exc}")
            continue
        if not items:
            notes.append(f"{up.name}: 最近 {up.recent_days} 天无更新")
            continue
        fresh = [i for i in items if i.bvid not in known]
        if not fresh:
            notes.append(f"{up.name}: 最新内容已推送过")
            continue
        top = fresh[0]
        body = top.text.strip()
        # 简介为空时用 view 接口补一次
        if len(body) < 120 and top.kind == "video":
            detail = fetcher.fetch_detail(top.bvid)
            if detail:
                body = ((detail.get("desc") or "") + "\n" + body).strip()
        parts = [f"【视频标题】{top.title}", f"【UP 主】{up.name}"]
        if body:
            parts.append(f"【简介/文案】\n{body[:4000]}")
        parts.append(
            f"【说明】该 UP 主于 {datetime.fromtimestamp(top.pub_ts, tz=timezone(timedelta(hours=cfg.timezone_offset))):%Y-%m-%d %H:%M} 发布。"
            "B站视频通常无公开英文文本，请以标题、简介与主题为线索，"
            "选取该主题下最可能出现的地道英文学习点；若无法确知原片英文内容，"
            "必须在导读中明确说明「以下例句与解析基于主题推演，非视频原话」，不得伪造引语。"
        )
        notes.append(f"{up.name}: 命中 {top.bvid}")

        # 首次全量回溯：把回溯到的历史 bvid 全部登记为「已知」，
        # 否则明天又会因为 known 变化触发一次全量翻页。
        # 只有本次选中的那一条留作 pushed，其余作为 baseline 记下来。
        if first_run:
            baseline = {i.bvid for i in items if i.bvid != top.bvid}
            state_mod.record_baseline(mid, baseline)
            stamps = [i.pub_ts for i in items if i.pub_ts > 0]
            span = (
                datetime.fromtimestamp(
                    min(stamps), tz=timezone(timedelta(hours=cfg.timezone_offset))
                ).strftime("%Y-%m-%d")
                if stamps
                else "未知"
            )
            notes.append(
                f"{up.name}: 已建立历史基线 {len(baseline)} 条"
                f"（{span} → {now_local(cfg.timezone_offset):%Y-%m-%d}）"
            )

        return (
            Material(
                kind="video" if top.kind == "video" else "dynamic",
                title=top.title,
                url=top.url,
                source=f"Bilibili · {up.name}",
                published=datetime.fromtimestamp(
                    top.pub_ts, tz=timezone(timedelta(hours=cfg.timezone_offset))
                ).strftime("%Y-%m-%d %H:%M"),
                body="\n\n".join(parts),
                author=up.name,
            ),
            " | ".join(notes),
        )
    return None, " | ".join(notes) or "未配置任何 UP 主"


def build_markdown(
    cfg: Config, material: Material | None, today: datetime, banner: str, reason: str
) -> str:
    if material is None:
        header = [
            f"# 英语每日精读 · {today:%Y-%m-%d}",
            "",
            f"> **{NO_MATERIAL_BANNER}**",
            f">",
            f"> {reason}",
            f">",
            f"> 以下内容来自英美权威媒体，用于在 UP 主未更新的日子里保持输入。",
            "",
            f"**来源**：{material.source if material else '兜底媒体'}",
            f"**标题**：{material.title if material else ''}",
            f"**链接**：<{material.url if material else ''}>",
            "",
        ]
    else:
        header = [
            f"# 英语每日精读 · {today:%Y-%m-%d}",
            "",
            f"**来源**：{material.source}",
            f"**标题**：{material.title}",
            f"**链接**：<{material.url}>",
            "",
        ]

    llm = LLM(cfg.llm_base_url, cfg.llm_api_key, cfg.llm_model, cfg.llm_timeout)
    from src.llm import STYLE_RULES

    mat = material or Material(kind="news", title="", url="", source="", body="")
    prompt = PROMPT_TEMPLATE.format(style=STYLE_RULES, material=mat.to_prompt())
    body = sanitize(llm.complete(prompt))
    return "\n".join(header) + "\n" + body + "\n"


def main() -> int:
    setup_log()
    log = logging.getLogger("main")

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只生成文件与日志，不发邮件、不写 state")
    ap.add_argument("--force-fallback", action="store_true", help="跳过 B 站，直接用兜底源")
    args = ap.parse_args()

    cfg = load_config()
    if args.dry_run:
        cfg.dry_run = True
    if args.force_fallback:
        cfg.force_fallback = True

    today = now_local(cfg.timezone_offset)
    fetcher = Fetcher(
        cookie=cfg.bili_cookie,
        user_agent=cfg.bili_user_agent,
        min_interval=cfg.bili_min_interval,
        jitter=cfg.bili_jitter,
    )

    material: Material | None = None
    reason = "已手动指定使用兜底素材"
    if cfg.force_fallback:
        log.info("--force-fallback 生效，跳过 B 站")
    else:
        material, reason = pick_bili_material(cfg, fetcher)
        log.info("B 站结果：%s", reason)

    if material is None:
        log.info("进入兜底流程。原因：%s", reason)
        if not cfg.fallback_enabled:
            log.error("兜底已禁用，终止")
            return 2
        nf = news_mod.NewsFetcher(
            guardian_key=cfg.guardian_api_key,
            sources=cfg.fallback_sources or None,
            seed=today.toordinal(),  # 同一天重跑结果一致，便于调试
        )
        art = nf.pick()
        if art is None:
            log.error("兜底源也无可用素材")
            return 3
        body = art.body or art.summary
        warn = ""
        if art.kind == "rss":
            warn = (
                "\n\n【素材说明】该源只提供标题与导语，正文为基于导语的合理扩写，"
                "并非原文全文。请点击链接阅读原文核对细节。"
            )
        material = Material(
            kind="news",
            title=art.title,
            url=art.url,
            source=art.source,
            published=art.published,
            body=f"【新闻标题】{art.title}\n\n【导语】{art.summary}\n\n【正文】{body}{warn}",
        )
        reason = f"{reason}；已启用兜底素材：{art.source}"

    log.info("素材确定：%s", material.title or material.source)

    try:
        md = build_markdown(cfg, material, today, NO_MATERIAL_BANNER, reason)
    except Exception as exc:  # noqa: BLE001
        log.exception("生成成稿失败: %s", exc)
        return 4

    POSTS.mkdir(parents=True, exist_ok=True)
    path = POSTS / f"{today:%Y-%m-%d}.md"
    path.write_text(md, encoding="utf-8")
    log.info("成稿已写入 %s（%d 字符）", path.name, len(md))

    # 索引页
    idx = ROOT / "README.md"
    if idx.exists():
        rows = "\n".join(
            f"| {p.stem} | {p.stat().st_size:,} |" for p in sorted(POSTS.glob("*.md"), reverse=True)[:60]
        )
        table = f"\n## 往期\n\n| 日期 | 字节 |\n| --- | --- |\n{rows}\n"
        text = idx.read_text(encoding="utf-8")
        head, sep, _ = text.partition("\n## 往期")
        idx.write_text((head.rstrip() + table) if sep else text.rstrip() + table, encoding="utf-8")

    if cfg.skip_mail or cfg.dry_run:
        log.info("跳过邮件发送（skip_mail=%s dry_run=%s）", cfg.skip_mail, cfg.dry_run)
    else:
        subject = f"英语每日精读 · {today:%Y-%m-%d}"
        if cfg.force_fallback or "兜底素材" in reason:
            subject += f"  [{NO_MATERIAL_BANNER}]"
        banner = NO_MATERIAL_BANNER if cfg.force_fallback or "兜底素材" in reason else ""
        html = wrap_email(subject, md, banner)
        try:
            smtp_send.send(
                subject=subject,
                html_body=html,
                to=cfg.mail_to,
                from_addr=cfg.mail_from,
                smtp_host=cfg.smtp_host,
                smtp_port=cfg.smtp_port,
                user=cfg.smtp_user,
                password=cfg.smtp_password,
                use_ssl=cfg.smtp_use_ssl,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("邮件发送失败（成稿已生成，不阻断 commit）: %s", exc)

    if not cfg.dry_run:
        st = state_mod.load()
        st["last_run"] = today.isoformat()
        if material and material.url:
            st["last_source"] = material.url
        state_mod.save(st)

    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())