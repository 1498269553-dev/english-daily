# B 站 Cookie 完全指南

**怎么用、为什么要用、有什么风险、怎么发现泄漏、泄漏了怎么办。**

> 配套工具：`tools/clean_cookie.py`（自动识别敏感字段并生成安全版 Cookie）

---

## 目录

1. [为什么需要 Cookie](#1-为什么需要-cookie)
2. [怎么拿 Cookie](#2-怎么拿-cookie)
3. [Cookie 里都有什么](#3-cookie-里都有什么)
4. [风险到底有多大](#4-风险到底有多大)
5. [最小化方案：只留必要字段](#5-最小化方案只留必要字段)
6. [如何发现是否泄漏](#6-如何发现是否泄漏)
7. [泄漏了怎么办](#7-泄漏了怎么办)
8. [失效与轮换](#8-失效与轮换)
9. [速查卡](#9-速查卡)

---

## 1. 为什么需要 Cookie

### 1.1 B 站的风控逻辑

B 站判断一个请求"是不是机器人"，主要看三样东西：

| 依据 | 说明 | 我们处于什么状态 |
| --- | --- | --- |
| **IP 信誉** | 数据中心 IP（Azure/AWS/阿里云）天然低信誉 | ❌ GitHub Actions 就是数据中心 IP，天生吃亏 |
| **Cookie 完整度** | 有没有 `buvid3`、`bili_ticket` 这类设备指纹 | ⚠️ 不配就是"裸奔" |
| **请求行为** | 频率是否规律、有没有 Referer/UA | ✅ 已加随机节流 1.5~2.3 秒 + 完整 UA/Referer |

三样里我们只能控制后两样，所以 **Cookie 是唯一能补的短板**。

### 1.2 实测数据（2026-10-14，本项目的真实结果）

| 场景 | 投稿列表接口 | 结果 |
| --- | --- | --- |
| 无 Cookie、家用 IP | 时好时坏，同一分钟内先返回数据后返回 412 | 约 50% |
| 无 Cookie、数据中心 IP（GitHub Actions） | 频繁 412 | **很低** |
| 有 `buvid3` + `bili_ticket` | 成功率明显上升 | 可用 |

返回码含义：

| code | 含义 |
| --- | --- |
| `0` | 成功 |
| `412` | **被风控拦截**（最常见，就是它导致抓不到） |
| `-352` | 风控二次校验 |
| `-799` | 请求过于频繁 |
| `-101` | 未登录（部分接口正常反应，不算失败） |

### 1.3 不配会怎样

**不会报错，但会静默降级**：

```
B 站抓取失败（412）
  → 自动走兜底新闻源
  → 成稿开头标「今日暂无新素材」
  → 你每天收到的是 Guardian / BBC 新闻，不是你关注的那位 UP 主
```

项目还能用，但数据源不是你要的。这也是为什么它被列为"强烈建议"而非"必填"。

### 1.4 代码里是怎么用的

`src/bili.py` 的 `__post_init__`：

```python
if self.cookie:
    self._session.headers["Cookie"] = self.cookie
    log.info("已加载 B 站 Cookie（%d 字符）", len(self.cookie))
else:
    log.warning("未配置 BILI_COOKIE：请求成功率会明显下降，建议配置")
```

**只做一件事：把整串塞进请求头。** 程序不会解析、不会上传、不会写入任何文件，
也不会用它去做登录态相关的操作（发评论、点赞之类）——我们只要公开视频列表。

> 关键结论：**抓取公开视频列表根本不需要登录态**。
> 需要的是设备指纹（`buvid3`）+ 临时票据（`bili_ticket`），跟"你是不是登录用户"无关。
> 这就是下面第 5 节"最小化方案"能成立的原因。

---

## 2. 怎么拿 Cookie

### 方法一：F12 Network 面板（推荐，最通用）

适用于 Chrome / Edge / Firefox。

1. 浏览器打开 <https://www.bilibili.com>
   - **建议登录**，登录状态下 Cookie 字段更全（含 `bili_ticket`）
   - 不登录也行，但可能缺 `bili_ticket`，效果差一些
2. 按 `F12` 打开开发者工具 → 切到 **Network（网络）** 标签
3. 按 `F5` 刷新页面（必须刷新，否则面板是空的）
4. 上方 **Filter / 筛选** 框输入 `api.bilibili.com`
5. 左侧列表里**随便点一个请求**（比如 `nav` 或 `web-interface`）
6. 右侧切到 **Headers** → 往下找 **Request Headers** 区块
7. 找到 `cookie:` 这一行 → **右键 → Copy value**

复制到的长这样：

```
buvid3=A1B2C3D4-1234-5678-9abc-def01234567812345infoc; b_nut=1728888888;
bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6...; buvid4=...;
SESSDATA=8f3a2b1c%2C17...%2C12345%2C...; ...
```

⚠️ **不要包含 `cookie:` 这个词本身**，只取冒号后面那一串。

### 方法二：Application 面板（更直观，字段可单独复制）

1. `F12` → **Application**（Chrome）/ **存储**（Edge）标签
2. 左侧 **Storage → Cookies → https://www.bilibili.com**
3. 表格里就是所有 Cookie，能看到每个字段的 **Name / Value / Expires**
4. 想看某个字段的值：点一下 Value 列，或双击后复制

**好处**：能直接看到 `SESSDATA` 的过期时间，方便判断还剩多久失效。

### 方法三：不登录拿"游客 Cookie"

如果只是想要 `buvid3`：

1. 用**无痕窗口**打开 bilibili.com（确保没登录）
2. 按方法一的步骤复制
3. 此时得到的是游客 Cookie，**天然不含 `SESSDATA`** —— 最安全

代价：可能缺 `bili_ticket`，过风控能力略弱。可以先试这个，不行再换登录版。

### 复制时的三个坑

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 值里有 `%2C` `%3A` 等百分号 | 拿到的是 URL 编码版 | 重新复制一次；或用方法一而不是从地址栏复制 |
| 只有一小段，很短 | 点到了静态资源（js/css）而不是 API 请求 | 必须筛 `api.bilibili.com` |
| 复制出来带换行 | 从多行文本框复制的 | 粘进 Secret 前先粘到记事本，确认是一整行 |

---

## 3. Cookie 里都有什么

典型的一串 B 站 Cookie 包含这些字段。**按敏感度分级**：

| 字段 | 是什么 | 敏感度 | 抓视频要不要 |
| --- | --- | --- | --- |
| `buvid3` | **设备指纹**，B 站给你发的匿名 ID | 🟢 无风险 | ✅ **核心，必须有** |
| `buvid4` | 设备指纹补充 | 🟢 无风险 | ✅ 建议留 |
| `b_nut` | 首次访问时间戳 | 🟢 无风险 | ✅ 建议留 |
| `bili_ticket` | **临时风控票据**，JWT 格式，几小时~几天过期 | 🟢 无风险 | ✅ **核心，必须有** |
| `buvid_fp` | 浏览器指纹（Canvas 等生成的一串哈希） | 🟡 低（指纹，非身份） | ⭕ 可选 |
| `fingerprint` | 同上，指纹种子 | 🟡 低 | ⭕ 可选 |
| `CURRENT_FNVAL` | 播放器功能开关 | 🟢 无 | ⭕ 可选 |
| `sid` | 会话 ID | 🟡 低 | ⭕ 可选 |
| ⚠️ **`SESSDATA`** | **登录态凭证** | 🔴 **等价于账号密码** | ❌ **删除** |
| ⚠️ **`bili_jct`** | **CSRF Token**，配合 SESSDATA 可发请求 | 🔴 **高危** | ❌ **删除** |
| ⚠️ **`DedeUserID`** | **你的 B 站 UID**（明文数字） | 🟠 隐私 | ❌ 删除 |
| ⚠️ **`DedeUserID__ckMd5`** | UID 的校验值 | 🟠 隐私 | ❌ 删除 |
| ⚠️ **`sid`（登录版）** | 登录会话 ID | 🟠 中 | ❌ 删除 |

**记住这条线**：

```
buvid3 / buvid4 / b_nut / bili_ticket  →  匿名设备标识，留着，无害
SESSDATA / bili_jct / DedeUserID       →  身份凭证，删掉，抓视频用不上
```

---

## 4. 风险到底有多大

### 4.1 SESSDATA 是什么

`SESSDATA` 是 B 站**在你登录后下发的会话凭证**。
它的本质是一把"已经验证过身份的钥匙"——**拿到它的人不需要知道你的密码**，
把这段字符串塞进自己的请求头，B 站就认为"这个请求就是你本人发的"。

它的典型格式：

```
SESSDATA=8f3a2b1c%2C17xxxxxxx%2C12345%2Cabc...
                  ↑ 这里面编码了你的 UID 和有效期
```

### 4.2 拿到它能干什么

| 能做的 | 严重度 |
| --- | --- |
| 以你的身份**发动态、发评论、发弹幕** | 🔴 高 |
| **点赞、投币、收藏、关注/取关** | 🔴 高 |
| 修改个人资料（头像、签名） | 🔴 高 |
| 查看**私信、历史记录、观看记录** | 🔴 高 |
| 查看大会员状态、消费记录 | 🟠 中 |
| **改绑手机/邮箱**（可能需要二次验证，不保证） | 🔴 极高 |
| 盗号后进一步社工（用你账号骗好友） | 🔴 高 |

**一句话：SESSDATA 泄漏 ≈ 账号被盗，但不一定能改密码。**

### 4.3 在本项目里，风险"被关在笼子里"

| 环节 | 是否安全 | 说明 |
| --- | --- | --- |
| 存在 GitHub Secrets | ✅ 安全 | 加密存储，**只写不可读**——连你自己打开网页都看不到明文，只能覆盖 |
| 仓库公开 | ✅ 安全 | 代码里只有 `${{ secrets.BILI_COOKIE }}` 占位符，运行时才替换，公开也读不到值 |
| 传输到 Actions | ✅ 安全 | GitHub 内部注入，不落盘 |
| 程序运行 | ✅ 安全 | 只放进请求头发给 bilibili.com，不外传 |
| ⚠️ **你自己这一端** | ❌ **唯一的风险点** | 见下 |

**真正的漏洞从来不是 GitHub，是你自己这一端**：

1. **本地 `.env` 没 gitignore 干净** → 一次 `git add -A` 就进仓库了
2. **把 Cookie 贴到了公开地方**（论坛提问、GitHub Issues、截图没打码发群里）
3. **截图发给我时没打码**（本次会话里你就是这么操作的，虽然是私聊，习惯要改）
4. 多人共用电脑 / 电脑中毒

> 这就是为什么文档反复强调"删掉 SESSDATA"——
> **把最坏情况的损失从"账号被盗"降到"几乎为零"**，成本只是复制后删一段。

### 4.4 如果仓库已经公开了

公开仓库**不会泄漏 Secrets**，这点可以放心。但要确认一件事：
**有没有哪次提交把 Cookie 写进了文件？** 检查方法见第 6 节。

---

## 5. 最小化方案：只留必要字段

### 5.1 手工删（30 秒）

Cookie 是一串 `key=value; key=value;`。
找到 `SESSDATA=` 开头、到**下一个 `;`** 为止的整段，删掉。

**前**：

```
buvid3=ABC-123infoc; b_nut=1728888888; bili_ticket=eyJhbG...;
SESSDATA=8f3a2b1c%2C17xxx%2C12345%2Cabc...; bili_jct=5f2e...;
DedeUserID=12345678; DedeUserID__ckMd5=9a8b...; buvid4=DEF-456...
```

**后**（这就是最终要粘进 Secret 的）：

```
buvid3=ABC-123infoc; b_nut=1728888888; bili_ticket=eyJhbG...; buvid4=DEF-456...
```

⚠️ `SESSDATA` 的值里常带 `%2C` `%3A`，**别只删一半**——一定要删到下一个分号为止。

### 5.2 用工具自动删（推荐，不会漏）

项目里带了清洗工具：

```bash
# 方式一：管道
python tools/clean_cookie.py "$(cat cookie.txt)"

# 方式二：直接传（注意引号）
python tools/clean_cookie.py "buvid3=xxx; b_nut=xxx; SESSDATA=xxx; bili_jct=xxx"

# 只做体检，不输出清洗结果
python tools/clean_cookie.py --check "buvid3=xxx; SESSDATA=xxx"
```

输出示例：

```
字段体检：
  buvid3                 🟢 保留   设备指纹（必需）
  b_nut                  🟢 保留   首次访问时间戳
  bili_ticket            🟢 保留   风控票据（必需）
  SESSDATA               🔴 删除   登录态凭证，等价账号密码
  bili_jct               🔴 删除   CSRF Token
  DedeUserID             🟠 删除   你的 B 站 UID

⚠️ 发现 3 个敏感字段，已移除。

清洗后（共 4 个字段，118 字符）：
──────────────────────────────────────────────────────────
buvid3=xxx; b_nut=xxx; bili_ticket=xxx; buvid4=xxx
──────────────────────────────────────────────────────────
↑ 复制这一行粘到 GitHub Secret 的 BILI_COOKIE
```

### 5.3 更新 Secret

1. 仓库 → **Settings** → **Secrets and variables** → **Actions** → **Secrets**
2. 点列表里的 `BILI_COOKIE`
3. 点右上角 **Update secret**
4. 粘贴清洗后的那一行 → **Update secret**

---

## 6. 如何发现是否泄漏

按"从最可能到最不可能"的顺序检查，前两项 2 分钟能查完。

### 检查 1：本地仓库有没有把 Cookie 写进文件 ⭐ 最重要

```bash
cd D:/WorkBuddyData/2026-10-14-10-35-29/english-daily

# 扫描当前所有被跟踪的文件
git grep -niE "SESSDATA|bili_jct|DedeUserID" $(git rev-parse HEAD) -- . | head

# 扫描整个 git 历史（含已删除的文件）
git log -p --all -S "SESSDATA" -- . | grep -i "SESSDATA" | head
```

- **第一条无输出** → 当前代码干净 ✅
- **第二条无输出** → 历史里也从来没有过 ✅

如果第二条有输出，说明某次提交真的写进去过，必须按第 7 节处理。

### 检查 2：本地 `.env` 是否安全

```bash
# 看 .gitignore 有没有排除 .env
grep -n "\.env" .gitignore

# 确认 .env 确实没被跟踪（无输出 = 安全）
git ls-files | grep "^\.env$"
```

`git ls-files` 无输出 = 安全 ✅

### 检查 3：B 站登录设备管理（看有没有异地登录）

1. B 站网页 → 右上角头像 → **设置**
2. 左侧 **安全隐私** → **登录设备管理**
3. 看列表里的**设备、IP 归属地、登录时间**

⚠️ **需要重点警惕**：出现你没用过的设备，或归属地是**境外 / 你没去过的城市**。

> 注意：GitHub Actions 用的是 Cookie 而非账号密码登录，
> **不会**在这里产生登录记录。所以这里出现陌生设备 = 真被盗。

### 检查 4：看账号有没有异常行为

- **我的动态**：有没有你没发过的动态
- **历史记录 / 稍后再看**：有没有陌生视频
- **关注列表**：有没有多出你不认识的人
- **我的钱包 / 大会员**：有没有异常消费

### 检查 5：Cookie 是否还有效（顺带确认是否被别人在用）

用清洗前的完整 Cookie 跑一次：

```bash
python -c "
import sys; sys.path.insert(0,'.')
from src.bili import Fetcher
f = Fetcher(cookie='这里粘完整Cookie')
info = f._json('https://api.bilibili.com/x/web-interface/nav',
               'https://www.bilibili.com/', allow_codes={-101})
print(info)
"
```

- `data.isLogin: true` → Cookie 有效（说明你复制时是登录状态）
- `data.isLogin: false` → 已失效或本来就是游客 Cookie

---

## 7. 泄漏了怎么办

**按顺序做，前三步 5 分钟内能完成。**

### 第 1 步：让旧 Cookie 立刻失效（最关键）

> **改密码。** 这是唯一能保证所有会话立刻失效的办法。

1. B 站 → **设置 → 安全隐私 → 账号安全 → 修改密码**
2. 改完后，**所有已下发的 `SESSDATA` 立即作废**，旧的那串变成废纸

如果暂时改不了密码，退而求其次：

**设置 → 安全隐私 → 登录设备管理 → 退出所有设备**

### 第 2 步：把泄漏的内容删掉

- **在 GitHub**：删掉那个 Secret（`BILI_COOKIE` → Remove），重新生成一个干净的
- **在 git 历史里**：`git filter-repo` 重写历史（会改变所有 commit hash，要强推）
  ```bash
  git filter-repo --replace-text <(echo "SESSDATA=xxx==>REMOVED")
  git push --force
  ```
  > 强推前务必备份。**改公开之前做这件事**，公开之后再删就已经被人爬走了。
- **在聊天记录 / 截图里**：能删就删，B 站工单里提一下

### 第 3 步：检查损失

按第 6 节检查 3、4 走一遍：登录设备、动态、关注列表、钱包。
发现异常内容（陌生动态、陌生关注）手动删掉。

### 第 4 步：亡羊补牢

- 开启 B 站**登录二次验证**（设置 → 安全隐私 → 二次验证）
- 以后复制 Cookie **先删 SESSDATA 再用**，形成习惯
- 本地 `.env` 用完即删，或至少确认被 `.gitignore` 排除

---

## 8. 失效与轮换

### 8.1 不同字段的寿命不一样

| 字段 | 大概寿命 | 影响 |
| --- | --- | --- |
| `bili_ticket` | **几小时 ~ 几天** | 过期后风控能力下降，412 变多 |
| `buvid3` / `buvid4` | 很久（接近永久） | 基本不用管 |
| `b_nut` | 永久 | 不用管 |
| `SESSDATA` | 约半年 | 反正建议删掉 |

**关键点**：真正决定成败的是 `bili_ticket`，而它是**短命**的。
所以"配一次管一年"这种想法不成立。

### 8.2 怎么判断该换了

出现下面任一情况就该重抓：

- 连续 3 天以上成稿都是「今日暂无新素材」，而 UP 主其实有更新
- Actions 日志里 `B 站结果：` 显示「抓取异常」或 `412`
- 距上次更换超过 **3 个月**

### 8.3 排查顺序（别一上来就换 Cookie）

```
1. 看 Actions 日志里「B 站结果：」那一行
   ├─ 显示「最近 N 天无更新」→ 正常，UP 主真没发，不用管
   ├─ 显示「抓取异常」      → 继续第 2 步
   └─ 显示「命中 BVxxx」    → 成功，不用管

2. 手动 Run workflow 一次
   ├─ 成功 → 只是偶发风控，不用管
   └─ 失败 → 继续第 3 步

3. 重抓 Cookie（记得删 SESSDATA）
```

---

## 9. 速查卡

```
┌──────────────────────────────────────────────────────────┐
│  B 站 Cookie 速查                                          │
├──────────────────────────────────────────────────────────┤
│  拿：bilibili.com → F12 → Network → 刷新                  │
│      → 筛 api.bilibili.com → 点任一请求                   │
│      → Headers → Request Headers → cookie → Copy value    │
│                                                            │
│  删：去掉 SESSDATA=...;  bili_jct=...;  DedeUserID=...;    │
│                                                            │
│  留：buvid3, buvid4, b_nut, bili_ticket                    │
│                                                            │
│  填：Settings → Secrets and variables → Actions            │
│      → Secrets → BILI_COOKIE → Update secret               │
│                                                            │
│  查泄漏：git log -p --all -S "SESSDATA" -- .               │
│          （无输出 = 干净）                                  │
│                                                            │
│  泄漏后：改密码（最有效）→ 删 Secret → 查登录设备           │
│                                                            │
│  换：bili_ticket 只活几天~几小时，                          │
│      连续 3 天「暂无新素材」就该重抓                        │
└──────────────────────────────────────────────────────────┘
```

---

## 附：为什么抓公开视频不需要登录态

B 站的接口分两类：

| 类型 | 举例 | 是否需要 SESSDATA |
| --- | --- | --- |
| **公开读接口** | 视频详情 `x/web-interface/view`<br>投稿列表 `x/space/wbi/arc/search`<br>UP 主信息 | ❌ 不需要。判别你是人是机器靠 `buvid3` + `bili_ticket` |
| **用户态接口** | 发评论、点赞、投币、看私信、历史记录 | ✅ 需要 |

本项目**只用第一类**。所以：

- 留 `buvid3` + `bili_ticket` → 能过风控，拿到公开数据
- 删 `SESSDATA` → 拿不到你的身份，也做不了任何用户态操作
- **两头都占**：功能不打折，风险降到接近零

这就是"删 SESSDATA"能成立的完整理由。
