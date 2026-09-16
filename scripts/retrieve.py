#!/usr/bin/env python3
"""Retrieve timestamped excerpts from the managed temporary cache."""

import argparse
import locale
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

CACHE_ROOT = Path(tempfile.gettempdir()) / f"video-deep-reader-{os.geteuid()}"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
STAMP = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$")
SYNONYMS = {
    "注意力": ("attention",),
    "神经网络": ("neural network",),
    "深度学习": ("deep learning",),
    "机器学习": ("machine learning",),
    "大模型": ("large language model", "llm"),
    "提示词": ("prompt",),
    "上下文": ("context",),
    "智能体": ("agent",),
    "检索增强": ("retrieval augmented", "rag"),
    "向量": ("vector",),
    "嵌入": ("embedding",),
    "推理": ("inference",),
    "训练": ("training",),
}


def ts_to_seconds(value):
    try:
        parts = [int(item) for item in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def find_transcript(video_id, root=CACHE_ROOT):
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("invalid video ID")
    if not root.exists():
        raise FileNotFoundError("managed cache does not exist")
    root_info = root.lstat()
    if (
        stat.S_ISLNK(root_info.st_mode)
        or not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid != os.geteuid()
        or stat.S_IMODE(root_info.st_mode) != 0o700
    ):
        raise ValueError("managed cache root failed ownership or permission checks")

    safe = []
    for channel in root.iterdir():
        channel_info = channel.lstat()
        if (
            stat.S_ISLNK(channel_info.st_mode)
            or not stat.S_ISDIR(channel_info.st_mode)
            or channel_info.st_uid != os.geteuid()
            or stat.S_IMODE(channel_info.st_mode) != 0o700
        ):
            continue
        video_dir = channel / video_id
        if not video_dir.exists() or video_dir.is_symlink():
            continue
        video_info = video_dir.lstat()
        if (
            not stat.S_ISDIR(video_info.st_mode)
            or video_info.st_uid != os.geteuid()
            or stat.S_IMODE(video_info.st_mode) != 0o700
        ):
            continue
        path = video_dir / "transcript.txt"
        if not path.exists() or path.is_symlink():
            continue
        file_info = path.lstat()
        if not stat.S_ISREG(file_info.st_mode) or file_info.st_uid != os.geteuid():
            continue
        resolved = path.resolve()
        if root.resolve() in resolved.parents:
            safe.append(path)
    if len(safe) != 1:
        raise FileNotFoundError(f"expected one managed transcript, found {len(safe)}")
    return safe[0]


def parse_transcript(path):
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = STAMP.match(line)
        if not match:
            continue
        seconds = ts_to_seconds(match.group(1))
        if seconds is not None:
            entries.append((seconds, match.group(1), match.group(2)))
    return entries


def expand_keyword(keyword):
    if any("\u4e00" <= char <= "\u9fff" for char in keyword):
        candidates = [
            (key, values) for key, values in SYNONYMS.items() if key in keyword
        ]
        if candidates:
            return max(candidates, key=lambda item: len(item[0]))[1]
    return ()


def keyword_matches(entries, keyword, synonym_mode="none"):
    lowered = keyword.lower()
    indexes = [index for index, item in enumerate(entries) if lowered in item[2].lower()]
    used = keyword
    if not indexes and synonym_mode == "zh-en":
        for alternative in expand_keyword(keyword):
            indexes = [
                index
                for index, item in enumerate(entries)
                if alternative.lower() in item[2].lower()
            ]
            if indexes:
                used = alternative
                break
    return indexes, used


def interface_language(requested):
    if requested and requested != "auto":
        return "zh" if requested.lower().startswith("zh") else "en"
    current = locale.getlocale()[0] or ""
    return "zh" if current.lower().startswith("zh") else "en"


def main():
    parser = argparse.ArgumentParser(
        description="Search one managed Video Deep Reader transcript."
    )
    parser.add_argument("video_id")
    parser.add_argument("keyword", nargs="?")
    parser.add_argument("--at", help="Timestamp such as 3:20 or 1:02:45")
    parser.add_argument("--window", type=int, default=30)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--context", type=int, default=1)
    parser.add_argument(
        "--synonyms",
        choices=("none", "zh-en"),
        default="none",
        help="Optional query expansion; zh-en maps selected Chinese technical terms",
    )
    parser.add_argument("--ui-lang", default="auto", help="UI language or auto")
    args = parser.parse_args()
    ui_lang = interface_language(args.ui_lang)

    if sum((bool(args.keyword), bool(args.at), bool(args.list))) != 1:
        print("Choose exactly one of keyword, --at, or --list.", file=sys.stderr)
        return 2
    try:
        path = find_transcript(args.video_id)
        entries = parse_transcript(path)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not entries:
        print("Managed transcript is empty.", file=sys.stderr)
        return 1

    selected = []
    note = ""
    if args.list:
        step = max(1, len(entries) // 40)
        selected = entries[::step]
    elif args.at:
        center = ts_to_seconds(args.at)
        if center is None:
            print("Invalid timestamp.", file=sys.stderr)
            return 2
        selected = [
            item for item in entries
            if center - args.window <= item[0] <= center + args.window
        ]
    else:
        indexes, used = keyword_matches(entries, args.keyword, args.synonyms)
        note = used if used != args.keyword else ""
        seen = set()
        for index in indexes:
            for cursor in range(
                max(0, index - args.context),
                min(len(entries), index + args.context + 1),
            ):
                if cursor not in seen:
                    selected.append(entries[cursor])
                    seen.add(cursor)

    if not selected:
        text = "没有命中。" if ui_lang == "zh" else "No matches."
        print(text, file=sys.stderr)
        return 1
    if note:
        print(f"synonym: {note}")
    for _, stamp, text in selected:
        print(f"[{stamp}] {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
