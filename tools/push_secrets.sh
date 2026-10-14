#!/usr/bin/env bash
# 把本地 .env 一键灌进 GitHub 仓库 Secrets，省得在网页点十几下。
#
# 前置：安装 GitHub CLI —— https://cli.github.com/
#   winget install --id GitHub.cli
# 然后登录一次：
#   gh auth login
#
# 用法：
#   bash tools/push_secrets.sh                     # 自动猜仓库（当前 git remote）
#   bash tools/push_secrets.sh 用户名/仓库名        # 手动指定
#
# 注意：GitHub Secrets 是「只写不可读」的，写进去之后网页上再也看不到明文，
#       只能覆盖。所以本地 .env 请自己留一份备份。

set -euo pipefail

REPO="${1:-}"
if [ -z "$REPO" ]; then
  REPO=$(git remote get-url origin 2>/dev/null | sed -E 's#.*github\.com[:/]##; s#\.git$##' || true)
fi
if [ -z "$REPO" ]; then
  echo "✗ 拿不到仓库名。先 publish 一次，或者手动传：bash tools/push_secrets.sh 用户名/english-daily"
  exit 1
fi

ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
  echo "✗ 没有 .env。先 cp .env.example .env 再填"
  exit 1
fi

# 只有这些会被推上 GitHub Secrets；其余是本地调试用的开关
SECRET_KEYS=(
  BILI_COOKIE
  LLM_BASE_URL
  LLM_API_KEY
  LLM_MODEL
  LLM_TIMEOUT
  SMTP_HOST
  SMTP_PORT
  SMTP_USE_SSL
  SMTP_USER
  SMTP_PASSWORD
  MAIL_FROM
  MAIL_TO
  GUARDIAN_API_KEY
)

echo "→ 目标仓库：$REPO"
count=0
for key in "${SECRET_KEYS[@]}"; do
  # 从 .env 取值，兼容 KEY=value / KEY="value" / 导出格式
  val=$(grep -E "^\s*(export\s+)?${key}\s*=" "$ENV_FILE" | tail -n1 \
        | sed -E "s/^\s*(export\s+)?${key}\s*=\s*//; s/^[\"']//; s/[\"']\s*$//" || true)
  if [ -z "$val" ]; then
    echo "  - $key （空，跳过）"
    continue
  fi
  printf '%s' "$val" | gh secret set "$key" --repo "$REPO" >/dev/null
  echo "  ✓ $key"
  count=$((count + 1))
done

echo ""
echo "完成，共写入 $count 个 Secret。"
echo "核对：https://github.com/$REPO/settings/secrets/actions"
echo "（网页只能看到名字，看不到值，这是正常的）"
