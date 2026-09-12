---
name: video-digest
version: 1.1.4
description: 视频深读——把没时间看的 YouTube 视频提炼成中文结构化笔记：概述主要内容、按主题整理成文、区分🧱事实与💭观点、附原链接+时间戳可跳回，支持追问深挖与内容平台选题素材。仅在用户提供 YouTube 链接/视频 ID 或明确说「视频深读 <链接>」时使用。抓 YouTube 字幕→中文笔记（默认中文，用户可指定其他输出语言），落盘可复用。笔记生成由执行本 skill 的 AI 按模板完成，脚本只负责抓取。英文 AI/科技/访谈/TED/讲座效果最佳。需要 python3 + yt-dlp + 网络可达 YouTube（本机代理或可直连）。
agent_created: true
metadata: { "openclaw": { "requires": { "bins": ["python3"], "env": ["HTTPS_PROXY"] }, "install": [ { "kind": "uv", "package": "yt-dlp", "bins": ["yt-dlp"] } ] } }
---

# 视频深读 (video-digest)

把"没时间看的 YouTube 优质视频"变成「能 5 分钟读完、可跳回原片、可追问深挖、可当选题素材」的中文结构化笔记。适合英文 AI/科技类长视频、访谈、讲座。

## 触发场景

**仅当用户消息里出现 YouTube 链接/视频 ID，或明确说「视频深读 <链接>」时才激活**。示例形态：

- `youtube.com/watch?v=` / `youtu.be/` / `youtube.com/shorts/` 开头的链接
- 裸视频 ID（如 `dQw4w9WgXcQ`）
- 明确命令：「视频深读 <链接>」「深读 <链接>」

如果用户只是泛泛说"总结这个视频""这个视频讲了什么"而没有给链接/ID：先请用户提供链接，**不要**自行猜测或触发抓取。抓取前脚本会再次校验 URL 属于 YouTube 域名，非 YouTube 输入直接拒绝。

## 快速开始

丢一条链接即可（模式 A）。示例：
> 视频深读 https://www.youtube.com/watch?v=zjkBMFhNj_g

多条链接（≥2）自动走模式 B 批量扫描。

## 权限边界（最小权限声明）

本 skill 只用以下能力，且用途单一：**抓 YouTube 字幕 → 落盘中文笔记**。

- **网络访问**：仅限抓取 YouTube 元数据/字幕（youtube.com / youtu.be）；优先走用户本机代理（127.0.0.1 常见端口），不可用时直连。**无凭据的本地代理（最常见）命令行里只出现 host:port，凭据零暴露**；带凭据的代理会打印明确提示（受限于 yt-dlp 仅支持参数传代理）。代理 URL 打印/落盘前一律脱敏（剥 userinfo）
- **shell 执行**：仅运行本 skill 自带的 `scripts/fetch_video.py`（内部调 yt-dlp）与 `scripts/retrieve.py`（检索），不执行任意其它命令
- **文件读写**：仅在笔记输出目录写文件（默认 `~/Documents/video-notes/<频道>/<video-id>/`，可用 `--out` 指定）；`retrieve.py` 只读取用户在会话中明确指定的 transcript 路径（默认约定在笔记输出目录内），越界路径会打印透明提示
- **环境变量**：只读 `HTTPS_PROXY`/`https_proxy` 作为代理候选；代理 URL 打印/落盘前会**脱敏**（剥掉 userinfo，凭据绝不落盘）；无凭据代理的命令行参数里不含任何敏感值
- **输入校验**：只接受 YouTube 链接或合法 video_id；非 YouTube 域名/非法 ID 直接拒绝，不交给 yt-dlp，不参与路径拼接

## 人机分工（架构说明）

「抓字幕 → 中文笔记」由两部分协作完成，这是设计而非缺失：
- **代码（scripts/）**：只负责抓取——校验输入、探测网络、调用 yt-dlp 获取元数据与字幕、解析为带时间戳的 transcript.txt。不含文本生成逻辑
- **AI（执行本 skill 的智能体）**：读取 transcript 与 `references/note_template.md`，完成结构化笔记、事实/观点分层、追问检索作答、选题角度——笔记能力以提示词规范实现，落在 SKILL.md 与模板文件里

## 依赖与前置

- 网络：脚本自动探测本机代理（Clash/V2ray，常见端口 7897/7890/1087）；探测不到会自动试直连 YouTube，直连可用则走直连；两者都不通才报错退出。海外网络/企业出口可直连的环境，可加 `--direct` 跳过代理探测
- 需要 yt-dlp：脚本自动定位托管 venv（`~/.workbuddy/binaries/python/envs/default/bin/python`）；若提示找不到，安装：`pip install yt-dlp`
- 无字幕的视频（无手动字幕也无自动字幕）→ 明确告知无法提炼，不做本地转写

## 抓取脚本用法

```bash
# 单条(模式 A)
python <skill_dir>/scripts/fetch_video.py "<youtube_url>"

# 批量(模式 B,多条一次抓,代理只探测一次)
python <skill_dir>/scripts/fetch_video.py url1 url2 url3

# 复用存档(已有 transcript 则跳过,模式 C 追问前用)
python <skill_dir>/scripts/fetch_video.py "<url>" --skip-existing

# 直连(不走代理探测;海外网络或企业出口可直连 YouTube 时用)
python <skill_dir>/scripts/fetch_video.py "<url>" --direct

# 可选参数: --out <目录>(默认 ~/Documents/video-notes) --langs en,zh
```

脚本产出（`~/Documents/video-notes/<频道>/<video-id>/`）：
- `meta.json` — 标题/频道/时长/简介/原链接/章节(chapters)/字幕语言
- `transcript.txt` — 带 `[MM:SS]` 时间戳的连贯文本（已做 ASR 滚动窗口融合去重，每行≈1 个完整语义句块）

退出码：0 成功/跳过 | 2 环境不可用(代理/yt-dlp) | 3 视频不可达 | 4 无字幕。stdout 关键行：`PROXY:`、`NET:`（直连模式）、`✓ OK`、`⏭ 跳过`、`⚠ 无字幕`、`✗ ERROR`、`DIR:`。批量时单条失败不中断，末尾有汇总。

## 示例样张（references/examples/）

- `example_ted_conversation.md` — TED 演讲（手动字幕,11min）：完整深读笔记范本
- `example_vllm_shorts.md` — YouTube Shorts（自动字幕,3min）：短视频轻量笔记范本
- 真实抓取输出见 `~/Documents/video-notes/<频道>/<video-id>/note.md`，结构与样张一致

## 四种模式

### 模式 A · 单条深读（默认）

1. 跑抓取脚本拿 meta + transcript（脚本会打印进度，正常单条约 10-30 秒）
2. 读 transcript（若 >30k token 先切块小节概述再合并，见"长视频"）
3. 按 `references/note_template.md` 模板产出中文笔记，对话内交付
4. 把笔记存为 `<video-notes>/<频道>/<video-id>/note.md`（脚本已建好目录，直接写文件），供模式 C 复用
5. **落盘后回读校验**：确认 note.md 确实写入且非空（文件存在 + 字符数 > 0）。校验失败要如实告知"笔记未成功落盘"，不要假装已存
6. **追加索引行**：在 `~/Documents/video-notes/INDEX.md` 末尾追加一行（文件不存在则先写表头），方便日后翻找已深读的视频：

   ```markdown
   | 日期 | 频道 | 标题 | 时长 | 原链接 | 笔记 |
   |---|---|---|---|---|---|
   | 2026-09-05 | 3Blue1Brown | 注意力机制 | 22:00 | https://youtu.be/... | 3Blue1Brown/9-Jl0dxWQs8/note.md |
   ```

### 模式 B · 批量扫描

用户丢多条链接（≥2 条）时：
1. 一次传多个 URL 跑抓取脚本（批量模式，自动汇总每条状态）
2. 每条只出 TL;DR 卡片：**一句话核心 + 🧱事实1条 + 💭观点1条 + 值不值得深读判断**（含原链接）
3. 合成一份清单交付；用户圈选想深读的，再转模式 A

批量优先建议：告诉用户一次别超过 5 条，抓取较慢（每条 10-60s，走代理时更慢）。

### 模式 C · 追问深挖

用户基于已提炼的视频追问（"他对 X 的论证是什么""3:20 那句展开讲"）：
1. 先查 `~/Documents/video-notes/<频道>/<video-id>/transcript.txt` 是否已有；没有则先跑抓取脚本（`--skip-existing` 保险）
2. 用 `scripts/retrieve.py` 从 transcript 定位原文：
   ```bash
   python <skill_dir>/scripts/retrieve.py <transcript.txt> "关键词"           # 关键词 ±上下文(默认前后 1 行)
   python <skill_dir>/scripts/retrieve.py <transcript.txt> "关键词" --ctx 3    # 自定义上下文行数
   python <skill_dir>/scripts/retrieve.py <transcript.txt> --at 3:20          # 3:20 前后 30 秒(默认窗口)
   python <skill_dir>/scripts/retrieve.py <transcript.txt> --at 3:20 --window 90  # 自定义窗口
   python <skill_dir>/scripts/retrieve.py <transcript.txt> --list             # 时间戳分布索引
   ```
   **中英跨语言检索**：英文视频字幕里没有中文字，中文关键词直接搜必然 0 命中。脚本内置常见 AI/技术中英同义映射（注意力→attention、大模型→large language model 等），直接命中失败时自动换英文词重试，并在结果头部标明"已用同义词 X 检索"。若仍无结果，脚本会提示改英文关键词，或先 `--list` 看时间戳分布再用 `--at` 定位。
3. 把检索到的上下文片段交给 LLM 精读回答
4. 回答要标注所依据的时间戳区间，可跳回原片核实

### 模式 D · 选题素材（笔记尾部，不写稿）

每条模式 A 笔记的「📌 可写角度」区块产出 2-3 个可发布的选题钩子：
- **钩子要具体可兑现**：写清"这条内容能回答什么问题、给出什么结果"，避免空泛口号式标题
- **必须带自己的视角**：强调创作者的亲身验证、踩坑、对比与判断，不搬运原视频内容（防洗稿）
- 如创作者有自备的标题公式/禁区清单/平台规范，按其规范产出；没有就用上面的通用写法
- **不自动写稿**；用户说"写一篇"才另开对话按发布流程写

## 长视频 / 超长 transcript 处理

- transcript 字符数 ≤ ~90k（≈25k token）→ 单次读完直接提炼
- 超长 → 按 `[MM:SS]` 语义分段（每段 ~10 分钟），逐段让 LLM 出小节要点，再合并成终稿。合并时保留下每个要点的原始时间戳
- **有章节(chapters)的视频**：`meta.json` 的 chapters 字段含官方分节（start/end/title），提炼时优先参考它做大纲草稿，再结合字幕补细节——比纯听字幕分节准
- 时间戳格式保持 `MM:SS`（≥1 小时为 `H:MM:SS`），中文笔记里用同样的标记，方便用户跳回

## 输出语言与字幕

- **默认输出中文是便于中文用户快速消费的选择，非强制**：用户在请求里指定其他语言（如"用英文总结"）时，按用户指定的语言输出
- 输入为英文视频 → 笔记默认中文；金句保留英文原文 + 中文翻译
- 视频是中文的（如中文访谈）→ 笔记直接中文，金句不必翻译
- 字幕语言选择：脚本按 `--langs en,zh` 偏好自动挑（同语言下手动字幕优先于自动字幕）；如该视频只有别的语言字幕，脚本会抓取并如实标注，主 Agent 判断是否值得提炼

## 内容边界（重要）

- **事实 vs 观点是硬分层**：🧱事实 = 视频中陈述的可验证内容（数据、研究、事件、已发布产品、时间点）；💭观点 = 作者的判断、预测、建议、价值立场。两者不得混写，拿不准的标"待核实"
- 只总结视频里真实出现的内容，**不脑补**。字幕缺失/听不清处如实说明
- 观点类视频（博主 opinion）要提示作者立场；区分"视频讲的事实"和"视频作者的看法"
- 笔记是学习辅助，不是转载稿；模式 D 角度要防洗稿

## 常见问题

- 代理没开 → 脚本会先试直连，直连也不通才报错，提示开 Clash/V2ray 或加 `--direct`
- 视频不可用/地区限制/年龄限制 → 透出具体错误，建议换视频或说明原因
- 视频无字幕 → 明确告知无法提炼（当前版本不做本地 Whisper 转写）
- 抓取慢 → 过代理 + 字幕下载通常需 10-60 秒，脚本会打印进度；批量时会给出总耗时预估
- 中文关键词搜不到 → 正常现象（英文视频字幕无中文）；脚本会自动试同义词，也可改英文关键词或改用 `--at` 定位
- 链接被拒 → 只接受 YouTube 域名（youtube.com / youtu.be）与合法 video_id，其它站点不支持

