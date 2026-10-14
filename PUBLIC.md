# 把仓库改成公开：风险评估与操作清单

> 结论先说：**可以公开，但要动三处配置。**
> 代码和 Secrets 本身是安全的（已扫描确认，见下），真正的风险不在"密钥泄漏"，
> 而在 **① 成稿里的媒体原文版权** 和 **② B 站 Cookie 的登录态**。

---

## 0. 先做的安全扫描结论

```
git ls-files                 → 24 个文件，全部为代码/文档/配置
grep 敏感字样（sk- / password / token / SESSDATA / @qq.com ...）
                             → 命中的只有 ${ { secrets.XXX } } 这种引用
```

**`${{ secrets.SMTP_PASSWORD }}` 这类写法是安全的。** 它是 GitHub 在运行时替换的占位符，
提交到公开仓库也不会泄漏——值本身存在 GitHub 的加密存储里，任何人都读不出来，
包括仓库所有者（只能覆盖，不能查看）。

所以"改公开 = 密码被看光"这个担心是**不成立**的。

---

## 1. 四个真实风险（按严重程度排序）

### 🔴 风险一：成稿里的媒体原文 —— 版权

**这是唯一真正需要动手处理的。**

`src/llm.py` 的写作规范里写着：

> `## 全文对照` —— 给出**完整原文**，不得删减、不得概括、不得只给片段。原素材有多长就写多长。

也就是说，兜底素材如果是 Guardian 的一篇报道（实测 RSS 描述能到 **1958 字符**），
那篇报道的**正文会原封不动进到 `posts/2026-10-14.md`**。

- **私有仓库**：自己学习用，属于合理使用，没人管
- **公开仓库**：等于在公开站点完整转载 The Guardian / NYT / BBC 的付费内容。
  Guardian 相对开放（有 Open Platform），但 NYT、FT、WaPo 是出了名会发 DMCA 的

**实际被追责的概率不高，但这是明确存在的法律风险，不该赌。**

**缓解（三选一，推荐第一个）：**

| 方案 | 做法 | 代价 |
| --- | --- | --- |
| **A. 成稿不入库**（推荐） | 仓库 Variables 里加 `COMMIT_POSTS = false`，只提交 `data/` | 仓库里看不到历史成稿，**邮件照常收到** |
| B. 成稿只留摘要 | 改 `llm.py` 的 `全文对照` 为节选（限 300 词内） | 学习内容质量下降 |
| C. 换开放授权素材 | 只用 Guardian API / 维基 / Project Gutenberg | 素材面变窄 |

> ⚠️ 方案 A **只对未来生效**。已经提交过的 `posts/*.md` 仍在 git 历史里，
> 要彻底清掉得重写历史（`git filter-repo`）或重建仓库。

---

### 🟠 风险二：B 站 Cookie 里的 `SESSDATA` = 你的登录态

`BILI_COOKIE` 里如果带了 `SESSDATA`，那**等价于你的 B 站账号密码**。
它本身在 Secrets 里不会泄漏，但：

1. 万一你本地 `.env` 没 gitignore 干净（已 gitignore，风险低）
2. 万一将来合并了恶意 PR（见风险三）

**缓解**：Cookie 只需要 `buvid3` 和 `bili_ticket` 就能显著降低风控，
**把 `SESSDATA` 那段删掉再粘进 Secret**。登录态对抓公开视频列表没有帮助。

---

### 🟡 风险三：Fork PR 窃取 Secrets

公开仓库任何人都能 fork 并提交 PR。恶意 PR 可以改 `.github/workflows/daily.yml`，
加一行把 Secrets 编码后 POST 到外部服务器。

**但本项目的实际风险比一般公开库低很多**，原因是：

```yaml
on:
  schedule:          # 只有定时
  workflow_dispatch: # 只有手动
```

**没有 `pull_request` 触发器**，所以外面的 PR 根本不会触发这个工作流。
要得手必须你自己把恶意 PR merge 进去 —— 只要你别乱合并，这条路就不通。

**缓解（顺手做一下）：**

- Settings → Actions → General → Fork pull request workflows
  → 选 **"Require approval for all external contributors"**（GitHub 默认就是这个，确认一下）
- 永远别 merge 看不懂的、改动 `.github/` 的 PR

---

### 🟡 风险四：署名信息暴露个人信息

如果配了 `GIT_USER_NAME` / `GIT_USER_EMAIL`，它们会成为 commit 作者信息**永久公开**。

- 用了真名 + 私人邮箱 → 会被爬虫抓去卖
- 不配的话默认用 `english-daily-bot <actions@github.com>`，反而更安全

**缓解**：公开前把这两个 Secret 删掉，或者改成不含个人信息的昵称。

---

## 2. 顺带说一个好处

| 项目 | 私有仓库 | 公开仓库 |
| --- | --- | --- |
| Actions 时长 | 免费额度 2000 分钟/月 | **无限** |
| 定时任务 | 同上 | 同上 |
| 60 天休眠规则 | 会暂停 | 会暂停（一样） |

你现在每天跑 5 分钟，一个月 150 分钟，私有额度绰绰有余。
但公开库在 Actions 时长上是**完全免费无上限**的，算个附带好处。

---

## 3. 改公开的操作清单

```
□ 1. 仓库 Settings → Secrets and variables → Actions → Variables 标签
     → New repository variable
     → Name: COMMIT_POSTS   Value: false          （成稿不再入库，规避版权）

□ 2. Secrets 里删掉 GIT_USER_NAME 和 GIT_USER_EMAIL（或改成不含个人信息的昵称）

□ 3. 重新抓一次 BILI_COOKIE，粘贴前把 SESSDATA=...; 那一段删掉

□ 4. 确认 Settings → Actions → General → Fork pull request workflows
     是 "Require approval for all external contributors"

□ 5. Settings → 页面最底部 Danger Zone → Change repository visibility
     → Change to public → 输入仓库名确认

□ 6. 若之前已有 posts/ 提交过，想彻底清除需重写历史：
     git filter-repo --path posts --invert-paths --force
     （会改写所有 commit hash，谨慎操作；或干脆重建仓库）
```

---

## 4. 我的建议

**推荐做法：代码公开 + 成稿不入库。**

```
公开的部分：src/（抓取+生成逻辑）、config.yaml、*.md 文档、tools/ 诊断脚本
私有的部分：posts/（成稿，走邮件给你）、所有 Secrets
```

这样你既能把项目放进作品集、让别人参考你的实现，
又不用承担转载第三方付费内容的责任，而你自己每天照常收到邮件，体验完全不变。

**不建议的做法**：直接把现在的仓库改成公开而不做任何处理。
等 `posts/` 里攒了几十篇 Guardian/NYT 全文，风险就不再是纸面上的了。
