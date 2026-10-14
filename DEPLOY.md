# 部署到 GitHub

按顺序做完这 5 步，大约 15 分钟。

---

## 第 1 步 · 在 GitHub 创建空仓库

打开 <https://github.com/new>

| 字段 | 填什么 |
| --- | --- |
| Repository name | `english-daily` |
| Description | 每日英语精读自动推送 |
| Public / Private | **建议 Private** —— 成稿和配置不公开更省心 |
| 勾选 | **不要**勾任何选项（不要 README / .gitignore / license） |

> 仓库必须是**空**的，本地已有完整提交。创建后不要点 "add a README file"。

---

## 第 2 步 · 推送代码

在项目目录执行（把 `你的用户名` 换成实际值）：

```bash
cd D:/WorkBuddyData/2026-10-14-10-35-29/english-daily
git remote add origin git@github.com:你的用户名/english-daily.git
git push -u origin main
```

用 SSH 需要先配好 SSH key。如果你用的是 HTTPS：

```bash
git remote add origin https://github.com/你的用户名/english-daily.git
git push -u origin main
```

推送时会要求输入 GitHub 用户名和 **Personal Access Token**（不是密码）。
Token 在 <https://github.com/settings/tokens> 生成，勾 `repo` 权限即可。

---

## 第 3 步 · 配置 Secrets（最关键）

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

逐条添加，**一次一个**，Name 和 Value 都要填：

### 必填（缺了跑不起来）

| Name | Value 示例 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点 |
| `LLM_API_KEY` | `sk-xxxxxxxx` | 模型密钥 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `SMTP_HOST` | `smtp.qq.com` | QQ 邮箱填这个 |
| `SMTP_PORT` | `465` | SSL 用 465，发信失败换 587 |
| `SMTP_USE_SSL` | `1` | 465 填 `1`；587 填 `0`（走 STARTTLS） |
| `SMTP_USER` | `123456789@qq.com` | 发件邮箱 |
| `SMTP_PASSWORD` | `abcdefghijkl` | **SMTP 授权码，不是登录密码** |
| `MAIL_FROM` | `123456789@qq.com` | 可与 `SMTP_USER` 相同 |
| `MAIL_TO` | `me@qq.com` | 收件邮箱，多个用逗号分隔 |

**QQ 邮箱授权码获取**：设置 → 账户 → 开启 SMTP 服务 → 用手机验证 → 得到 16 位授权码。
163 / Gmail 同理，都在设置里开 SMTP 后生成。

### 强烈建议

| Name | 获取方式 |
| --- | --- |
| `BILI_COOKIE` | 见下方说明 |

### 可选

| Name | 说明 |
| --- | --- |
| `GUARDIAN_API_KEY` | <https://open-platform.theguardian.com/access> 免费注册，有全文效果更好 |

### BILI_COOKIE 怎么拿

1. 浏览器登录 bilibili.com
2. F12 打开开发者工具 → **Network** 面板
3. 刷新页面，在请求列表里随便点一个 `api.bilibili.com` 开头的请求
4. **Headers** → Request Headers → 找到 `Cookie:` 那行
5. 右键复制**整行 Cookie 的值**（只要 `buvid3=xxx; bili_ticket=xxx; ...` 这一串，不含 `Cookie:` 字样）

> ⚠️ **复制后先删掉 `SESSDATA=...;` `bili_jct=...;` `DedeUserID=...;` 这三段再填。**
> 它们是登录态凭证（等价于账号密码），而抓公开视频列表只需要 `buvid3` + `bili_ticket`
> 这类匿名设备标识。可用 `tools/clean_cookie.py` 自动清洗。详见 [COOKIE.md](COOKIE.md)。
> DevTools 里显示的是 URL 编码版本，若出现 `%2C` `%3A` 之类需 URL 解码。
> `bili_ticket` 只活几小时~几天，失效后重新复制一次即可。

---

## 第 4 步 · 检查 UP 主配置

仓库里的 `config.yaml` 已经填好了艾伦·麦克法兰：

```yaml
uploaders:
  - name: 艾伦-麦克法兰
    mid: "3546896526215753"
    recent_days: 7
    backfill_days: 3650
```

要改 UP 主直接编辑这个文件并 push。

---

## 第 5 步 · 手动触发验证

进入仓库 → **Actions** 标签页 → 左侧选 **Daily English Digest** →
右侧 **Run workflow** → 点绿色按钮

首次运行会做全量回溯（4~8 分钟），属正常。之后每天只需 1-2 页，很快。

跑完后：

- 看 **Actions 日志**确认哪一步成功（`B 站结果：` 那行会说明命中了什么）
- 看仓库里 **`posts/` 目录**是否生成了当天日期的 `.md`
- 检查**邮箱**是否收到推送

---

## 定时说明

已配置为 **UTC 01:00 = 北京时间 09:00**。

改时间编辑 `.github/workflows/daily.yml` 里的 cron：

```yaml
- cron: "0 1 * * *"   # 北京时间 09:00
```

注意是 **UTC 时间**，北京时间要 **减 8 小时**。比如想北京时间 07:00 推送：

```yaml
- cron: "23 23 * * *"   # UTC 23:00 = 北京次日 07:00
```

⚠️ GitHub 的 cron 在整点触发时经常延迟 5-15 分钟，属正常现象。

---

## 常见问题

**Q: 日志报 `SMTP` 认证失败**
A: 用了登录密码而不是授权码。另外确认 QQ 邮箱已开启 SMTP 服务。

**Q: 成稿开头显示「今日暂无新素材」**
A: 三种可能：① UP 主当天真没更新 ② B 站被风控（看日志有没有 412）③ 兜底 RSS 全部拉取失败。
调试时可以在 Actions 页面勾选 `force_fallback` 手动跑一次，单独验证兜底链路。

**Q: 连续几天都是兜底素材**
A: 大概率是 B 站风控。IP 风控通常几小时会自行解除，先确认 `BILI_COOKIE` 配了没。

**Q: 想验证兜底链路是否正常**
A: Actions → Run workflow → 勾选 `force_fallback`。

**Q: 邮件里 `^{}` 没渲染成灰色小字**
A: 说明成稿是手写或旧版本，重新跑一次生成即可。