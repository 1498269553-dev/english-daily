# -*- coding: utf-8 -*-
"""调用 OpenAI 兼容接口，把素材加工成中英对照学习短文。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位资深的英语学习素材编辑，同时精通中文表达。"
    "你为中文母语的英语学习者制作每日精读材料，风格严谨、克制、具体。"
    "只输出 Markdown 正文，不要输出任何解释性前后缀，不要使用代码块包裹全文。"
)

STYLE_RULES = """
写作规范（必须严格遵守）：

## 整体结构
小节顺序固定，不得调换，不得缺失：
1. `## 全文对照`  —— 必须第一个出现
2. `## 生词与短语`
3. `## 长难句解析`
4. `## 核心内容摘要`
5. `## 背诵例句`

只输出 Markdown，标题从 `##` 开始，不要出现 `# ` 一级标题，不要用代码块包裹全文。

## 一、全文对照（最重要）
这是全文的地基，读者要靠它才知道文章到底讲了什么。
1. 给出**完整原文**，不得删减、不得概括、不得只给片段。原素材有多长就写多长。
2. 按自然段落切分，段落数与原文一致，不要合并。
3. 每段英文原文下方紧跟中文翻译，中文另起一段。
4. **行内生词标注是硬性要求**：在原文中不常用、超纲、或值得背诵的单词/短语下方标注中文释义。
   语法固定为 `英文原词^{中文释义}`，例如：`The rabbit^{兔子} dashed^{猛冲} ahead^{向前}`。
   渲染后中文会显示为小号浅色字紧跟英文词，读者一眼能分辨这是注释而非原文。
   标注规则：
   - 必须标注：
     (a) B1-B2 阶段不认识的实义词、有固定搭配的短语、含一词多义的词、
         学术/新闻常见术语、逻辑关系词（rather than / despite / unless / whereas 等）
     (b) **中高考大纲核心词**——即使字面简单也要标，但要标注其**本语境下的义项**，
         例如 `developed^{发展成熟的（此处非「已开发」）}`、`relationship^{关系}`、
         `protect^{保护}`、`result from^{源于}`、`involve^{涉及}、`    这类词中国学生通常只会直译，标注时点出真实用法或易错点
   - 禁止标注：冠词、介词、代词、数词
   - 段落开头若出现高频核心词，优先标它，而不是先标生僻词
   - 一段内标注 6-14 个，宁可少而准，绝不逐词翻译
   - `^{}` 内只写中文释义，不要写音标，不要嵌套括号
5. 中文翻译要自然准确，允许意译，但不得漏译关键信息、不得添加原文没有的内容。
6. 全文后追加一行 `**字数**：约 N 词`（N 为原文实际词数）。

## 二、生词与短语
这一节必须分成**两张表**，中间用 `### 高频核心词` 和 `### 拓展词与短语` 两个三级标题隔开。

### 高频核心词（6-8 个，必须给足）
这是本节的重点。收录**中国中高考英语大纲里出现过、但很多学生 STILL 没真正掌握**的高频核心词。

判断标准 —— 满足以下任一条即入选：
- 中考/高考大纲核心词，且在原文中反复出现或承担关键语义
- 看起来简单、但中国学生普遍用错或只会直译的词，例如：
  develop / developed / relationship / protect / result / cause / consider /
  describe / involve / provide / remain / suggest / affect / compare / recognize /
  establish / maintain / allow / avoid / achieve / require / expect
- 一词多义且原文用的是非最常见义项，例如 `develop` 当「发展」讲，
  而非「开发者」（程序员语境）；`issue` 当「问题/议题」讲，而非「发行」
- 有固定搭配的常用动词短语，例如 `protect ... from ...`、`result from`（因果）
  与 `result in`（结果）方向相反这类易混点

表格格式：`| 单词 | 音标 | 词性与释义 |`
释义栏必须写清**本语境下的义项**，并对易错点加简短提醒，例如：
`develop | v. 发展；开发（此处指社会形态演进，不是「开发者」）`

表格后用列表给 2-3 个搭配或例句，指出常见搭配和错误用法。

### 拓展词与短语（6-8 个）
收录原文里地道的学术/新闻词汇、固定短语。这一部分沿用传统：
表格格式：`| 单词/短语 | 音标 | 词性与释义 |`，表格后给 1 个搭配或例句。

两张表都要**只从全文对照里出现过的词中选**，不得杜撰原文没有的词。

## 三、长难句解析
挑 2-3 个原文中最难的**完整句子**（必须是全文里真实出现的句子），逐句给出：
- 句子原文（照抄全文中的原句）
- 语法结构拆分：主干 / 从句 / 修饰成分，逐层拆开
- 中文翻译
- 为什么难：具体指出难点（插入语干扰主干、连字符复合形容词、多重后置定语等）

## 四、核心内容摘要
分 3-5 个要点，每点先用英文关键词开头，再中文说明。
这一节回答「文章讲了什么」，不能与全文对照重复堆砌句子。

## 五、背诵例句
给 6-8 组中英对照例句，主题必须紧扣本篇内容。
最后一组必须是「可直接套用的写作模板句型」，用 `【写作模板】` 开头。

## 通用要求
- 严格区分事实与推测，不虚构原文没有的数据、人名、引语
- 中文用简体中文；英文原文片段保持原样，不做翻译腔改写
- 如果素材是视频或动态（无公开英文文本），必须在全文对照开头声明
  「以下英文文本基于视频主题仿写，非视频原话」，并让仿写文本贴近该主题的常见表达
"""


@dataclass
class Material:
    """送给 LLM 的原始素材。"""

    kind: str                 # video | dynamic | news
    title: str
    url: str
    source: str
    published: str = ""
    body: str = ""
    author: str = ""

    def to_prompt(self) -> str:
        head = f"素材类型：{self.kind}\n标题：{self.title}\n来源：{self.source}"
        if self.author:
            head += f"\n作者/UP主：{self.author}"
        if self.published:
            head += f"\n发布时间：{self.published}"
        head += f"\n链接：{self.url}\n\n素材正文：\n{self.body or self.title}"
        return head


@dataclass
class LLM:
    base_url: str
    api_key: str
    model: str
    timeout: int = 120

    def _endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def complete(self, user_prompt: str, max_tokens: int = 4000, temperature: float = 0.6) -> str:
        if not (self.base_url and self.api_key and self.model):
            raise RuntimeError("LLM 配置不完整：需要 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(
            self._endpoint(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:400]}")
        data = r.json()
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM 响应结构异常: {str(data)[:300]}") from exc


def sanitize(md: str) -> str:
    """去掉模型可能带出的围栏与前言尾巴。"""
    md = md.strip()
    md = re.sub(r"^```(?:markdown|md)?\s*", "", md)
    md = re.sub(r"\s*```$", "", md)
    # 去掉开头的客套话
    md = re.sub(r"^(好的|以下是|下面是|我为你)[^\n]{0,80}[：:]\s*\n", "", md)
    return md.strip()