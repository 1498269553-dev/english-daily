# -*- coding: utf-8 -*-
"""Markdown -> 邮件 HTML（极简，无第三方依赖）。"""
from __future__ import annotations

import html
import re


def md_to_html(md: str) -> str:
    """够用的 Markdown 子集：标题、列表、表格、粗体、行内代码、引用、链接、行内注音。"""
    lines = md.splitlines()
    out: list[str] = []
    in_table = False
    list_stack: list[str] = []
    section = ""

    def close_lists(to: int) -> None:
        while len(list_stack) > to:
            out.append(f"</{list_stack.pop()}>")

    def inline(text: str) -> str:
        # 顺序很重要：先整体转义（用户/LLM 内容里的 < > & 必须转义），
        # 再插入我们自己的标签。插入的标签若在转义前写，会被一并转义成 &lt;span。
        text = html.escape(text, quote=False)
        # 行内标注 word^{释义} -> word<span class="anno">（释义）</span>
        # ^{} 内是中文，转义不影响，可安全地在转义后替换
        text = re.sub(
            r"\^\{([^{}]*)\}",
            lambda m: '<span class="anno">（' + m.group(1) + "）</span>",
            text,
        )
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', text)
        return text

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        # 表格
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue  # 分隔行
            if not in_table:
                close_lists(0)
                out.append('<table>')
                in_table = True
                out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                continue
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table and not stripped.startswith("|"):
            out.append("</tbody></table>")
            in_table = False

        if not stripped:
            close_lists(0)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_lists(0)
            lvl = len(m.group(1))
            section = m.group(2).strip()
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            continue

        if stripped.startswith("> "):
            close_lists(0)
            out.append(f"<blockquote>{inline(stripped[2:])}</blockquote>")
            continue

        # 全文对照小节内：中文翻译段加灰底左边框，英文段正常，形成一英一中配对
        if section.startswith("全文"):
            # 中英判定：统计中文字符数 vs 英文字母数，中文占比高即视为翻译段
            n_zh = len(re.findall(r"[\u4e00-\u9fff]", stripped))
            n_en = len(re.findall(r"[A-Za-z]", stripped))
            close_lists(0)
            cls = "trans" if n_zh > n_en else "en"
            out.append(f'<p class="{cls}">{inline(stripped)}</p>')
            continue

        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if m:
            indent = len(m.group(1)) // 2
            tag = "ul" if not re.match(r"^\d", m.group(2)) else "ol"
            if not list_stack:
                list_stack.append(tag)
                out.append(f"<{tag}>")
            elif list_stack[-1] != tag:
                out.append(f"</{list_stack.pop()}>")
                list_stack.append(tag)
                out.append(f"<{tag}>")
            close_lists(1 + indent)
            out.append(f"<li>{inline(m.group(3))}</li>")
            continue

        close_lists(0)
        out.append(f"<p>{inline(stripped)}</p>")

    close_lists(0)
    if in_table:
        out.append("</tbody></table>")

    body = "\n".join(out)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
 body{{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.75;color:#1f2328;max-width:760px;margin:0 auto;padding:24px;}}
 h2{{font-size:20px;border-bottom:2px solid #d8dee4;padding-bottom:6px;margin-top:28px;}}
 h3{{font-size:17px;margin-top:20px;}}
 table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;}}
 th,td{{border:1px solid #d0d7de;padding:6px 10px;text-align:left;vertical-align:top;}}
 th{{background:#f6f8fa;}}
 code{{background:#f6f8fa;padding:2px 5px;border-radius:4px;font-size:13px;}}
 blockquote{{border-left:4px solid #d0d7de;margin:12px 0;padding:4px 14px;color:#57606a;background:#f6f8fa;}}
 a{{color:#0969da;text-decoration:none;}}
 .banner{{background:#fff4e5;border:1px solid #ffcf7d;padding:10px 14px;border-radius:6px;font-weight:600;}}
 .anno{{color:#8b949e;font-size:12px;vertical-align:baseline;}}
 p.en{{margin:14px 0 2px;line-height:1.85;}}
 p.trans{{margin:0 0 16px;padding:8px 14px;background:#f6f8fa;border-left:3px solid #d0d7de;color:#3d444d;font-size:14px;line-height:1.8;}}
 footer{{margin-top:32px;padding-top:14px;border-top:1px solid #eaeef2;color:#8b949e;font-size:12px;}}
</style></head><body>
{body}
<footer>本邮件由 GitHub Actions 自动生成推送，仅供个人英语学习使用。</footer>
</body></html>"""


def wrap_email(title: str, body_md: str, banner: str = "") -> str:
    banner_html = f'<div class="banner">{html.escape(banner)}</div>' if banner else ""
    inner = md_to_html(body_md)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f6f8fa;font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;">
<div style="max-width:800px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;">
  <div style="background:#24292f;color:#fff;padding:16px 24px;">
    <div style="font-size:18px;font-weight:600;">{html.escape(title)}</div>
  </div>
  {banner_html}
  <div style="padding:4px 24px 24px;">{inner}</div>
</div>
</body></html>"""