# 英语每日精读 · 完整配置手册

> 目标：每天北京时间 **09:00** 自动抓 B 站 UP 主更新 → 生成中英对照精读 → **发到你的 QQ 邮箱**。
> 全程不需要命令行，用 GitHub Desktop + GitHub 网页即可完成。
> 预计耗时：**20 分钟**（大头是找 QQ 授权码）。

---

## 0. 你要准备的东西（先备齐，别边配边找）

| # | 东西 | 去哪拿 | 大概多久 |
| --- | --- | --- | --- |
| 1 | QQ 邮箱 **SMTP 授权码**（16 位） | mail.qq.com → 设置 → 账户 | 3 分钟 |
| 2 | DeepSeek **API Key**（`sk-` 开头） | platform.deepseek.com | 2 分钟 |
| 3 | B 站 **Cookie**（强烈建议） | 浏览器 F12 | 2 分钟 |
| 4 | GitHub 账号（已登录 Desktop） | — | — |

代码和仓库我已经准备好了，你不用写代码。

---

## 1. 拿 QQ 邮箱 SMTP 授权码 ⭐ 最容易卡住的一步

### 1.1 开启服务

1. 浏览器打开 <https://mail.qq.com> 并登录
2. 顶部点 **设置** → **账户**（不是「常规」，是「账户」标签页）
3. 页面往下拉，找到这一大块：
   > **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务**
4. 找到 **「IMAP/SMTP服务」** 那一行 → 点 **开启**
5. 会弹一个验证框，要求用**绑定的手机发一条短信**到指定号码（内容通常是「配置邮件客户端」之类的固定文案）
6. 发完点「我已发送」
7. 页面会弹出一串 **16 位字母** 的授权码，例如 `abcdefghijklmnop`

> ⚠️ **这串码只显示这一次，关掉就再也看不到，只能重新生成。**
> 当场复制，或截图存好。

### 1.2 记下这组参数

| 项目 | 值 | 说明 |
| --- | --- | --- |
| SMTP 服务器 | `smtp.qq.com` | 所有 QQ 邮箱都一样 |
| 端口 | `465` | 配 SSL 用 465 |
| 加密 | SSL | 项目里对应填 `1` |
| 用户名 | `你的QQ号@qq.com` | **必须带 `@qq.com`**，只填 QQ 号会登录失败 |
| 密码 | **那 16 位授权码** | ❌ 不是你的 QQ 登录密码，也不是邮箱独立密码 |

### 1.3 常见坑

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 找不到「IMAP/SMTP服务」 | 用的是邮箱**独立密码**登录 | 退出，用 QQ 号+QQ 密码重新登录 |
| 收不到短信 / 提示发送失败 | 手机号不是密保手机 | 去 QQ 安全中心改密保手机 |
| 登录报 `535 Authentication failed` | 填了 QQ 登录密码 | 换成 16 位授权码；`SMTP_USER` 补全 `@qq.com` |
| 报 `SSL: WRONG_VERSION_NUMBER` | 端口和加密不匹配 | `465` 配 `SMTP_USE_SSL=1`；用 `587` 就配 `0` |
| 授权码忘了 | 看不见明文 | 重走 1.1，重新生成，**旧的立刻失效** |
| 用 163/126 邮箱 | 参数不同 | 见下表 |

**其他邮箱参数对照**（如果你想换成别的邮箱）：

| 邮箱 | HOST | PORT | USE_SSL | 密码 |
| --- | --- | --- | --- | --- |
| QQ | `smtp.qq.com` | `465` | `1` | 16 位授权码 |
| 163 | `smtp.163.com` | `465` | `1` | 授权码（非登录密码） |
| 126 | `smtp.126.com` | `465` | `1` | 授权码 |
| Gmail | `smtp.gmail.com` | `587` | `0` | App Password（需开 2FA） |
| Outlook | `smtp.office365.com` | `587` | `0` | 账号密码或应用密码 |

---

## 2. 拿 DeepSeek API Key

1. 打开 <https://platform.deepseek.com> 注册/登录
2. 左侧 **API Keys** → **创建 API Key**
3. 复制 `sk-xxxxxxxx...`（只显示一次）
4. 充个十块钱够跑很久（deepseek-chat 很便宜，一篇大概几分钱）

想换别家也行，只要是 **OpenAI 兼容接口**：

| 服务商 | BASE_URL | MODEL |
| --- | --- | --- |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`（有免费额度） |
| 月之暗面 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |

---

## 3. 拿 B 站 Cookie（强烈建议，不配容易被风控）

GitHub Actions 跑在**数据中心 IP** 上，B 站对这类 IP 比家用 IP 敏感得多。
不带 Cookie 时列表接口经常返回 412，导致抓不到东西、只能走新闻兜底。

1. 浏览器登录 <https://www.bilibili.com>
2. 按 `F12` → 切到 **Network** 面板
3. 按 `F5` 刷新页面
4. 筛选框输入 `api.bilibili.com`，点开任意一个请求
5. 右侧 **Headers** → **Request Headers** → 找到 `cookie:` 这一行
6. 右键 → **Copy value**

复制到的是 `buvid3=xxx; bili_ticket=xxx; SESSDATA=xxx; ...` 这一长串。
**不要包含 `cookie:` 这个词本身。**

> ⚠️ **先把 `SESSDATA=...` 那一段删掉再粘进 Secret。**
> `SESSDATA` 是 B 站的**登录态凭证，等价于账号密码**，拿到的人可以不输密码操作你的账号。
> 而抓公开视频列表**根本不需要登录**——`buvid3` + `bili_ticket` 就是过风控的主力。
> Cookie 是一串 `key=value;`，找到 `SESSDATA=` 开头、到下一个 `;` 为止，整段删掉即可
> （它的值里常带 `%2C` `%3A` 这类编码字符，别只删一半）。
> 仓库若是私有的话留着也行；**打算公开就必须删**。
> 万一泄漏：B 站 设置 → 安全隐私 → 登录设备管理 → 退出所有设备，然后改密码，SESSDATA 立刻失效。

> 如果里面有 `%2C` `%3A` 这类百分号，说明是 URL 编码版，重新复制一次通常就好了。
> Cookie 大约 **半年**失效一次，发现每天都是「今日暂无新素材」时就该换一个。

---

## 4. 用 GitHub Desktop 发布仓库

> 这一步会自动帮你：在 GitHub 上建仓库 + 配好远程地址 + 推送全部代码。
> 所以**不用**再去网页上手动建仓库。

### 4.1 登录

打开桌面上的 **GitHub Desktop**

- 菜单 **File → Options → Accounts**（Windows 上是 **File → Options**）
- 点 **Sign in**，浏览器会弹出来授权，确认即可

> 如果它让你输「密码」而不是弹浏览器：GitHub 早就不支持密码登录了。
> 去 <https://github.com/settings/tokens> 生成一个 Token（勾 `repo` 权限），粘进去。

### 4.2 添加本地仓库

- **File → Add local repository**（快捷键 `Ctrl+O`）
- 路径选：`D:\WorkBuddyData\2026-10-14-10-35-29\english-daily`
- 点 **Add repository**

加进来后左下角 History 里能看到已有的 **7 次提交**，说明加载正确。

> ⚠️ 如果提示 "This directory does not appear to be a Git repository"：
> 路径选深了，回到 `english-daily` 这一层（里面应该能看到 `.github`、`src`、`config.yaml`）。

### 4.3 发布

点顶部蓝色的 **Publish repository**，填：

| 字段 | 填什么 |
| --- | --- |
| Name | `english-daily` |
| Description | 每日英语精读自动推送 |
| ✅ **Keep this code private** | **必须勾上** —— 不勾就是公开库，别人能看到你的配置和成稿 |
| Organization | 留空（None） |

点 **Publish repository**，等进度条走完。

---

## 5. 配置 Secrets ⭐ 核心步骤

### 5.1 先说清楚：为什么之前配过还要再配

- GitHub Secrets 是**仓库级**的，**仓库之间不共享**，个人账号下没有「全局 Secrets」
- Secrets **只写不可读**：老仓库里的值在网页上**看不到明文**，只能覆盖
- 所以这个值如果本地没留底，只能重新生成

**能直接照抄的**：`LLM_BASE_URL`、`LLM_MODEL`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_USE_SSL`、`SMTP_USER`、`MAIL_FROM`、`MAIL_TO`
**30 秒内能重生成的**：`SMTP_PASSWORD`（QQ 授权码可无限次重生成）、`BILI_COOKIE`
**唯一可能真丢的**：`LLM_API_KEY`（回服务商后台重新生成即可）

### 5.2 进入配置页

1. 浏览器打开你刚发布的仓库：`https://github.com/你的用户名/english-daily`
2. 点 **Settings**（仓库右上角，不是头像那个）
3. 左侧 **Secrets and variables** → **Actions**
4. 点右上角绿色 **New repository secret**

一次填一个，Name 和 Value 都填好点 **Add secret**，然后继续下一个。

> ⚠️ 三个细节：
> 1. **Name 必须一模一样**：全大写、下划线分隔、**前后不能有空格**。写错（比如 `Smtp_Host`、`SMTP_HOST `）工作流读不到，且不会报错，只会表现为邮件发不出去。
> 2. **Secret 框虽然是大文本域，但每个值都只粘一行**，粘完别回车、别留换行，末尾也不要多敲空格。
> 3. 加完之后**看不到值**（只显示名字和更新时间），这是设计如此——所以请把值在本地留个底。

### 5.3 必填 10 个（用 QQ 邮箱）

| # | Name | Value（照抄或替换） |
| --- | --- | --- |
| 1 | `LLM_BASE_URL` | `https://api.deepseek.com/v1` |
| 2 | `LLM_API_KEY` | `sk-xxxxxxxx`（第 2 步拿到的） |
| 3 | `LLM_MODEL` | `deepseek-chat` |
| 4 | `SMTP_HOST` | `smtp.qq.com` |
| 5 | `SMTP_PORT` | `465` |
| 6 | `SMTP_USE_SSL` | `1` |
| 7 | `SMTP_USER` | `你的QQ号@qq.com` ← **必须带后缀** |
| 8 | `SMTP_PASSWORD` | 第 1 步的 **16 位授权码** ← 不是 QQ 密码 |
| 9 | `MAIL_FROM` | `你的QQ号@qq.com`（和上面一样） |
| 10 | `MAIL_TO` | 收件邮箱，多个用英文逗号分隔：`123456@qq.com,abc@163.com` |

### 5.4 强烈建议 1 个

| # | Name | Value |
| --- | --- | --- |
| 11 | `BILI_COOKIE` | 第 3 步复制的那一长串 |

### 5.5 可选 3 个

| # | Name | Value | 不配会怎样 |
| --- | --- | --- | --- |
| 12 | `GUARDIAN_API_KEY` | <https://open-platform.theguardian.com/access> 免费申请 | 兜底源少一个有全文的来源 |
| 13 | `GIT_USER_NAME` | 你的名字 | 自动提交署名变成 `english-daily-bot` |
| 14 | `GIT_USER_EMAIL` | 你的邮箱 | 同上 |

> 填完核对一下：Settings → Secrets and variables → Actions 里应该能看到 **11~14 条**记录。
> 网页上**只能看到名字，看不到值**，这是正常的。

---

## 6. 手动跑一次验证

**Secrets 全部填完再跑**，否则邮件那步必失败。

1. 仓库页面 → 顶部 **Actions** 标签
2. 左侧工作流列表点 **Daily English Digest**
3. 右侧点 **Run workflow** → 再点绿色 **Run workflow** 按钮
4. 等 4~8 分钟（首次会做历史全量回溯，100+ 个视频，每个请求间隔 1.5~2.3 秒）

### 检查三处

| 位置 | 正常表现 |
| --- | --- |
| Actions 日志 | 看到 `B 站结果：` 那一行，写明命中了哪条视频；结尾没有红色 ❌ |
| 仓库 `posts/` 目录 | 出现当天日期的 `.md` 文件，如 `2026-10-14.md` |
| QQ 邮箱 | 收到标题类似「英语每日精读 · 2026-10-14」的邮件 |

三个都对了，整套就通了。

---

## 7. 定时任务

### 7.1 当前设置

**北京时间每天 09:00** 自动执行。

配置文件在 `.github/workflows/daily.yml`：

```yaml
on:
  schedule:
    - cron: "0 1 * * *"    # UTC 01:00 = 北京时间 09:00
```

### 7.2 改推送时间

编辑 `.github/workflows/daily.yml`，把 `cron` 那行换成下表的对应值，提交即可。

| 北京时间 | cron |
| --- | --- |
| 07:00 | `"0 23 * * *"` |
| 08:00 | `"0 0 * * *"` |
| **09:00（当前）** | `"0 1 * * *"` |
| 10:00 | `"0 2 * * *"` |
| 12:00 | `"0 4 * * *"` |
| 20:00 | `"0 12 * * *"` |
| 22:00 | `"0 14 * * *"` |

> 公式：`UTC小时 = 北京时间小时 - 8`，不够就往前借一天。

### 7.3 三个要知道的坑

| 坑 | 说明 |
| --- | --- |
| **会延迟** | GitHub 定时任务在整点常常晚 5~15 分钟甚至更久，属正常，不是坏了 |
| **会休眠** | 仓库连续 **60 天**没有任何提交/运行，GitHub 会**自动暂停**定时任务，需要手动 Run workflow 一次唤醒 |
| **时区是 UTC** | 别写成北京时间，不然会差 8 小时 |

---

## 8. 日常维护

### 8.1 换 UP 主

编辑仓库里的 `config.yaml`（网页上直接点文件 → 右上角铅笔图标即可改）：

```yaml
uploaders:
  - name: 艾伦-麦克法兰
    mid: "3546896526215753"
    recent_days: 7      # 只推最近 7 天发布的
    backfill_days: 3650 # 首次回溯 10 年建基线
```

- `mid` 从 UP 主主页 URL 里拿：`https://space.bilibili.com/3546896526215753` 中间那串数字
- 只填 `name` 不填 `mid` 也行，程序会自动搜索解析
- 改完 Commit changes 即可，下次运行生效

### 8.2 换推送邮箱

改 5 个 Secrets：`SMTP_HOST` / `SMTP_PORT` / `SMTP_USE_SSL` / `SMTP_USER` / `SMTP_PASSWORD`。
参数对照表见本文 1.3。

### 8.3 换 LLM

改 3 个：`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`。对照表见第 2 节。

### 8.4 兜底源体检（怀疑新闻源坏了就跑这个）

```bash
python tools/diag_feeds.py     # 逐个 RSS 体检：条目数、摘要长度、可用条数
python tools/probe_feeds.py    # 探测 18 个候选源，找替代品用
```

`diag_feeds.py` 会打印每个源的「近全文 / 可用」条数。若某天全是 0，说明该源挂了，
用 `probe_feeds.py` 找替代 URL，改 `src/news.py` 里的 `DEFAULT_FEEDS` 即可。

> 2026-10-14 实测基线：Guardian 两个源提供 90 条近全文素材，其余源合计 200+ 条导语级素材。

---

## 9. 排错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 邮件收不到，日志报 `535` | 用了 QQ 登录密码 | 换 16 位授权码 |
| 邮件收不到，日志报 `SSL` 相关 | 端口/加密不匹配 | 465 ↔ `USE_SSL=1`；587 ↔ `USE_SSL=0` |
| `SMTP_USER` 被拒 | 没带 `@qq.com` | 补全 |
| 成稿显示「今日暂无新素材」 | B 站风控（412）或 UP 主真没更新 | 换 `BILI_COOKIE`；或勾 `force_fallback` 手动跑验证兜底源 |
| Actions 失败，日志末尾 `exit code 3` | 代码里 `return 3` = 「兜底源也无可用素材」，即 B 站和新闻源都没抓到 | 2026-10-14 已修（RSS 长度门槛从 300 降到 120/600 两档，并换上 Guardian 近全文源）。若再现，跑 `python tools/diag_feeds.py` 体检源；同时确认 `BILI_COOKIE` 是否过期 |
| Actions 失败，日志末尾 `exit code 2` | 兜底被禁用（`FALLBACK_ENABLED=0`）且 B 站无素材 | 把 `FALLBACK_ENABLED` 改回 `1` |
| Actions 失败，日志末尾 `exit code 4` | 生成成稿时抛异常，多半是 LLM key 无效或模型名写错 | 检查 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` 三者是否配套 |
| Actions 报 `Bad credentials` | 仓库改名/换账号 | 重新用 Desktop Publish 或检查 remote |
| Desktop 提示不是 Git 仓库 | 路径选错 | 选 `english-daily` 那一层 |
| 发布后发现是公开库 | 忘了勾 private | Settings → 页面最底 **Change repository visibility** → Private |
| 每天都是旧内容 | `state.json` 游标问题 | 删掉仓库 `data/state.json` 重新跑一次全量 |
| 推送时间不对 | cron 写成北京时间 | 减 8 小时，见 7.2 |

---

## 10. 一键速查清单（下次照着走）

```
□ 1. QQ 邮箱：mail.qq.com → 设置 → 账户 → 开启 IMAP/SMTP → 拿 16 位授权码
□ 2. DeepSeek：platform.deepseek.com → API Keys → 创建 → 复制 sk-xxx
□ 3. B 站 Cookie：F12 → Network → 筛 api.bilibili.com → 复制 cookie 值
□ 4. GitHub Desktop：File → Add local repository → english-daily
□ 5. Desktop：Publish repository → 勾 Keep this code private → Publish
□ 6. GitHub 仓库 → Settings → Secrets and variables → Actions
      填 10 个必填 + BILI_COOKIE + （可选 Guardian / GIT_USER_*）
□ 7. Actions → Daily English Digest → Run workflow → 等 5 分钟
□ 8. 检查日志 + posts/ 目录 + QQ 邮箱
```

---

## 附：Secrets 值速填卡（打印/存备忘录用）

```
LLM_BASE_URL      = https://api.deepseek.com/v1
LLM_API_KEY       = sk-________________________
LLM_MODEL         = deepseek-chat

SMTP_HOST         = smtp.qq.com
SMTP_PORT         = 465
SMTP_USE_SSL      = 1
SMTP_USER         = ________@qq.com
SMTP_PASSWORD     = ________________  (16位授权码，非QQ密码)
MAIL_FROM         = ________@qq.com
MAIL_TO           = ________@qq.com

BILI_COOKIE       = buvid3=...; b_nut=...; bili_ticket=...; buvid4=...
                    ↑ 注意：SESSDATA=... 那一段要删掉，它是登录态=账号密码

GUARDIAN_API_KEY  = (可选)
GIT_USER_NAME     = (可选)
GIT_USER_EMAIL    = (可选)
```
