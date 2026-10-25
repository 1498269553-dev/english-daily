# 英语每日精读自动推送

每天自动抓取指定 B 站 UP 主的最新内容，生成一篇中英对照精读短文，存进仓库并邮件推送。
UP 主当天没更新时，自动从英美权威媒体（匿名）随机挑一篇作为替代素材，
并在成稿开头明确标注「今日暂无新素材」。

> **📘 从零配置看 [SETUP.md](SETUP.md)** —— GitHub Desktop 发布 + QQ 邮箱授权码 + 12 个 Secrets + 定时，全程图形界面。
> **首次部署请看 [DEPLOY.md](DEPLOY.md)** —— 含 GitHub Secrets 完整清单与排错手册。
> **准备推送看 [PUSH.md](PUSH.md)** —— 逐步操作清单，命令可直接复制。
> **想改成公开库先看 [PUBLIC.md](PUBLIC.md)** —— 风险评估（版权 / Cookie 登录态 / Fork PR）+ 操作清单。
> **B 站 Cookie 看 [COOKIE.md](COOKIE.md)** —— 怎么拿、为什么要用、SESSDATA 风险、如何查泄漏、泄漏后怎么办。

---

## 一、可行性评估结论（2026-10-14 实测）

| 环节 | 结论 | 依据 |
| --- | --- | --- |
| B 站视频详情 `x/web-interface/view` | **免登录可用，最稳定** ✅ | 实测始终可用，且 `pubdate`/`duration`/`desc` 比投稿列表接口完整，**已作为详情唯一来源** |
| B 站投稿列表 `x/space/wbi/arc/search` | **间歇可用** ⚠️ | 需 WBI 签名。实测同一分钟内先返回数据、后返回 412/-352，成功率随 IP 信誉波动。已加退避重试 |
| B 站动态 `x/polymer/web-dynamic/...` | **基本不可用** ❌ | 实测持续 412 |
| UP 主名 → mid | **免登录可用** ✅ | `x/web-interface/search` 实测 `code=0` |
| 兜底媒体 RSS | **可用** ✅ | 7 个源已内置。零 key、零成本 |
| Guardian Open Platform | **可用，需免费 key** | 免费 500 次/天，含 `bodyText` 全文，效果远好于 RSS |
| LLM 生成 | **可用** ✅ | 任何 OpenAI 兼容接口（DeepSeek 等） |
| GitHub Actions 定时 + 邮件推送 | **可用** ✅ | 标准 cron + SMTP |

**总体结论：可行。** 核心依赖（view 接口）免登录且稳定，风险点在投稿列表接口的 IP 层风控。

**抓取策略（两段式）：**

**第一段 · 首次全量回溯（只发生一次）**

`backfill_days`（默认 3650 天 ≈ 10 年）在首次运行时生效。检测到 `state.json` 里该 UP 主
没有任何基线时，会从最新页一直翻到底，把**从最早一期到当前最新**的全部视频纳入基线。

```
第 1 页  ← 2026 年最新（10-11）
第 2 页  ← 2026 年 5-6 月
第 3 页  ← 2026 年初
第 4 页  ← 2025 年 12 月
第 5 页  ← 2025 年 9-10 月
第 N 页  ← 2025-05-08（最早一期）
```

实测艾伦·麦克法兰这个 UP 主有 **100+ 条视频，从 2025-05-08 至今**，仅用 2 页翻页是远远不够的
（`recent_days=7` 时只看 2 页，实际只会看到 2026 年 5 月之后的内容）。

**第二段 · 稳态游标推进（每天一次）**

基线建立后转为游标翻页：从最新一页往前翻，**遇到已推送或已在基线里的 bvid 就立即停**。
稳态下每次只请求 1-2 页，既省请求也抗风控。

**其他要点：**

- 翻页上限：全量回溯 `max_pages=30`，稳态 `max_pages=10`（每页 30 条）
- 拿到 bvid 后用 `view` 接口补全 `pubdate`/`duration`/`owner`/`desc`；
  **串行**调用且只补列表里缺失的字段——实测并发 5 线程会瞬时打出几十个请求，
  极易触发风控（同一分钟就从可用变成 412）
- 投稿列表接口有指数退避重试（3s→6s→12s→24s），重试前重新拉取可能已轮换的密钥
- `pub_ts <= 0` 的条目会被 `is_recent` 判为「不新」，避免 1970 年时间戳误触发兜底
- 所有路径失败都不抛异常，自动降级到兜底媒体源

**查看历史清单：**

```bash
python src/history.py --mid 3546896526215753 --name "艾伦-麦克法兰"   # 拉取并输出
python src/history.py --list                                         # 查看已保存的清单
```

会把该 UP 主全部视频按发布时间排序输出，并按月统计分布，保存到
`data/history_<mid>.json`。首次部署时建议先跑一次，确认抓取范围覆盖了你想用的历史区间。

> ⚠️ 本地直连 B 站和英美站点均被风控/网络拦截，属预期。**该项目设计为在 GitHub Actions 上运行**，那里的网络环境与本机不同。

---

## 二、整体设计

### 成稿结构（固定五节，顺序不可调换）

```
① 全文对照      ← 第一节，完整英文原文 + 逐段中文翻译 + 行内生词标注
② 生词与短语     ← 拆两张表：高频核心词 / 拓展词与短语
③ 长难句解析     ← 2-3 句，必须照抄①里的原句，逐层拆语法
④ 核心内容摘要   ← 3-5 点，回答「文章讲了什么」
⑤ 背诵例句       ← 6-8 组 + 1 个可套用写作模板
```

**为什么全文对照必须是第一节：** 没有全文，生词表就成了悬空的标签 —— 读者知道 `jeer` 是「嘲笑」，但不知道它在句子里怎么用。全文在最前，读者先建立整体理解，后面的讲解才有落点。

**生词表为什么拆两张：** 中国学生的问题不是「不认识生僻词」，而是**大纲核心词只会直译**。所以：

- **高频核心词**（6-8 个）：中考/高考大纲词，且是中国学生普遍用错的。收录标准包括
  ① 大纲核心词且在原文承担关键语义 ② 看似简单但只会直译的词（develop / relationship /
  protect / result / consider / involve / remain）③ 一词多义且原文用非最常见义项
  ④ 有固定搭配的动词（`result from` 源于 vs `result in` 导致，这种反向关系必须标出来）
- **拓展词与短语**（6-8 个）：学术/新闻地道词汇，传统的高分内容

**高频词同样要做行内标注**：prompt 里明确要求「段落开头若出现高频核心词，优先标它，而不是先标生僻词」——
否则读者在全文里看到的全是没标注的简单词，只在表格里被讲解，脱节。

**行内标注语法：** LLM 输出 `jeered^{嘲笑}`，渲染时转为 `<span class="anno">（嘲笑）</span>`，显示为紧跟英文词的灰色小号字。一眼能分辨哪些是原文、哪些是注释，不会误读成原文的一部分。

标注范围由 prompt 严格约束：实义词、固定搭配、一词多义、逻辑连接词必须标；冠词介词代词、数词、最基础动词禁止标。一段 5-12 个，宁缺毋滥，避免变成逐词翻译。

### 数据流

```
┌──────────────┐
│ GitHub Actions│  cron 每日 01:00 UTC（北京时间 09:00）
└──────┬───────┘
       ▼
  src/main.py
       │
       ├─► bili.Fetcher ──► UP 主最近内容 ──► state.json 去重
       │      动态接口 → 投稿列表(WBI) → 视频详情(view)
       │
       ├─ 命中新素材 ─────────────────────────┐
       │                                     ▼
       └─ 未命中/失败 ──► news.NewsFetcher ──► Material
                              Guardian API(有key)
                              └► RSS 池(7 源)  │
                                             ▼
                                    llm.LLM (OpenAI 兼容)
                                             │
                                             ▼
                              posts/YYYY-MM-DD.md
                              README.md 往期索引
                              data/state.json
                                             │
                          ┌──────────────────┴──────────┐
                          ▼                             ▼
                   mailer.wrap_email              git commit & push
                          │
                          ▼
                    SMTP 推送到你的邮箱
```

关键设计决策：

- **去重靠 `data/state.json`**，保留最近 60 条 bvid。同一素材不会重复推送。
- **`recent_days` 容忍窗口**（默认 3 天）。UP 主今天没更但昨天更了，依然算有效素材，不会因为时区或执行时间抖动而误触发兜底。
- **RSS 只拿到标题+导语**，正文由 LLM 基于导语扩写，并在成稿里明确标注「并非原文全文，请点击链接核对」—— 不伪装成原文。
- **B 站素材没有公开英文全文**，所以 prompt 强制要求在全文对照开头声明「以下英文基于视频主题仿写，非视频原话」，禁止伪造引语。
- **长难句解析必须照抄全文里的原句**，不能另造句子，否则解析的和全文对不上。
- **邮件发送失败不阻断 commit**。成稿已经落到仓库里了，邮件挂了不该丢内容。
- **`posts/*.md` 里保留 `^{}` 原始语法**，方便在 GitHub 上直接检索某个词的释义；只有邮件 HTML 会把它渲染成灰色小字。

---

## 三、文件结构

```
english-daily/
├── .github/workflows/daily.yml   # 定时任务定义
├── config.yaml                   # UP 主列表、兜底源、模型名（非敏感配置）
├── .env.example                  # 凭据模板
├── .gitignore
├── requirements.txt
├── README.md                     # 本文件
├── posts/                        # 成稿，按日期命名
│   └── YYYY-MM-DD.md
├── data/
│   ├── state.json                # 已推送 + 历史基线（游标锚点）
│   └── history_<mid>.json        # 历史清单快照，用 history.py 生成
└── src/
    ├── config.py                 # 配置加载（env 优先于 yaml）
    ├── bili.py                   # B 站：WBI 签名 + 两段式抓取（全量回溯 / 游标推进）
    ├── news.py                   # 兜底媒体：Guardian API + RSS
    ├── llm.py                    # LLM 调用 + prompt + 清洗
    ├── mailer.py                 # Markdown -> 邮件 HTML（含 ^{} 行内标注渲染）
    ├── smtp_send.py              # SMTP 发送
    ├── state.py                  # 状态读写（pushed + baseline）
    ├── history.py                # 历史清单工具：拉全量、按时间排序、按月统计
    └── main.py                   # 主流程编排
```

---

## 四、配置项说明

### config.yaml

| 字段 | 说明 |
| --- | --- |
| `uploaders[].name` | UP 主昵称（mid 为空时用于搜索解析） |
| `uploaders[].mid` | UP 主 UID。**留空则运行时按 name 解析**，建议直接填 |
| `uploaders[].recent_days` | 日常只认最近 N 天内容。默认 3；长视频 UP 建议 7 |
| `uploaders[].backfill_days` | **首次运行**回溯多少天建立历史基线，默认 3650（≈10 年）。只想覆盖最近半年就填 180 |
| `fallback_sources` | 兜底源 key 或直接填 RSS URL；留空用内置全部 |
| `llm_base_url` | OpenAI 兼容端点，如 `https://api.deepseek.com/v1` |
| `llm_model` | 模型名 |
| `timezone_offset` | 时区偏移，默认 8 |

### 环境变量 / GitHub Secrets

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | ✅ | OpenAI 兼容端点 |
| `LLM_API_KEY` | ✅ | 模型密钥 |
| `LLM_MODEL` | ✅ | 模型名 |
| `SMTP_HOST` | ✅ | 如 `smtp.qq.com` |
| `SMTP_PORT` | ✅ | SSL 填 465，STARTTLS 填 587 |
| `SMTP_USE_SSL` | — | `1`=465 直连 SSL，`0`=587 + STARTTLS |
| `SMTP_USER` | ✅ | 发件邮箱 |
| `SMTP_PASSWORD` | ✅ | **授权码，不是登录密码** |
| `MAIL_FROM` | — | 缺省用 `SMTP_USER` |
| `MAIL_TO` | ✅ | 收件人，多个用逗号分隔 |
| `BILI_COOKIE` | 强烈建议 | 见下方「风控」章节 |
| `BILI_MIN_INTERVAL` | 否 | 请求最小间隔秒数，默认 1.5。**别调小** |
| `BILI_JITTER` | 否 | 随机抖动上限秒数，默认 0.8 |
| `GUARDIAN_API_KEY` | 否 | 有则用全文，效果更好 |
| `DRY_RUN` | 否 | `1`=只生成不发邮件 |
| `FORCE_FALLBACK` | 否 | `1`=跳过 B 站强制兜底 |

---

## 五、部署步骤

### 1. 推送仓库

```bash
cd english-daily
git init && git add -A && git commit -m "init: english daily digest"
git remote add origin git@github.com:<你的用户名>/<仓库名>.git
git push -u origin main
```

### 2. 本地先跑通

```bash
cp .env.example .env     # 填入 LLM 和邮件配置
pip install -r requirements.txt
python src/main.py --dry-run     # 只生成不发邮件
```

### 3. 配置 GitHub Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret，逐个添加：

`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`SMTP_HOST`、`SMTP_PORT`、`SMTP_USE_SSL`、`SMTP_USER`、`SMTP_PASSWORD`、`MAIL_FROM`、`MAIL_TO`、`BILI_COOKIE`、`GUARDIAN_API_KEY`

### 4. 填 UP 主

编辑 `config.yaml` 的 `uploaders`，填上 UP 主昵称和 mid。

### 5. 手动触发一次验证

Actions → Daily English Digest → Run workflow。绿了之后就不用管了。

---

## 六、风控说明（重要）

**先说结论：会风控，GitHub Actions 也一样。**

B 站的风控分三层，本项目对应三层应对：

| 层级 | 表现 | 本项目的应对 |
| --- | --- | --- |
| **IP 层** | 412 Precondition Failed | 请求间强制 1.5~2.3 秒随机间隔；失败时指数退避重试 |
| **频率层** | 短时间大量请求被识别为机器行为 | 全程串行 + 随机抖动；view 补详情只补真正缺字段的条目 |
| **身份层** | 未登录请求被限制 | 配置 `BILI_COOKIE`（最有效的一项） |

**GitHub Actions 的 runner 是数据中心 IP（Azure/AWS），对高频请求通常比家用 IP 更敏感。**
所以本项目默认开启节流，首次全量回溯 100 条视频会跑 4~6 分钟——这是刻意的，
把请求摊开比快速跑完更不容易被拦。workflow 超时已放宽到 40 分钟。

**实测数据（本机 2026-10-14）**：
- 未加节流时，5 线程并发补详情 → 同一分钟 IP 就被盯上，从可用变成 412
- 改为串行 + 1.5~2.3 秒随机间隔后，view 接口稳定可用
- WBI 投稿列表接口始终间歇可用（该 IP 后来被持续风控，加 Cookie 后可缓解）

**提高成功率的做法，按性价比排序：**

1. **配置 `BILI_COOKIE`** —— 浏览器登录 B 站 → DevTools → Network → 任意 `api.bilibili.com` 请求 → Request Headers → 复制整段 Cookie。**只要匿名设备标识 `buvid3` / `buvid4` / `b_nut` / `bili_ticket`**，把 `SESSDATA`、`bili_jct`、`DedeUserID` 三段删掉（它们是登录态凭证，抓公开视频用不上，泄漏等于账号被盗）。可用 `tools/clean_cookie.py` 自动清洗。完整说明见 **[COOKIE.md](COOKIE.md)**。`bili_ticket` 只活几小时~几天，连续几天「暂无新素材」就该重抓。
2. **不要调小节流间隔** —— `BILI_MIN_INTERVAL` 默认 1.5 秒，本机调试时可临时调到 3。调太小反而更容易被拦。
3. **接受降级** —— 三条路径（动态接口 / 投稿列表 / 视频详情）任一可用即可出内容。全失败则自动走兜底媒体源，当天仍能收到一篇精读稿，只是开头标注「今日暂无新素材」。

> **IP 风控通常会随时间自行解除。** 如果某天突然全量失败，多半是 IP 暂时被标记，等几个小时或换个网络环境再跑即可，不必立刻怀疑代码有问题。

---

## 七、常用命令

```bash
python src/main.py                      # 正常跑
python src/main.py --dry-run            # 不发邮件、不写 state
python src/main.py --force-fallback     # 跳过 B 站，直接用媒体源（调试兜底用）
```

在 Actions 页面勾选 `force_fallback` 同样能强制走兜底，用来验证兜底链路是否正常。
## 往期

| 日期 | 字节 |
| --- | --- |
| 2026-10-25 | 11,801 |
| 2026-10-24 | 9,182 |
| 2026-10-23 | 9,410 |
| 2026-10-22 | 13,823 |
| 2026-10-21 | 13,045 |
| 2026-10-20 | 10,097 |
| 2026-10-19 | 12,379 |
| 2026-10-18 | 11,475 |
| 2026-10-17 | 12,120 |
| 2026-10-16 | 9,637 |
| 2026-10-15 | 10,129 |
| 2026-10-14 | 11,702 |
