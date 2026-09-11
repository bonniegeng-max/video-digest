#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video-digest / retrieve.py
模式 C 追问检索工具:从带时间戳的 transcript.txt 里定位原文片段。

用法:
    python retrieve.py <transcript.txt> "关键词"              # 含关键词的行 ±上下文(默认前后 1 行)
    python retrieve.py <transcript.txt> "关键词" --ctx 3       # 自定义上下文行数
    python retrieve.py <transcript.txt> --at 3:20 --window 30  # 时间戳 3:20 前后各 30 秒
    python retrieve.py <transcript.txt> --list                 # 列出全部时间戳(稀疏采样,看话题分布)
    python retrieve.py <transcript.txt> --at 3:20              # 时间戳前后默认 30 秒

transcript 行格式: [MM:SS] 文本 或 [H:MM:SS] 文本
退出码: 0 有结果 | 1 无结果/文件问题 | 2 参数错误

中文检索说明:
    英文视频的字幕里没有中文字,中文关键词直接搜必然 0 命中。
    脚本内置常见中英同义映射(注意力→attention、大模型→LLM 等),
    直接命中失败时会自动用对应英文词重试,并提示用的是哪个词。
"""
import argparse
import re
import sys

# 常见中英同义映射(AI/技术语境),用于中文关键词搜英文视频时自动兜底。
SYNONYMS = {
    "注意力": ["attention"],
    "注意力机制": ["attention"],
    "神经网络": ["neural network", "neural net"],
    "深度学习": ["deep learning"],
    "机器学习": ["machine learning"],
    "梯度下降": ["gradient descent"],
    "反向传播": ["backpropagation", "backprop", "back-prop"],
    "损失函数": ["loss function", "loss"],
    "过拟合": ["overfitting", "overfit"],
    "欠拟合": ["underfitting"],
    "正则化": ["regularization"],
    "微调": ["fine-tune", "fine tuning", "finetune", "fine-tuned"],
    "预训练": ["pretrain", "pre-train", "pretraining", "pretrained"],
    "强化学习": ["reinforcement learning", "reinforcement"],
    "监督学习": ["supervised learning"],
    "无监督": ["unsupervised"],
    "自监督": ["self-supervised"],
    "大模型": ["large language model", "llm", "foundation model"],
    "大语言模型": ["large language model", "llm"],
    "提示词": ["prompt"],
    "提示工程": ["prompt engineering"],
    "上下文": ["context"],
    "上下文窗口": ["context window"],
    "幻觉": ["hallucination", "hallucinate"],
    "对齐": ["alignment", "align"],
    "智能体": ["agent"],
    "检索增强": ["retrieval augmented", "rag"],
    "向量": ["vector"],
    "嵌入": ["embedding", "embed"],
    "词元": ["token"],
    "分词": ["tokenization", "tokenize"],
    "编码器": ["encoder"],
    "解码器": ["decoder"],
    "卷积": ["convolution", "convolutional"],
    "池化": ["pooling"],
    "激活函数": ["activation function", "activation"],
    "参数": ["parameter", "weight"],
    "推理": ["inference"],
    "训练": ["training", "train"],
    "数据集": ["dataset"],
    "模型": ["model"],
    "架构": ["architecture"],
    "涌现": ["emergent", "emergence"],
    "缩放": ["scaling", "scale"],
    "泛化": ["generalization", "generalize"],
    "多模态": ["multimodal"],
    "扩散模型": ["diffusion"],
    "生成式": ["generative"],
    "贝叶斯": ["bayes", "bayesian"],
    "概率": ["probability", "probabilistic"],
    "导数": ["derivative"],
    "矩阵": ["matrix", "matrices"],
    "线性": ["linear"],
    "非线性": ["nonlinear", "non-linear"],
    "优化": ["optimization", "optimize"],
    "误差": ["error"],
    "准确率": ["accuracy"],
    "语言模型": ["language model"],
    "词向量": ["word vector", "word2vec"],
    "循环神经网络": ["recurrent neural network", "rnn"],
    "变换器": ["transformer"],
    "自编码器": ["autoencoder"],
    "生成对抗": ["generative adversarial", "gan"],
    "标注": ["label", "annotation"],
    "奖励": ["reward"],
    "策略": ["policy"],
    "采样": ["sampling", "sample"],
    "分布": ["distribution"],
    "均值": ["mean", "average"],
    "方差": ["variance"],
    "维度": ["dimension"],
    "激活": ["activation"],
    "层": ["layer"],
    "权重": ["weight"],
    "偏差": ["bias"],
}


def ts_to_sec(ts_str):
    """'MM:SS' 或 'H:MM:SS' → 秒。失败返回 None。"""
    parts = ts_str.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def sec_to_ts(sec):
    """秒 → 'M:SS' 或 'H:MM:SS'。"""
    if sec < 0:
        sec = 0
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_lines(path):
    """解析 transcript,返回 [(ts_sec, ts_str, text)]。"""
    ts_re = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$")
    entries = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            m = ts_re.match(raw.rstrip("\n"))
            if not m:
                continue
            ts_str, text = m.group(1), m.group(2).strip()
            sec = ts_to_sec(ts_str)
            if sec is not None and text:
                entries.append((sec, ts_str, text))
    return entries


def print_entry(entry):
    """只打印 [时间戳] 文本。文件行号是内部细节,不对外显示。"""
    sec, ts_str, text = entry
    print(f"[{ts_str}] {text}")


def has_cjk(s):
    """是否含中日韩字符。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def expand_keyword(kw):
    """同义扩展:中文词→常见英文词;英文词→中文词。返回候选列表(不含原词)。"""
    kw_l = kw.lower().strip()
    out = []
    if has_cjk(kw_l):
        # 中文 → 英文:只取被包含的「最长」条目,避免"大模型"误命中泛化的"模型"
        best = None
        for zh in SYNONYMS:
            if zh in kw_l and (best is None or len(zh) > len(best)):
                best = zh
        if best:
            for en in SYNONYMS[best]:
                if en.lower() != kw_l:
                    out.append(en)
    else:
        # 英文 → 中文:凡是英文条目被包含的都算
        for zh, ens in SYNONYMS.items():
            if any(en.lower() in kw_l for en in ens) and zh not in out:
                out.append(zh)
    return out


def search(entries, kw):
    """返回命中下标列表。"""
    kw_l = kw.lower()
    return [i for i, e in enumerate(entries) if kw_l in e[2].lower()]


def main():
    ap = argparse.ArgumentParser(description="从 video-digest transcript 检索原文片段")
    ap.add_argument("transcript", help="transcript.txt 路径")
    ap.add_argument("keyword", nargs="?", default=None, help="关键词(与 --at/--list 互斥)")
    ap.add_argument("--ctx", type=int, default=1, help="关键词命中行前后各取几行,默认 1")
    ap.add_argument("--at", default=None, help="时间戳,如 3:20 或 1:02:45")
    ap.add_argument("--window", type=int, default=30,
                    help="--at 模式:前后各多少秒,默认 30(即共 1 分钟)")
    ap.add_argument("--list", action="store_true", help="列出全部时间戳索引")
    args = ap.parse_args()

    # 模式互斥校验
    modes = sum([bool(args.keyword), bool(args.at), bool(args.list)])
    if modes != 1:
        print("ERROR: 关键词 / --at / --list 三选一。")
        sys.exit(2)

    try:
        entries = parse_lines(args.transcript)
    except FileNotFoundError:
        print(f"ERROR: 文件不存在: {args.transcript}")
        sys.exit(1)
    if not entries:
        print("ERROR: transcript 为空或格式无法解析。")
        sys.exit(1)

    # ---- --list: 时间戳索引(稀疏采样,每页至多 ~40 个点) ----
    if args.list:
        step = max(1, len(entries) // 40)
        for e in entries[::step]:
            print_entry(e)
        print(f"\n共 {len(entries)} 个时间戳点 (采样步长 {step})")
        sys.exit(0)

    # ---- --at: 时间戳区间 ----
    if args.at:
        center = ts_to_sec(args.at)
        if center is None:
            print(f"ERROR: 无法解析时间戳 '{args.at}',格式应为 MM:SS 或 H:MM:SS")
            sys.exit(2)
        lo, hi = center - args.window, center + args.window
        matched = [e for e in entries if lo <= e[0] <= hi]
        if not matched:
            print(f"无结果: {args.at} 前后 {args.window}s 内没有文本({len(entries)} 个时间点中)")
            sys.exit(1)
        print(f"── [{args.at}] 前后 {args.window}s "
              f"({sec_to_ts(lo)} ~ {sec_to_ts(hi)}) 命中 {len(matched)} 行 ──")
        for e in matched:
            print_entry(e)
        sys.exit(0)

    # ---- keyword: 关键词 ± 上下文(带同义兜底) ----
    matched_idx = search(entries, args.keyword)
    note = ""
    if not matched_idx:
        # 直接命中失败 → 尝试中英同义替换
        for alt in expand_keyword(args.keyword):
            idx = search(entries, alt)
            if idx:
                matched_idx = idx
                note = f"「{args.keyword}」无直接命中,已用同义词「{alt}」检索"
                break

    if not matched_idx:
        print(f"无结果: 关键词 '{args.keyword}' 未命中({len(entries)} 行中)")
        if has_cjk(args.keyword):
            print("提示: 中文关键词在英文视频字幕里搜不到是正常的。可以:")
            print("   - 换成英文关键词(如 attention / large language model)")
            print("   - 先 --list 看时间戳分布,再用 --at 3:20 定位到大致时段")
        else:
            print("提示: 换个更短的关键词(取词根,如 attention 而不是 attentions),")
            print("      或先 --list 看话题分布,再用 --at 定位。")
        sys.exit(1)

    if note:
        print(f"── 关键词 '{args.keyword}' 命中 {len(matched_idx)} 处 ({note}, 显示每处 ±{args.ctx} 行) ──")
    else:
        print(f"── 关键词 '{args.keyword}' 命中 {len(matched_idx)} 处(显示每处 ±{args.ctx} 行) ──")
    shown = set()
    for i in matched_idx:
        lo = max(0, i - args.ctx)
        hi = min(len(entries) - 1, i + args.ctx)
        block = [j for j in range(lo, hi + 1) if j not in shown]
        if not block:
            continue
        for j in block:
            if j != i:
                print("  ┆")
            print_entry(entries[j])
            shown.add(j)
        print("  …")
    sys.exit(0)


if __name__ == "__main__":
    main()
