# video-digest · 视频深读

把「没时间看的 YouTube 优质视频」变成「能 5 分钟读完、可跳回原片、可追问深挖、可当选题素材」的中文结构化笔记。

> 一个 agent skill。适用于英文 AI/科技类长视频、TED 演讲、访谈、Shorts 科普。

## 为什么做这个

收藏夹里躺着太多"以后再看"的优质视频——但真的没时间看。与其让它们在收藏夹吃灰，不如让 AI 把内容提炼出来：

- **概述主要内容**：按主题分节整理成文，不是流水账
- **区分事实和观点**：🧱 可验证的事实 / 💭 作者的判断、预测、立场——硬分层，不得混写
- **可跳回原片**：每条要点带 `[MM:SS]` 时间戳 + 原链接，感兴趣直接点回去看
- **可追问深挖**：笔记和字幕原文落盘存档，任何会话说一句"再讲讲 3:20 那段"就能翻原文精读
- **顺带产出选题素材**：笔记尾部给 2-3 个公众号/小红书「可写角度」钩子（不自动写稿）

## 怎么装

```bash
# WorkBuddy / CodeBuddy 用户级安装
git clone https://github.com/bonniegeng-max/video-digest.git ~/.workbuddy/skills/video-digest

# OpenClaw / ClawHub
openclaw skills install video-digest
```

依赖：`yt-dlp`（Python 包，抓字幕用）+ 本机可用的科学上网代理（Clash/V2ray，常见端口 7897/7890/1087，脚本自动探测）。

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
| D 选题素材 | 笔记尾部自带 | 2-3 个公众号/小红书选题钩子（不写稿） |

### 命令行进阶

```bash
# 批量抓取（模式 B，一次传多个 URL，代理只探测一次）
python scripts/fetch_video.py <url1> <url2> <url3>

# 复用已有存档（模式 C 追问前用，已有字幕则跳过）
python scripts/fetch_video.py <url> --skip-existing

# 追问检索（模式 C）：按关键词 / 时间戳区间 / 索引 定位原文
python scripts/retrieve.py <transcript.txt> "关键词"
python scripts/retrieve.py <transcript.txt> --at 3:20 --window 90
python scripts/retrieve.py <transcript.txt> --list
```

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
📌 可写角度（公众号/小红书选题素材，不写稿）
```

## 技术说明

- 抓取走 `scripts/fetch_video.py`：自动探测代理 → yt-dlp 抓元数据+字幕 → 解析成带时间戳的连贯文本
- YouTube 自动字幕是"滚动窗口式"的（每行重复前文），脚本用最长重叠融合算法去重，3380 碎片可清洗成约 216 个语义句块
- 无字幕的视频会明确告知（当前版本不做本地 Whisper 转写，以后可扩展）
- 笔记存档：`~/Documents/video-notes/<频道>/<video-id>/`（meta.json + transcript.txt + note.md）

## 隐私与数据保留

抓取会把以下内容**保存在本机**，请知悉：

- **存什么**：`meta.json`（标题/频道/时长/简介/章节/字幕语言，**代理地址已脱敏**，不含任何凭据）、`transcript.txt`（完整字幕原文）、`note.md`（AI 生成的中文笔记）
- **存哪里**：默认 `~/Documents/video-notes/<频道>/<video-id>/`。字幕原文可能反映你的观看与研究兴趣，请存放在你认为安全的位置
- **存多久**：不自动删除，除非你手动清理
- **如何改位置**：加 `--out <目录>` 参数可指定输出目录
- **如何删除**：删除单个视频：`rm -rf ~/Documents/video-notes/<频道>/<video-id>`；删除全部：`rm -rf ~/Documents/video-notes`

代理安全：脚本只把代理 URL 的 `scheme://host:port` 打印或写入 meta.json，`user:password@` 凭据部分一律剥掉，不会出现在日志或存档里。

## License

MIT
