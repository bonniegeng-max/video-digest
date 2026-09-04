#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video-digest / fetch_video.py
抓取 YouTube 视频元数据 + 字幕,解析为带时间戳的纯文本 transcript。

用法:
    python fetch_video.py <youtube_url> [--out <目录>] [--langs en,zh]

输出:
    落在 <out>/<频道>/<video-id>/
    meta.json        视频元数据(标题/频道/时长/简介/字幕语言)
    transcript.txt   带 [MM:SS] 时间戳的纯文本(行内去重合并)

退出码:
    0 成功 | 2 代理/python 环境不可用 | 3 视频不可达/下载失败 | 4 无可用字幕
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

PROXY_CANDIDATES = [
    "http://127.0.0.1:7897",  # Clash 常见端口
    "http://127.0.0.1:7890",  # Clash 旧默认
    "http://127.0.0.1:1087",  # V2rayU 常见
    "http://127.0.0.1:10809",  # v2rayN
]
YOUTUBE_PROBE = "https://www.youtube.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_venv_python():
    """定位装有 yt-dlp 的 python(优先当前解释器,其次托管 venv)。"""
    try:
        import yt_dlp  # noqa: F401
        return sys.executable
    except ImportError:
        pass
    candidates = [
        os.path.expanduser("~/.workbuddy/binaries/python/envs/default/bin/python"),
        os.path.join(os.path.dirname(SCRIPT_DIR), ".venv", "bin", "python"),
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                r = subprocess.run([c, "-c", "import yt_dlp"], capture_output=True, timeout=15)
                if r.returncode == 0:
                    return c
            except Exception:
                continue
    return None


def probe_proxy(proxy_url):
    """探测代理是否可达 YouTube。"""
    if not proxy_url:
        return False
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    )
    try:
        req = urllib.request.Request(YOUTUBE_PROBE, method="HEAD")
        return opener.open(req, timeout=8).status < 400
    except Exception:
        return False


def pick_proxy():
    """按候选顺序探测可用代理;全失败则看环境变量 HTTPS_PROXY。"""
    for p in PROXY_CANDIDATES:
        if probe_proxy(p):
            return p
    env_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if env_proxy and probe_proxy(env_proxy):
        return env_proxy
    return None


def format_ts(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def clean_line(line):
    line = re.sub(r"<[^>]+>", "", line)          # 去 html 标签
    line = re.sub(r"\[[^\]]*\]", "", line).strip()  # 去 [Music] 等
    return line


def parse_vtt(vtt_text):
    """解析 vtt → [(start_sec, text)],合并断句与翻页重复。"""
    blocks = []
    ts_re = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s*"
        r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})"
    )
    lines = vtt_text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = ts_re.search(lines[i])
        if m:
            h1, m1, s1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            start = h1 * 3600 + m1 * 60 + s1
            texts = []
            j = i + 1
            while j < n and not ts_re.search(lines[j]):
                line = lines[j].strip()
                if line and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE", "-->", "::cue")):
                    cleaned = clean_line(line)
                    if cleaned:
                        texts.append(cleaned)
                j += 1
            if texts:
                blocks.append([start, " ".join(texts)])
            i = j
        else:
            i += 1

    # 重叠融合:YouTube ASR 字幕是滚动窗口(每行=前文尾缀+新内容),
    # 用最长后缀/前缀匹配把碎片拼回连贯长句,去掉纯重复行。
    MAX_SENT = 320  # 单行封顶字符,超出则封口新起一行,保留时间戳粒度

    def max_overlap(a, b):
        """返回 b 前缀与 a 后缀的最长重叠长度(字符,上限防退化)。"""
        limit = min(len(a), len(b), 200)
        for k in range(limit, 3, -1):
            if a[-k:] == b[:k]:
                return k
        return 0

    merged = []  # [start, text]
    for start, text in blocks:
        if not text:
            continue
        if not merged:
            merged.append([start, text])
            continue
        prev_start, prev_text = merged[-1]
        if text in prev_text:
            continue  # 整句已存在
        ov = max_overlap(prev_text, text)
        new_tail = text[ov:]
        if ov >= 4 and new_tail:
            if len(prev_text) + len(new_tail) + 1 <= MAX_SENT:
                merged[-1][1] += " " + new_tail  # 续拼当前行
            else:
                # 当前行已够长:封口,新增内容另起一行(带本行时间戳)
                merged.append([start, new_tail.lstrip()])
        elif ov >= 4 and not new_tail:
            continue  # 纯重复
        else:
            merged.append([start, text])
    return merged


def pick_subtitle(info, lang_prefs):
    """从手动字幕 + 自动字幕里挑最佳语言,返回 (lang_code, key, is_auto) 或 None。
    规则:偏好语言 > 非偏好语言;同语言下手动 > 自动。
    """
    def lang_score(code):
        base = code.split("-")[0].lower()
        for i, pref in enumerate(lang_prefs):
            if base == pref or base.startswith(pref):
                return i
        return len(lang_prefs)

    best = None  # (score, manual_priority, code, key, is_auto)
    for key, is_auto in (("subtitles", False), ("automatic_captions", True)):
        subs = info.get(key) or {}
        for code in subs:
            cand = (lang_score(code), 0 if not is_auto else 1, code, key, is_auto)
            if best is None or cand[:2] < best[:2]:
                best = cand
    return best[2:] if best else None  # (code, key, is_auto)


def write_meta(vdir, meta):
    os.makedirs(vdir, exist_ok=True)
    with open(os.path.join(vdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="抓取 YouTube 元数据+字幕")
    ap.add_argument("url", help="YouTube 视频 URL 或 ID")
    ap.add_argument("--out", default=None, help="输出根目录(默认 ~/Documents/video-notes)")
    ap.add_argument("--langs", default="en,zh", help="字幕语言偏好,默认 en,zh")
    args = ap.parse_args()

    proxy = pick_proxy()
    if not proxy:
        print("ERROR: 未探测到可用代理,请确认 Clash/V2ray 已开启(常见端口 7897/7890/1087)。")
        sys.exit(2)
    print(f"PROXY: {proxy}")

    py = find_venv_python()
    if not py:
        print("ERROR: 找不到带 yt-dlp 的 python,请先安装: pip install yt-dlp")
        sys.exit(2)

    langs = [l.strip().lower() for l in args.langs.split(",") if l.strip()]
    root = args.out or os.path.expanduser("~/Documents/video-notes")

    # ---- Step 1: 元数据 ----
    dump_cmd = [py, "-m", "yt_dlp", "--dump-json", "--skip-download",
                "--proxy", proxy, "--no-warnings", args.url]
    try:
        proc = subprocess.run(dump_cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("ERROR: 获取视频信息超时,网络慢或视频不存在。")
        sys.exit(3)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-800:]
        low = err.lower()
        if "video unavailable" in low or "is unavailable" in low or "unsupported url" in low or "not found" in low or "unable to extract" in low:
            print(f"ERROR: 视频不可达/链接无效。\n{err}")
        elif "sign in" in low or "age" in low or "confirm" in low or "restricted" in low:
            print(f"ERROR: 视频受限制(需登录/年龄验证/地区限制)。\n{err}")
        else:
            print(f"ERROR: yt-dlp 获取信息失败。\n{err}")
        sys.exit(3)

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("ERROR: 解析元数据失败。")
        sys.exit(3)

    video_id = info.get("id", "unknown")
    title = info.get("title", "untitled")
    channel = info.get("channel") or info.get("uploader") or "unknown"
    duration = info.get("duration") or 0
    description = (info.get("description") or "")[:2000]
    url = f"https://www.youtube.com/watch?v={video_id}"
    safe_channel = re.sub(r'[^\w\u4e00-\u9fff-]', "_", channel)[:60] or "channel"
    vdir = os.path.join(root, safe_channel, video_id)

    common_meta = {
        "id": video_id, "title": title, "channel": channel,
        "duration": duration, "duration_str": format_ts(duration),
        "description": description, "url": url, "proxy": proxy,
    }

    # ---- Step 2: 挑字幕 ----
    chosen = pick_subtitle(info, langs)
    if not chosen:
        print("NO_SUBTITLE: 该视频无可用字幕(手动/自动都没有)。")
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        print(f"META: {os.path.join(vdir, 'meta.json')}")
        print("提示: 当前版本不做本地转写,无字幕视频暂无法提炼。")
        sys.exit(4)

    lang_code, track_key, is_auto = chosen

    # ---- Step 3: 下载字幕 ----
    sub_cmd = [py, "-m", "yt_dlp",
               "--skip-download", "--proxy", proxy, "--no-warnings"]
    # 自动字幕需要 --write-auto-subs;手动字幕需要 --write-subs
    if is_auto:
        sub_cmd += ["--write-auto-subs"]
    else:
        sub_cmd += ["--write-subs"]
    sub_cmd += ["--sub-langs", lang_code,
                "--sub-format", "vtt/best",
                "-o", os.path.join(vdir, "%(id)s.%(ext)s"), args.url]
    try:
        proc2 = subprocess.run(sub_cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("ERROR: 字幕下载超时。")
        sys.exit(3)

    vtt_file = next((os.path.join(vdir, fn) for fn in os.listdir(vdir)
                     if fn.endswith(".vtt")), None)
    if vtt_file is None:
        print("NO_SUBTITLE: 字幕下载失败或无字幕文件。")
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        print(f"META: {os.path.join(vdir, 'meta.json')}")
        sys.exit(4)

    with open(vtt_file, encoding="utf-8") as f:
        vtt_text = f.read()
    blocks = parse_vtt(vtt_text)
    if not blocks:
        print("NO_SUBTITLE: 字幕内容为空。")
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        sys.exit(4)

    transcript_path = os.path.join(vdir, "transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        for s, t in blocks:
            t_clean = re.sub(r"\s+", " ", t).strip()  # 折叠行内多余空白
            f.write(f"[{format_ts(s)}] {t_clean}\n")

    try:
        os.remove(vtt_file)
    except OSError:
        pass

    write_meta(vdir, {**common_meta, "subtitle_lang": lang_code,
                      "subtitle_manual": not is_auto, "has_subtitle": True,
                      "blocks": len(blocks)})
    print(f"OK: {title}")
    print(f"CHANNEL: {channel}")
    print(f"DURATION: {format_ts(duration)}")
    print(f"LANG: {lang_code} ({'手动' if not is_auto else '自动'})")
    print(f"BLOCKS: {len(blocks)}")
    print(f"DIR: {vdir}")
    print(f"TRANSCRIPT: {transcript_path}")
    print(f"META: {os.path.join(vdir, 'meta.json')}")


if __name__ == "__main__":
    main()
