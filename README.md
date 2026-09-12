# video-digest · 视频深读

把「没时间看的 YouTube 优质视频」变成「能 5 分钟读完、可跳回原片、可追问深挖、可当选题素材」的结构化笔记（输出语言默认中文，可按用户要求换其他语言）。

> 一个 agent skill。适用于英文 AI/科技类长视频、TED 演讲、访谈、Shorts 科普。

## 为什么做这个

收藏夹里躺着太多"以后再看"的优质视频——但真的没时间看。与其让它们在收藏夹吃灰，不如让 AI 把内容提炼出来：

- **概述主要内容**：按主题分节整理成文，不是流水账
- **区分事实和观点**：🧱 可验证的事实 / 💭 作者的判断、预测、立场——硬分层，不得混写
- **可跳回原片**：每条要点带 `[MM:SS]` 时间戳 + 原链接，感兴趣直接点回去看
- **可追问深挖**：笔记和字幕原文落盘存档，任何会话说一句"再讲讲 3:20 那段"就能翻原文精读
- **顺带产出选题素材**：笔记尾部给 2-3 个内容平台「可写角度」钩子（不自动写稿）

## 怎么装

```bash
# WorkBuddy / CodeBuddy 用户级安装
git clone https://github.com/bonniegeng-max/video-digest.git ~/.workbuddy/skills/video-digest

# OpenClaw / ClawHub
openclaw skills install video-digest
```

依赖：`yt-dlp`（Python 包，抓字幕用）+ 网络可达 YouTube。

- 国内网络：需要本机代理（Clash/V2ray，常见端口 7897/7890/1087，脚本自动探测；探测不到会自动试直连）
- 海外网络/企业出口可直连：脚本自动识别；也可加 `--direct` 显式跳过代理探测

```bash
pip install yt-dlp
```

> 供应链提示：为可复现安装，建议固定 yt-dlp 版本（如 `pip install yt-dlp==2025.xx.x`），并按需升级。

## 怎么用

丢一条 YouTube 链接即可：

> 帮我提炼这条视频：https://www.youtube.com/watch?v=...

或说「视频深读 <链接>」。支持四种模式：

| 模式 | 场景 | 产出 |
|---|---|---|
| A 单条深读 | 丢 1 条链接 | 完整中文结构化笔记（默认） |
| B 批量扫描 | 丢 N 条链接 | 每条 TL;DR 卡片 + 值不值得深读判断 |
| C 追问深挖 | 读笔记后继续问 | 按问题检索字幕原文，带时间戳精读回答 |
| D 选题素材 | 笔记尾部自带 | 2-3 个内容平台选题钩子（不写稿） |

### 命令行进阶

```bash
# 批量抓取（模式 B，一次传多个 URL，代理只探测一次）
python scripts/fetch_video.py <url1> <url2> <url3>

# 复用已有存档（模式 C 追问前用，已有字幕则跳过）
python scripts/fetch_video.py <url> --skip-existing

# 直连（不走代理探测；海外网络或企业出口可直连时用）
python scripts/fetch_video.py <url> --direct

# 追问检索（模式 C）：按关键词 / 时间戳区间 / 索引 定位原文
python scripts/retrieve.py <transcript.txt> "关键词"
python scripts/retrieve.py <transcript.txt> --at 3:20              # 前后 30 秒（默认）
python scripts/retrieve.py <transcript.txt> --at 3:20 --window 90  # 自定义窗口
python scripts/retrieve.py <transcript.txt> --list
```

> **中文关键词搜英文视频**：字幕里没有中文字，中文词直接搜必然 0 命中。脚本内置常见 AI/技术中英同义映射（注意力→attention、大模型→large language model 等），会**自动换英文词重试**并告知用了哪个词；若仍无结果，改英文关键词或先 `--list` 看分布再用 `--at` 定位。

### 章节信息

有官方章节(chapters)的长视频，抓取时会写入 `meta.json` 的 `chapters` 字段，提炼时优先参考章节做大纲，分节更准。

## 笔记长什么样

完整样张见 [`references/examples/`](references/examples/)：

- `example_ted_conversation.md` — TED 演讲（手动字幕 11min）深读范本
- `example_vllm_shorts.md` — YouTube Shorts（自动字幕 3min）轻量范本

核心结构：

```
TL;DR（2-3 句读完不用看视频）
📖 内容讲了什么（按主题分节 + 时间戳）
🧱 事实（可验证：数据/研究/事件）  💭 观点（作者判断/预测/立场）
💬 金句（原文 + 中译）
❓ 我的存疑 / 可追问点
📌 可写角度（内容平台选题素材，不写稿）
```

## 架构：代码抓取 + AI 提炼

本 skill = **抓取脚本（代码）** + **笔记规范（由运行本 skill 的 AI 执行）**：脚本只负责网络抓取与字幕解析，不含文本生成逻辑；"中文结构化笔记、事实/观点分层、追问检索作答"等能力由 AI 按 SKILL.md 与 note_template 的规范实现。

## 技术说明

- 抓取走 `scripts/fetch_video.py`：自动探测代理 → 不通则试直连 → yt-dlp 抓元数据+字幕 → 解析成带时间戳的连贯文本
- YouTube 自动字幕是"滚动窗口式"的（每行重复前文），脚本用最长重叠融合算法去重，3380 碎片可清洗成约 216 个语义句块
- 无字幕的视频会明确告知（当前版本不做本地 Whisper 转写，以后可扩展）
- 笔记存档：`~/Documents/video-notes/<频道>/<video-id>/`（meta.json + transcript.txt + note.md）
- 深读过的视频会登记到 `~/Documents/video-notes/INDEX.md`（日期/频道/标题/时长/链接/笔记路径），方便日后翻找

## 隐私与数据保留

抓取会把以下内容**保存在本机**，请知悉：

- **存什么**：`meta.json`（标题/频道/时长/简介/章节/字幕语言，**代理地址已脱敏**，不含任何凭据）、`transcript.txt`（完整字幕原文）、`note.md`（AI 生成的中文笔记）
- **存哪里**：默认 `~/Documents/video-notes/<频道>/<video-id>/`。字幕原文可能反映你的观看与研究兴趣，请存放在你认为安全的位置
- **存多久**：不自动删除，除非你手动清理
- **如何改位置**：加 `--out <目录>` 参数可指定输出目录
- **如何删除**：在访达/文件管理器中删除对应存档文件夹即可（单个视频：`~/Documents/video-notes/<频道>/<video-id>/`；全部：`~/Documents/video-notes/`）。删除是不可恢复操作，请确认后再删

代理安全：脚本只把代理 URL 的 `scheme://host:port` 打印或写入 meta.json，`user:password@` 凭据部分一律剥掉，不会出现在日志或存档里。本地代理（最常见，如 Clash 的 127.0.0.1:7897）通常无凭据，传给 yt-dlp 的命令行参数里只有 host:port，**凭据零暴露**；若代理带凭据，运行时会打印明确提示（受限于 yt-dlp 仅支持参数方式传代理）。

## License

MIT
