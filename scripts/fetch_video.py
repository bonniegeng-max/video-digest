#!/usr/bin/env python3
"""Fetch YouTube subtitles with the pinned yt-dlp Python API."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

PINNED_VERSION = "2026.8.19"
CACHE_ROOT = Path(tempfile.gettempdir()) / "video-deep-reader"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


class QuietLogger:
    """Suppress upstream CLI guidance; callers receive bounded errors instead."""

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def is_youtube_ref(value):
    value = (value or "").strip()
    if not value:
        return False
    if value.lower().startswith(("http://", "https://")):
        host = (urlsplit(value).hostname or "").lower()
        return any(host == item or host.endswith("." + item) for item in YOUTUBE_HOSTS)
    return bool(VIDEO_ID.fullmatch(value))


def load_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is missing; run scripts/doctor.py") from exc
    actual = yt_dlp.version.__version__
    normalize = lambda value: tuple(int(part) for part in value.split("."))
    if normalize(actual) != normalize(PINNED_VERSION):
        raise RuntimeError(
            f"yt-dlp {PINNED_VERSION} is required; found {actual}. Run scripts/doctor.py"
        )
    return yt_dlp


def format_ts(seconds):
    seconds = max(0, int(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def safe_name(value):
    value = re.sub(r"\s+", "_", (value or "channel").strip())
    value = re.sub(r"[^\w\u4e00-\u9fff-]", "_", value).strip("_")
    return value[:60] or "channel"


def clean_caption(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\[[^\]]*\]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_vtt(text):
    """Return timestamped, overlap-reduced transcript blocks."""
    stamp = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s*"
        r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})"
    )
    lines = text.splitlines()
    raw = []
    index = 0
    while index < len(lines):
        match = stamp.search(lines[index])
        if not match:
            index += 1
            continue
        start = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
        parts = []
        cursor = index + 1
        while cursor < len(lines) and not stamp.search(lines[cursor]):
            item = clean_caption(lines[cursor])
            if item and not item.startswith(("WEBVTT", "Kind:", "Language:")):
                parts.append(item)
            cursor += 1
        if parts:
            raw.append([start, " ".join(parts)])
        index = cursor

    def overlap(left, right):
        for size in range(min(len(left), len(right), 200), 3, -1):
            if left[-size:] == right[:size]:
                return size
        return 0

    merged = []
    for start, value in raw:
        if not merged:
            merged.append([start, value])
            continue
        previous = merged[-1][1]
        if value in previous:
            continue
        size = overlap(previous, value)
        tail = value[size:]
        if size >= 4 and tail and len(previous) + len(tail) <= 320:
            merged[-1][1] = f"{previous} {tail.lstrip()}"
        elif size < 4:
            merged.append([start, value])
        elif tail:
            merged.append([start, tail.lstrip()])
    return merged


def pick_subtitle(info, preferences):
    def score(code):
        base = code.split("-")[0].lower()
        for index, preference in enumerate(preferences):
            if base == preference or base.startswith(preference):
                return index
        return len(preferences)

    choices = []
    for key, automatic in (("subtitles", False), ("automatic_captions", True)):
        for code, formats in (info.get(key) or {}).items():
            track = next((item for item in formats if item.get("ext") == "vtt"), None)
            if track and track.get("url"):
                choices.append((score(code), automatic, code, track["url"]))
    if not choices:
        return None
    _, automatic, code, url = min(choices, key=lambda item: item[:2])
    return code, automatic, url


def managed_dir(channel, video_id, root=CACHE_ROOT):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / safe_name(channel) / video_id
    if target.exists() and target.is_symlink():
        raise RuntimeError("managed cache path is a symlink")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.resolve() not in target.resolve().parents:
        raise RuntimeError("managed cache boundary violation")
    return target


def write_private(path, content):
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def safe_error(error):
    """Return a bounded error without credential or bypass instructions."""
    value = str(error).lower()
    if "sign in" in value or "not a bot" in value or "cookies" in value:
        return (
            "YouTube requested sign-in or bot verification. Browser cookies are "
            "intentionally unsupported; paste or upload a transcript, or try later."
        )
    if "age" in value or "restricted" in value or "private video" in value:
        return (
            "The video is access-restricted. This skill does not bypass access controls; "
            "provide an authorized transcript instead."
        )
    if "unavailable" in value or "not available" in value:
        return "The video is unavailable. Check the link or provide a transcript."
    return "YouTube metadata or subtitle retrieval failed. Try later or provide a transcript."


def fetch_one(reference, languages, proxy_port, yt_dlp, root=CACHE_ROOT):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "logger": QuietLogger(),
    }
    if proxy_port:
        options["proxy"] = f"http://127.0.0.1:{proxy_port}"

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(reference, download=False)
        video_id = info.get("id") or ""
        if not VIDEO_ID.fullmatch(video_id):
            raise RuntimeError("provider returned an invalid video ID")
        directory = managed_dir(
            info.get("channel") or info.get("uploader"), video_id, root
        )
        selected = pick_subtitle(info, languages)
        metadata = {
            "id": video_id,
            "title": info.get("title") or "Untitled",
            "channel": info.get("channel") or info.get("uploader") or "Unknown",
            "duration": info.get("duration") or 0,
            "duration_str": format_ts(info.get("duration") or 0),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "chapters": [
                {
                    "start": format_ts(item.get("start_time") or 0),
                    "end": format_ts(item.get("end_time") or 0),
                    "title": (item.get("title") or "").strip(),
                }
                for item in (info.get("chapters") or [])
                if (item.get("title") or "").strip()
            ],
            "cache": "temporary",
        }
        if not selected:
            metadata["has_subtitle"] = False
            write_private(
                directory / "meta.json",
                json.dumps(metadata, ensure_ascii=False, indent=2),
            )
            return {"status": "no_subtitle", "dir": str(directory), **metadata}

        language, automatic, subtitle_url = selected
        with downloader.urlopen(subtitle_url) as response:
            blocks = parse_vtt(response.read().decode("utf-8", errors="replace"))
        if not blocks:
            metadata["has_subtitle"] = False
            write_private(
                directory / "meta.json",
                json.dumps(metadata, ensure_ascii=False, indent=2),
            )
            return {"status": "no_subtitle", "dir": str(directory), **metadata}

        transcript = "".join(
            f"[{format_ts(start)}] {value}\n" for start, value in blocks
        )
        metadata.update(
            {
                "has_subtitle": True,
                "subtitle_lang": language,
                "subtitle_manual": not automatic,
                "blocks": len(blocks),
            }
        )
        write_private(
            directory / "meta.json",
            json.dumps(metadata, ensure_ascii=False, indent=2),
        )
        write_private(directory / "transcript.txt", transcript)
        return {"status": "ok", "dir": str(directory), **metadata}


def main():
    parser = argparse.ArgumentParser(
        description="Fetch YouTube subtitles to a restricted temporary cache."
    )
    parser.add_argument("references", nargs="+", help="YouTube URLs or video IDs")
    parser.add_argument("--langs", default="en,zh", help="Subtitle preference, e.g. en,zh")
    parser.add_argument("--proxy-port", type=int, choices=range(1, 65536))
    parser.add_argument("--ui-lang", choices=("en", "zh"), default="en")
    args = parser.parse_args()

    if not all(is_youtube_ref(item) for item in args.references):
        text = "仅接受 YouTube 链接或视频 ID。" if args.ui_lang == "zh" else (
            "Only YouTube URLs or video IDs are accepted."
        )
        print(text, file=sys.stderr)
        return 2
    try:
        yt_dlp = load_yt_dlp()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    languages = [item.strip().lower() for item in args.langs.split(",") if item.strip()]
    results = []
    for reference in args.references:
        try:
            results.append(fetch_one(reference, languages, args.proxy_port, yt_dlp))
        except Exception as exc:
            results.append(
                {"status": "error", "reference": reference, "error": safe_error(exc)}
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(item["status"] == "error" for item in results):
        return 3
    if any(item["status"] == "no_subtitle" for item in results):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
