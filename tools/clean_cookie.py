#!/usr/bin/env python3
"""B 站 Cookie 体检与清洗工具。

用途：
  从浏览器复制出来的 B 站 Cookie 里含有 SESSDATA / bili_jct / DedeUserID 等
  登录态凭证，它们等价于账号密码。抓公开视频列表并不需要这些字段，
  本工具把敏感字段剔除，只保留过风控必需的设备指纹与临时票据。

用法：
  python tools/clean_cookie.py "buvid3=xxx; b_nut=xxx; SESSDATA=xxx"
  python tools/clean_cookie.py --check "buvid3=xxx; SESSDATA=xxx"   # 只体检
  cat cookie.txt | python tools/clean_cookie.py -                   # 从 stdin 读
  python tools/clean_cookie.py --clip                               # 从剪贴板读(Windows)
"""

from __future__ import annotations

import argparse
import sys

# ---------------------------------------------------------------- 字段分级表

# 敏感字段：登录态 / 身份凭证，一律删除
SENSITIVE: dict[str, str] = {
    "SESSDATA": "登录态凭证，等价账号密码",
    "bili_jct": "CSRF Token，配合 SESSDATA 可发起写操作",
    "DedeUserID": "你的 B 站 UID（明文数字）",
    "DedeUserID__ckMd5": "UID 校验值",
    "sid": "登录会话 ID",
    "ac_time_value": "登录时间值",
    "bili_live_session": "直播登录态",
    "LIVE_BUVID": "直播登录态",
    "hit-dyn-v2": "动态登录态",
}

# 必需字段：过风控的主力，必须保留
REQUIRED: dict[str, str] = {
    "buvid3": "设备指纹（必需）",
    "bili_ticket": "风控票据（必需）",
}

# 无害字段：保留
SAFE: dict[str, str] = {
    "buvid4": "设备指纹补充",
    "b_nut": "首次访问时间戳",
    "buvid_fp": "浏览器指纹哈希",
    "fingerprint": "指纹种子",
    "CURRENT_FNVAL": "播放器功能开关",
    "CURRENT_QUALITY": "默认清晰度",
    "rpdid": "风控设备 ID",
    "b_lsid": "会话标识",
    "PVID": "页面视图 ID",
    "inner-_cf-uid": "设备标识",
    "_uuid": "设备标识",
    "home-feed-column": "首页偏好（无害）",
    "browser_resolution": "屏幕分辨率",
    "theme_style": "主题偏好",
    "header_theme_version": "主题版本",
    "enable_web_push": "推送开关",
    "bmg_af_switch": "实验开关",
    "bmg_src_def_domain": "域名偏好",
    "bp_t_offset_0": "实验分桶",
    "b-user-id": "访客 ID",
    "deviceFingerprint": "设备指纹",
}

# 未登记字段的默认处理：保留但标注未知
UNKNOWN_NOTE = "未登记字段（保留，请自行确认）"


def parse_cookie(raw: str) -> list[tuple[str, str]]:
    """把 cookie 字符串解析为 [(name, value), ...]。

    容错处理：
    - 允许换行 / 多余空白
    - 去掉开头的 "cookie:" 前缀
    - 忽略空片段
    """
    text = raw.strip()
    # 有些人会把 "cookie: xxx" 一起复制进来
    for prefix in ("cookie:", "Cookie:", "COOKIE:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    # 换行/制表符统一成空格，再按分号切
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    items: list[tuple[str, str]] = []
    for seg in text.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        if "=" in seg:
            name, _, value = seg.partition("=")
            items.append((name.strip(), value.strip()))
        else:
            # 无 = 的片段当成标志位
            items.append((seg, ""))
    return items


def classify(name: str) -> tuple[str, str, str]:
    """返回 (标记, 颜色符号, 说明)。标记 ∈ {keep, drop, unknown}。"""
    if name in SENSITIVE:
        return "drop", "🔴", SENSITIVE[name]
    if name in REQUIRED:
        return "keep", "🟢", REQUIRED[name]
    if name in SAFE:
        return "keep", "🟢", SAFE[name]
    return "keep", "⚪", UNKNOWN_NOTE


def build(items: list[tuple[str, str]]) -> str:
    return "; ".join(f"{k}={v}" if v else k for k, v in items)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="B 站 Cookie 体检与清洗（剔除 SESSDATA 等登录态凭证）"
    )
    ap.add_argument("cookie", nargs="?", help="Cookie 字符串；传 - 则从 stdin 读")
    ap.add_argument("--check", action="store_true", help="只体检，不输出清洗结果")
    ap.add_argument("--clip", action="store_true", help="从剪贴板读取（Windows）")
    ap.add_argument("--quiet", action="store_true", help="只输出清洗后的 Cookie")
    args = ap.parse_args()

    raw = ""
    if args.clip:
        try:
            import subprocess

            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            raw = out.stdout.strip()
        except Exception as exc:  # noqa: BLE001
            print(f"读取剪贴板失败：{exc}", file=sys.stderr)
            return 1
    elif args.cookie == "-":
        raw = sys.stdin.read()
    elif args.cookie:
        raw = args.cookie
    else:
        ap.print_help()
        return 1

    items = parse_cookie(raw)
    if not items:
        print("没解析到任何 Cookie 字段。请确认复制的是 cookie: 后面那一整串值。")
        return 1

    keep: list[tuple[str, str]] = []
    dropped: list[str] = []

    for name, value in items:
        mark, _sym, _note = classify(name)
        if mark == "drop":
            dropped.append(name)
        else:
            keep.append((name, value))

    if not args.quiet:
        print("字段体检：")
        width = max(len(n) for n, _ in items)
        width = min(width, 24)
        for name, value in items:
            mark, sym, note = classify(name)
            action = "删除" if mark == "drop" else "保留"
            shown = (value[:18] + "...") if len(value) > 21 else value
            print(f"  {name:<{width}}  {sym} {action}   {note}")
            if not args.check:
                print(f"  {'':<{width}}        └─ {shown}")
        print()

        if dropped:
            print(f"⚠️  发现 {len(dropped)} 个敏感字段，已移除：{', '.join(dropped)}")
            print("    这些是登录态凭证，等价于账号密码，抓公开视频用不上。")
        else:
            print("✅ 未发现敏感字段，这份 Cookie 是干净的。")
        print()

        missing = [k for k in REQUIRED if k not in dict(items)]
        if missing:
            print(f"⚠️  缺少过风控的关键字段：{', '.join(missing)}")
            if "bili_ticket" in missing:
                print("    bili_ticket 通常只有登录状态下才会下发。")
                print("    建议登录 bilibili.com 后重新复制一次（复制完再删 SESSDATA）。")
            print()

    if args.check:
        return 1 if dropped else 0

    safe = build(keep)
    if not args.quiet:
        print(f"清洗后（共 {len(keep)} 个字段，{len(safe)} 字符）：")
        print("─" * 62)
    print(safe)
    if not args.quiet:
        print("─" * 62)
        print("↑ 复制这一行，粘到 GitHub Secret 的 BILI_COOKIE")
        print()
        print("更新路径：")
        print("  Settings → Secrets and variables → Actions → Secrets")
        print("  → BILI_COOKIE → Update secret")
        print()
        print("注意：粘之前确认是一整行，不要有多余换行。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
