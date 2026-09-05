#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video-digest / retrieve.py
模式 C 追问检索工具:从带时间戳的 transcript.txt 里定位原文片段。

用法:
    python retrieve.py <transcript.txt> "关键词"              # 含关键词的行 ±上下文(默认前后 1 行)
    python retrieve.py <transcript.txt> "关键词" --ctx 3       # 自定义上下文行数
    python retrieve.py <transcript.txt> --at 3:20 --window 90  # 时间戳 3:20 前后各 90 秒
    python retrieve.py <transcript.txt> --list                 # 列出全部时间戳(稀疏采样,看话题分布)
    python retrieve.py <transcript.txt> --at 3:20              # 只看 3:20 那一行

transcript 行格式: [MM:SS] 文本 或 [H:MM:SS] 文本
退出码: 0 有结果 | 1 无结果/文件问题 | 2 参数错误
"""
import argparse
import re
import sys


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


def parse_lines(path):
    """解析 transcript,返回 [(ts_sec, ts_str, text, line_no)]。"""
    ts_re = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s?(.*)$")
    entries = []
    with open(path, encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            raw = raw.rstrip("\n")
            m = ts_re.match(raw)
            if not m:
                continue
            ts_str, text = m.group(1), m.group(2).strip()
            sec = ts_to_sec(ts_str)
            if sec is not None and text:
                entries.append((sec, ts_str, text, line_no))
    return entries


def print_entry(entry, show_line=True):
    sec, ts_str, text, line_no = entry
    prefix = f"L{line_no} " if show_line else ""
    print(f"{prefix}[{ts_str}] {text}")


def main():
    ap = argparse.ArgumentParser(description="从 video-digest transcript 检索原文片段")
    ap.add_argument("transcript", help="transcript.txt 路径")
    ap.add_argument("keyword", nargs="?", default=None, help="关键词(与 --at/--list 互斥)")
    ap.add_argument("--ctx", type=int, default=1, help="关键词命中行前后各取几行,默认 1")
    ap.add_argument("--at", default=None, help="时间戳,如 3:20 或 1:02:45")
    ap.add_argument("--window", type=int, default=60,
                    help="--at 模式:前后各多少秒,默认 60(即共 2 分钟)")
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
        print(f"── [{args.at}] 前后 {args.window}s ({lo//60}:{lo%60:02d} ~ {hi//60}:{hi%60:02d}) 命中 {len(matched)} 行 ──")
        for e in matched:
            print_entry(e)
        sys.exit(0)

    # ---- keyword: 关键词 ± 上下文 ----
    kw = args.keyword.lower()
    matched_idx = [i for i, e in enumerate(entries) if kw in e[2].lower()]
    if not matched_idx:
        print(f"无结果: 关键词 '{args.keyword}' 未命中({len(entries)} 行中)")
        sys.exit(1)
    shown = set()
    print(f"── 关键词 '{args.keyword}' 命中 {len(matched_idx)} 处(显示每处 ±{args.ctx} 行) ──")
    for i in matched_idx:
        lo = max(0, i - args.ctx)
        hi = min(len(entries) - 1, i + args.ctx)
        for j in range(lo, hi + 1):
            if j in shown:
                continue
            if j != i:
                print("  ┆")
            print_entry(entries[j])
            shown.add(j)
        print("  …")
    sys.exit(0)


if __name__ == "__main__":
    main()
