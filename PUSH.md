# 推送操作清单

本地仓库已就绪：19 个文件、3 次提交、工作区干净、无敏感文件。
你只需要做 3 件事。

---

## 步骤 1 · 建空仓库

> 如果你用 **GitHub Desktop 的 Publish repository**，这一步可以跳过——它会自动建库。
> 只有走命令行方式才需要手动建。

打开 <https://github.com/new>

| 字段 | 填什么 |
| --- | --- |
| Owner | 你的账号 |
| Repository name | `english-daily` |
| Description | 每日英语精读自动推送 |
| Visibility | **Private**（建议） |
| 下方选项 | **全部不要勾** |

⚠️ 必须是**空仓库**。不要勾 "Add a README file"，否则会和本地提交冲突。

---

## 步骤 2 · 推送

**方式 A · GitHub Desktop（最省事，你已经装了）**

1. 打开桌面上的 **GitHub Desktop**
2. 如果还没登录：菜单 **File → Options → Accounts → Sign in**，用浏览器授权登录
3. **File → Add local repository**（或快捷键 `Ctrl+O`）
4. 路径选：`D:\WorkBuddyData\2026-10-14-10-35-29\english-daily`
   - 点 **Add repository**
   - ⚠️ 如果弹 "This directory does not appear to be a Git repository" → 说明路径选错了，检查一下是不是点进了 `english-daily` 里面一层
5. 加进来后，顶部会看到 **Publish repository** 按钮
6. 点它，填：
   | 字段 | 填什么 |
   | --- | --- |
   | Name | `english-daily` |
   | Description | 每日英语精读自动推送 |
   | ✅ Keep this code private | **勾上**（不勾就是公开库，别人能看到你的配置） |
   | Organization | 留空（None） |
7. 点 **Publish repository**，等进度条走完

> 这一步 GitHub Desktop 会自动帮你：在 GitHub 上建仓库 + 设置 `origin` + `git push -u origin main`。
> 所以**步骤 1 的网页建仓库可以跳过**——两种方式选一个即可。
>
> 若登录时要求输入密码而不是弹浏览器：GitHub 早已不支持密码登录，需要去
> <https://github.com/settings/tokens> 生成 Token（勾 `repo`），粘贴进去。

**方式 B · SSH（命令行）**

```bash
cd D:/WorkBuddyData/2026-14-10-35-29/english-daily
git remote add origin git@github.com:你的用户名/english-daily.git
git push -u origin main
```

> 注意上面的路径应该是 `2026-10-14`，完整路径：
> `cd D:/WorkBuddyData/2026-10-14-10-35-29/english-daily`

如果还没配 SSH key，先执行：

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
```

把输出的公钥粘到 <https://github.com/settings/keys> → New SSH key。

**方式 C · HTTPS（命令行）**

```bash
cd D:/WorkBuddyData/2026-10-14-10-35-29/english-daily
git remote add origin https://github.com/你的用户名/english-daily.git
git push -u origin main
```

推送时会要凭据：
- Username：你的 GitHub 用户名
- Password：**粘贴 Personal Access Token**，不是登录密码

Token 在 <https://github.com/settings/tokens> 生成，勾 `repo` 权限。

---

## 步骤 3 · 配置 Secrets

> **别的项目配过？还是要重新配一遍。**
> GitHub Secrets 是**仓库级**的，账号之间、仓库之间都不共享，没有「全局 Secrets」这种东西。
> 个人账号下的仓库尤其如此——只有 Organization（组织）才能设组织级 Secrets 让成员仓库继承，
> 而且需要你是该组织的 Owner。
>
> ⚠️ 更麻烦的一点：**Secrets 是只写不可读的**。老仓库里配过的值，你现在在网页上**看不到明文**，
> 只能覆盖。所以如果本地没留底，就得重新生成/复制一遍（见下表）。

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### 必填 10 个

| Name | Value |
| --- | --- |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` |
| `LLM_API_KEY` | 你的模型 API key |
| `LLM_MODEL` | `deepseek-chat` |
| `SMTP_HOST` | `smtp.qq.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USE_SSL` | `1` |
| `SMTP_USER` | 你的QQ邮箱@qq.com |
| `SMTP_PASSWORD` | **SMTP授权码**（16位） |
| `MAIL_FROM` | 你的QQ邮箱@qq.com |
| `MAIL_TO` | 收件邮箱 |

**QQ 邮箱授权码**：设置 → 账户 → 开启 SMTP 服务 → 手机验证 → 得到 16 位授权码

### 强烈建议 1 个

| Name | 获取方式 |
| --- | --- |
| `BILI_COOKIE` | 见下方 |

### 可选 1 个

| Name | 获取方式 |
| --- | --- |
| `GUARDIAN_API_KEY` | <https://open-platform.theguardian.com/access> 免费注册 |

---

### BILI_COOKIE 获取步骤

1. 浏览器登录 bilibili.com
2. 按 `F12` 打开开发者工具 → **Network** 面板
3. 刷新页面（`F5`）
4. 在请求列表筛选框输入 `api.bilibili.com`，点开任意一个请求
5. **Headers** → Request Headers → 找到 `cookie:` 那行
6. 右键 → Copy value

复制到的是 `buvid3=xxx; bili_ticket=xxx; ...` 这一串，**不要包含 `cookie:` 这个词**。

> 如果看到 `%2C` `%2A` `+` 这些，说明是 URL 编码版本，需要解码。
> 最省事的办法：用上面的方法重新复制一次，通常 DevTools 给的就是解码后的。

---

### 哪些能直接复用，哪些必须重新生成

| Secret | 老项目配过时怎么办 |
| --- | --- |
| `LLM_BASE_URL` / `LLM_MODEL` | 同一个服务商就**照抄**，值不变 |
| `LLM_API_KEY` | 本地/密码管理器里还留着就抄；**丢了只能去服务商后台重新生成** |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USE_SSL` | **照抄**，QQ 邮箱就是 `smtp.qq.com` / `465` / `1` |
| `SMTP_USER` / `MAIL_FROM` / `MAIL_TO` | **照抄** |
| `SMTP_PASSWORD` | QQ 邮箱授权码可以**无限次重新生成**（设置 → 账户 → SMTP 服务），重新生成一次即可，老的会失效 |
| `BILI_COOKIE` | 会过期，**建议现抓一次**（上面有步骤） |
| `GUARDIAN_API_KEY` | 登录 Guardian 后台能看到，不会丢 |

> 只有 `LLM_API_KEY` 需要你真去翻一下。其余要么照抄，要么 30 秒内能重生成。

---

### 更快的方式：gh CLI 批量导入

点 12 次网页挺烦的。装了 GitHub CLI 的话，一条命令搞定：

```bash
winget install --id GitHub.cli      # 装 gh
gh auth login                        # 登录一次

cd D:/WorkBuddyData/2026-10-14-10-35-29/english-daily
cp .env.example .env                 # 然后填好 .env（.env 已 gitignore，不会进仓库）
bash tools/push_secrets.sh           # 自动从 .env 灌进 Secrets
```

脚本只会上 `BILI_COOKIE / LLM_* / SMTP_* / MAIL_* / GUARDIAN_API_KEY` 这 13 个，
`DRY_RUN`、`SKIP_MAIL` 这类本地调试开关不会推上去（它们走 workflow 的 `with` 参数）。
顺带的好处：`.env` 留在本地，下次换仓库/重装能直接再来一遍。

---

## 步骤 4 · 验证

仓库 → **Actions** 标签页 → 左侧 **Daily English Digest** →右侧 **Run workflow** → 绿色按钮

首次运行会做历史全量回溯，**4~8 分钟**，属正常。

检查三处：

1. **Actions 日志** —— 找 `B 站结果：` 那行，确认命中了什么
2. **仓库 posts/ 目录** —— 应出现当天的 `.md` 文件
3. **邮箱** —— 应收到推送

---

## 排错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| Desktop 提示目录不是 Git 仓库 | 路径选错 | 确认选的是 `english-daily` 这一层（里面有 `.git`） |
| Desktop Publish 后仓库是公开的 | 忘了勾 private | GitHub 网页 → Settings → 最底部 **Change repository visibility** → Private |
| `remote origin already exists` | 已配过远程 | `git remote set-url origin <新地址>` |
| `Permission denied (publickey)` | SSH 未配置 | 改用 HTTPS，或先加 SSH key |
| `Authentication failed` | 用了登录密码 | 改用 Personal Access Token |
| `Updates were rejected` | 远程有本地没有的提交 | `git pull --rebase origin main` 后再 push |
| 邮件认证失败 | 用了登录密码 | 换成 SMTP 授权码 |
| 成稿显示「今日暂无新素材」 | B站风控或兜底源失败 | 勾选 `force_fallback` 手动跑，单独验证兜底 |

---

## 定时时间

当前是 **北京时间 09:00**（`cron: "0 1 * * *"`，UTC 01:00）。

改时间编辑 `.github/workflows/daily.yml`：

| 北京时间 | cron |
| --- | --- |
| 07:00 | `"0 23 * * *"` |
| 08:00 | `"0 0 * * *"` |
| **09:00（当前）** | `"0 1 * * *"` |
| 12:00 | `"0 4 * * *"` |
| 20:00 | `"0 12 * * *"` |
| 22:00 | `"0 14 * * *"` |

⚠️ GitHub 用 **UTC**，北京时间 = UTC + 8。
⚠️ GitHub 的定时任务在整点常延迟 5~15 分钟，属正常现象。
⚠️ 连续两个月没运行的仓库，GitHub 会自动暂停定时任务，需要手动点一次 Run workflow 恢复。