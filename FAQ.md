# 英语每日精读 · 部署排障实录与 FAQ

> 这份是**实战记录**，不是操作手册（操作手册看 SETUP.md / PUBLIC.md）。
> 记录的是 2026-10-14 首次从零部署到跑通的全过程中，**实际踩到的每一个坑**、
> 排查方法、以及根因。下次出问题先翻这里。

---

## 一、项目是什么

每天北京时间 09:00，GitHub Actions 自动：

```
抓 B 站 UP 主（艾伦-麦克法兰，mid 3546896526215753）最新内容
   ↓ 有更新 → 用它做素材
   ↓ 没更新 → 从 Guardian / BBC / NYT 等权威媒体随机挑一篇兜底
调 LLM 生成中英对照精读短文
   ↓
写进 posts/YYYY-MM-DD.md（可选）+ 发到 QQ 邮箱
```

仓库：`github.com/1498269553-dev/english-daily`
本地：`D:\WorkBuddyData\2026-10-14-10-35-29\english-daily`

---

## 二、踩坑实录（按时间顺序）

### 坑 1：首次运行失败，`exit code 3`

**现象**：Actions 跑了 1 分 05 秒后失败，日志末尾 `Process completed with exit code 3`。

**排查**：`src/main.py` 里搜返回值，定位到：

```python
art = nf.pick()
if art is None:
    log.error("兜底源也无可用素材")
    return 3          # main.py:236
```

含义：**B 站没抓到 + 新闻源也没抓到**，两头都空。

**根因（我写的 bug）**：`news.py` 里有这条过滤：

```python
if len(summary) < 300:
    continue          # 太短的做不了学习材料
```

写的时候以为 RSS 的 `<description>` 都有几百字符。实测完全不是：

| 源 | 摘要最长 | 过 300？ |
| --- | --- | --- |
| BBC world | 181 | ❌ |
| BBC business | 174 | ❌ |
| NYT world | 217 | ❌ |
| FT | 173 | ❌ |
| Telegraph | 137 | ❌ |
| WaPo | — | ❌ HTTP 502 源已死 |
| Reuters | — | ❌ HTTP 301 源已死 |

**没有一条能过线**，池子空了 → `pick()` 返回 None → `return 3`。

**顺带的发现**：探测了 18 个候选源后，找到 **Guardian 的 RSS 自带近全文**：

| 源 | 条目 | ≥600 字符 | 最长 |
| --- | --- | --- | --- |
| `guardian-intl` | 110 | **70** | 1958 |
| `guardian-world` | 45 | **20** | 1871 |
| cnn-world | 29 | 2 | 447 |
| independent | 74 | 0 | 219 |
| bbc-world | 23 | 0 | 181 |

1871 字符基本就是正文前几段，比 BBC 的 181 字符导语强太多，**而且不需要 API key**。

**修复**：

- 门槛拆两档：`MIN_SUMMARY=120`（可用）/ `RICH_SUMMARY=600`（近全文优先）
- 有近全文就只用近全文，绝不因为源少而退回导语
- Guardian 两个源提到最前；新增 CNN / Independent / Telegraph / NPR
- 失效源降级到最后并注明原因
- 支持 `content:encoded` 全文；加 `socket.setdefaulttimeout` 防止死源拖住工作流
- `MAX_SOURCES=8` + `ENOUGH_RICH=6` 早停

**验证**：`pick()` 连跑 5 次，5/5 成功取到 600~1362 字符的 Guardian 文章。
体检脚本复测：修复前 **0 条**可用，修复后 **近全文 90 条 + 可用 308 条**。

**排查工具（已入库，以后源坏了就跑它）**：

```bash
python tools/diag_feeds.py     # 逐个 RSS 体检
python tools/probe_feeds.py    # 探测 18 个候选源找替代品
```

---

### 坑 2：会永远重复推同一条（最严重，但没报错）

**发现时机**：第一次跑成功后，看 `data/state.json` 发现 `pushed: []` 是空的。

**根因**：`state_mod.record()` 我写了，但**在 `main()` 里从来没调用过**。

逻辑链：
1. 首次运行把 121 条历史视频登记为 `baseline`（基线不推送，只作游标锚点）
2. 选中的那条被**刻意排除**在 baseline 之外（它要被推送）
3. 但 `pushed` 是空的 → 那条既不在 baseline 也不在 pushed
4. 明天 `known = pushed ∪ baseline` 里查不到它 → 再次被判定为"新内容"

结果：**每天推同一条，永远**。

**修复**：

- `Material` 新增 `key` 字段（B 站用 bvid，新闻用 url）
- `main()` 末尾调用 `state_mod.record(material.key)`
- 兜底新闻用 `pick_with_seed()` 换种子重试最多 5 次，避开近期已推过的 url
- 手工把当天那条补进 `state.json` 的 `pushed`

**验证**：第二次跑完，`pushed` 变成 2 条 ✅

---

### 坑 3：成稿标题是空的

**现象**：第一篇成稿里 `**标题**：` 后面什么都没有，链接是 `t.bilibili.com/...`（动态）。

**根因**：命中的是一条**无标题的动态**。B 站动态接口的动态项常常没有标题字段。

**修复**：

- 过滤掉「既无标题、正文又不足 80 字」的条目
- 该 UP 主以长视频为主 → **有新视频时优先取视频**，只在视频都推过时才取动态
  ```python
  vids = [i for i in fresh if i.kind == "video"]
  top = vids[0] if vids else fresh[0]
  ```
- 标题兜底取正文首行，避免空标题

---

### 坑 4：B 站接口的风控

实测各接口可用性：

| 接口 | 结论 |
| --- | --- |
| `x/web-interface/view`（视频详情） | **免登录始终可用**，最稳定，已作为详情唯一来源 ✅ |
| `x/space/wbi/arc/search`（投稿列表） | **间歇可用** ⚠️ 需 WBI 签名，同分钟内可能先 200 后 412 |
| `x/polymer/web-dynamic/v1/feed/space`（动态） | **基本不可用** ❌ 持续 412 |
| `x/web-interface/search`（名→mid） | 免登录可用 ✅ |
| `x/web-interface/nav`（拿 wbi key） | 未登录返回 `code=-101`，但 `wbi_img` 仍可用 —— **不能当失败处理** |

**缓解**：配 `BILI_COOKIE`。GitHub Actions 跑在数据中心 IP，比家用 IP 敏感得多。

---

### 坑 5：并发抓详情触发风控

**教训**：曾经用 `ThreadPoolExecutor(max_workers=5)` 并发补详情，一分钟内几十个请求打过去，IP 直接被标记（可用 → 412）。

**结论**：改回串行，且只对真正缺字段的条目补详情。

---

### 坑 6：`html.escape()` 顺序搞反

**现象**：邮件里 `<span class="anno">` 被当纯文本显示出来。

**根因**：先插入 HTML 标签、后做转义，标签自己被转成了 `&lt;span`。

**正确顺序**：

```python
text = html.escape(text, quote=False)          # 先转义
text = re.sub(r"\^\{([^{}]*)\}", ..., text)    # 后插入标签
```

**另一个教训**：验证时我数的是 `class="anno"` 出现次数（3 次），看似正常——
但 `html.escape(quote=False)` **不转义引号**，所以这个指标根本发现不了问题。
**正确的检查是搜 `&lt;span` 残留，必须为 0。**

---

### 坑 7：用脚本批量改 Python 缩进，把文件改坏了

连续 3 个脚本试图批量修正缩进，每次边界判断都错，最终 273 行被过度缩进，
`IndentationError` 在不同行反复出现。

**结论**：**永远不要用脚本批量改 Python 缩进**，直接整文件重写。

---

## 三、Secrets 相关疑问

### Q：为什么非要 11 个？不能一个装完？

GitHub Secret 是**最简单的「名字 → 值」一对**，没有分组、没有嵌套，一个只能装一个值。
所以要传 11 个信息只能建 11 个。

值的流向：

```
网页填的 Secret
   ↓
.github/workflows/daily.yml 的 env: 块（${{ secrets.XXX }}）
   ↓
Python 进程的 os.environ
   ↓
src/config.py 的 os.getenv()
```

**关键**：没建这个 Secret 时，`${{ secrets.X }}` 会变成**空字符串**，
程序不报错、拿到空值，直到发邮件那一步才炸。所以"名字写错"和"没建"是同一种故障，且是静默的。

### Q：之前项目配过，这个还要配吗？

**要。** Secrets 是**仓库级**的，仓库之间不共享，个人账号下没有"全局 Secrets"。
只有 Organization 级能让成员仓库继承，且需要你是 Org Owner。

⚠️ 更麻烦的是：**Secrets 只写不可读**。老仓库的值在网页上看不到明文，只能覆盖。

| Secret | 怎么办 |
| --- | --- |
| `LLM_BASE_URL` / `LLM_MODEL` | 同一服务商就照抄 |
| `SMTP_HOST` / `PORT` / `USE_SSL` | 照抄（QQ：`smtp.qq.com` / `465` / `1`） |
| `SMTP_USER` / `MAIL_FROM` / `MAIL_TO` | 照抄 |
| `SMTP_PASSWORD` | QQ 授权码可无限次重新生成，重生成一次即可 |
| `BILI_COOKIE` | 会过期，建议现抓 |
| `GUARDIAN_API_KEY` | 后台能看到，不会丢 |
| **`LLM_API_KEY`** | **唯一真可能丢的**，回服务商后台重新生成 |

### Q：`sk-` 开头那串是什么？

DeepSeek 的 **API Key**，让程序能调大模型生成精读文章。没有它，B 站能抓到但生成不了文章。

免费替代（三个 Secret 一起换）：

| 服务商 | BASE_URL | MODEL | 免费额度 |
| --- | --- | --- | --- |
| **智谱 GLM** | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | **永久免费** |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` | 部分免费 |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | 无（10 元能用很久） |

> 智谱的 key 长得不一样，**没有 `sk-` 前缀**，别以为拿错了。

### Q：`SESSDATA` 要不要从 Cookie 里删？

**要删。** `SESSDATA` 是 B 站**登录态凭证，等价于账号密码**。
而抓公开视频列表**根本不需要登录** —— `buvid3` + `bili_ticket` 就是过风控的主力。

Cookie 是一串 `key=value;`，找到 `SESSDATA=` 开头、到下一个 `;` 为止整段删掉
（它的值里常带 `%2C` `%3A`，别只删一半）。

泄漏补救：B 站 设置 → 安全隐私 → 登录设备管理 → 退出所有设备 → 改密码，SESSDATA 立刻失效。

### Q：填 Secret 有什么要注意的？

1. **Name 必须一模一样**：全大写、下划线、**前后不能有空格**。写成 `Smtp_Host` 或多敲个空格，工作流**不报错**，只是邮件静默发不出去，极难查。
2. **Secret 框是大文本域，但每个值只粘一行**，粘完别回车、别留换行。`BILI_COOKIE` 那么长也是一整行。
3. 加完**看不到值**（只显示名字），所以值要在本地留底。

---

## 四、定时任务

```yaml
on:
  schedule:
    - cron: "0 1 * * *"    # UTC 01:00 = 北京时间 09:00
```

| 北京时间 | cron |
| --- | --- |
| 07:00 | `"0 23 * * *"` |
| 08:00 | `"0 0 * * *"` |
| **09:00（当前）** | `"0 1 * * *"` |
| 12:00 | `"0 4 * * *"` |
| 20:00 | `"0 12 * * *"` |
| 22:00 | `"0 14 * * *"` |

公式：`UTC小时 = 北京时间 - 8`，不够就往前借一天。

**三个坑**：

| 坑 | 说明 |
| --- | --- |
| 会延迟 | 整点常晚 5~15 分钟甚至更久，不是坏了 |
| 会休眠 | 仓库连续 **60 天**无提交/运行，GitHub 自动暂停定时任务，需手动 Run workflow 唤醒 |
| 时区是 UTC | 别写成北京时间，不然差 8 小时 |

---

## 五、改公开的风险（结论版）

**扫描结论**：仓库里**没有任何密钥泄漏**。命中的只有 `${{ secrets.XXX }}` 引用 ——
那是运行时才替换的占位符，值在 GitHub 加密存储里，**公开也读不出来**（连所有者都看不到，只能覆盖）。

所以"改公开 = 密码被看光"**不成立**。真风险是这四个：

| 级别 | 风险 | 处理 |
| --- | --- | --- |
| 🔴 | **版权**：`llm.py` 要求"全文对照给出完整原文不得删减"，而 Guardian RSS 描述可达 1958 字符 → 等于公开转载付费内容 | 加 `COMMIT_POSTS = false` 变量，成稿不入库 |
| 🟠 | `SESSDATA` = B 站登录态 | Cookie 里删掉那段 |
| 🟡 | Fork PR 窃 Secrets | 本库**只有 `schedule` + `workflow_dispatch`，没有 `pull_request` 触发器**，外人 PR 根本触发不了。别乱 merge 改动 `.github/` 的 PR 就行 |
| 🟡 | `GIT_USER_NAME/EMAIL` 成公开 commit 作者 | 删掉这两个 Secret，默认用 `english-daily-bot` 反而更安全 |

**附带好处**：公开库 Actions 时长**无限**（私有 2000 分钟/月）。

⚠️ `COMMIT_POSTS=false` **只对未来生效**，已提交的 `posts/*.md` 仍在 git 历史里，
要彻底清掉得 `git filter-repo --path posts --invert-paths --force` 或重建仓库。

---

## 六、Git 协作经验（这台机器）

- GitHub Desktop 发布时会在**本地仓库**写入 `credential.helper=manager`，
  所以我可以**直接 `git push`**（加 `GIT_TERMINAL_PROMPT=0` 避免卡在交互提示）
- 工作流自己会往 main 提交（digest / README 更新），本地提交常撞 non-fast-forward。
  标准解法：
  ```bash
  git fetch -q origin
  GIT_EDITOR=true git rebase origin/main
  git push origin main
  ```
- **rebase 冲突时 `--ours` 指的是 upstream（origin/main）那一侧，不是本地改动！**
  要拿自己的版本得 `--theirs`，或直接手工改文件
- 非交互环境 `git rebase --continue` 需要 `GIT_EDITOR=true`，否则报 "Terminal is dumb"

---

## 七、速查：出问题先看这

| 现象 | 定位 |
| --- | --- |
| `exit code 2` | 兜底被禁用（`FALLBACK_ENABLED=0`）且 B 站无素材 |
| **`exit code 3`** | 兜底源也无素材 → 跑 `python tools/diag_feeds.py` 体检源 |
| `exit code 4` | LLM 调用失败 → 检查 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` 是否配套 |
| 邮件报 `535` | 用了 QQ 登录密码，换 16 位授权码；`SMTP_USER` 要带 `@qq.com` |
| 邮件报 SSL 相关 | 端口/加密不匹配：465 ↔ `USE_SSL=1`，587 ↔ `USE_SSL=0` |
| 成稿标「今日暂无新素材」 | B 站风控 412 或 UP 主真没更新 → 换 `BILI_COOKIE` |
| 每天都是同一条 | `state.json` 的 `pushed` 没登记 → 检查 `Material.key` 是否传下去 |
| 标题为空 | 命中了无标题动态 → 检查"优先取视频"逻辑 |
| 推送时间不对 | cron 写成北京时间了，减 8 |

---

## 八、一键清单（下次从零再来一遍）

```
□ 1. QQ 邮箱：mail.qq.com → 设置 → 账户 → 开启 IMAP/SMTP → 拿 16 位授权码
□ 2. LLM：platform.deepseek.com → API Keys → 复制 sk-xxx
□ 3. B 站 Cookie：F12 → Network → 筛 api.bilibili.com → 复制 cookie（删掉 SESSDATA）
□ 4. GitHub Desktop：File → Add local repository → english-daily
□ 5. Desktop：Publish repository → 勾 Keep this code private → Publish
□ 6. Settings → Secrets and variables → Actions → New repository secret
     填 10 个必填 + BILI_COOKIE
□ 7. Actions → Daily English Digest → Run workflow → 等 5 分钟
□ 8. 检查日志 + 邮箱
□ 9. （若要公开）Variables 加 COMMIT_POSTS=false → Danger Zone 改公开
```
