#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video-digest / fetch_video.py
抓取 YouTube 视频元数据 + 字幕,解析为带时间戳的纯文本 transcript。

用法:
    python fetch_video.py <url1> [url2 url3 ...] [--out <目录>] [--langs en,zh] [--skip-existing]

    # 单条:     python fetch_video.py https://www.youtube.com/watch?v=xxx
    # 批量:     python fetch_video.py url1 url2 url3     (代理只探测一次)
    # 复用存档: python fetch_video.py url --skip-existing (已有 transcript 则跳过)

输出:
    每个视频落在 <out>/<频道>/<video-id>/
    meta.json        视频元数据(标题/频道/时长/简介/章节/字幕语言)
    transcript.txt   带 [MM:SS] 时间戳的纯文本(行内去重合并)

退出码:
    0 全部成功或按预期跳过 | 2 代理/python 环境不可用 | 3 视频不可达 | 4 有视频无字幕
    (批量时: 单个视频失败不中断,继续抓下一个,末尾汇总)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit, urlunsplit

PROXY_CANDIDATES = [
    "http://127.0.0.1:7897",  # Clash 常见端口
    "http://127.0.0.1:7890",  # Clash 旧默认
    "http://127.0.0.1:1087",  # V2rayU 常见
    "http://127.0.0.1:10809",  # v2rayN
]
YOUTUBE_PROBE = "https://www.youtube.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_MARKS = set("♪♫♬♩🎵🎶🎼")  # 音乐符号残留清理
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")  # YouTube 视频 ID 白名单


def sanitize_proxy(proxy_url):
    """脱敏代理 URL：只保留 scheme://host:port，剥掉 userinfo(可能含凭据)。

    代理 URL 形如 http://user:pass@127.0.0.1:7897 —— 打印与落盘时绝不允许出现凭据。
    """
    if not proxy_url:
        return ""
    try:
        parts = urlsplit(proxy_url)
        host = parts.hostname or ""
        port = parts.port
        netloc = host if port is None else f"{host}:{port}"
        scheme = parts.scheme or "http"
        return urlunsplit((scheme, netloc, "", "", ""))
    except Exception:
        # 解析失败兜底：粗暴去掉 @ 之前可能存在的 userinfo
        return proxy_url.rsplit("@", 1)[-1] if "@" in proxy_url else proxy_url


def is_youtube_ref(url_or_id):
    """输入校验：只接受 YouTube 域名链接或形如纯视频 ID 的字符串。

    - http(s) 链接 → host 必须在白名单内(含子域)
    - 非链接 → 必须是合法 video_id 形态
    拒绝其它一切输入，避免把任意 URL/ID 交给 yt-dlp。
    """
    s = (url_or_id or "").strip()
    if not s:
        return False
    if s.lower().startswith(("http://", "https://")):
        try:
            host = (urlsplit(s).hostname or "").lower()
        except Exception:
            return False
        return any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS)
    # 裸 ID：形如 dQw4w9WgXcQ
    return bool(VIDEO_ID_RE.fullmatch(s))


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
    line = re.sub(r"<[^>]+>", "", line)               # 去 html 标签
    line = re.sub(r"\[[^\]]*\]", "", line).strip()    # 去 [Music] 等
    line = "".join(ch for ch in line if ch not in MUSIC_MARKS)  # 去 ♪♫ 残留
    return line.strip()


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


def safe_dirname(channel):
    """频道名 → 安全目录名:去首尾空白与非法字符,压缩中间空白。"""
    name = (channel or "channel").strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r'[^\w\u4e00-\u9fff-]', "_", name).strip("_")
    return name[:60] or "channel"


def extract_chapters(info):
    """从 info 提取章节 → [{start, end, title}] (start/end 为 MM:SS 字符串)。"""
    chapters = []
    for ch in info.get("chapters") or []:
        start = ch.get("start_time") or ch.get("start") or 0
        end = ch.get("end_time") or ch.get("end") or 0
        title = (ch.get("title") or "").strip()
        if title:
            chapters.append({"start": format_ts(start), "end": format_ts(end), "title": title})
    return chapters


def fetch_one(url, proxy, py, root, langs, skip_existing):
    """抓取单个视频,返回 (video_id, status, message)。
    status: ok / skipped / no_subtitle / error
    """
    # ---- Step 1: 元数据 ----
    dump_cmd = [py, "-m", "yt_dlp", "--dump-json", "--skip-download",
                "--proxy", proxy, "--no-warnings", url]
    try:
        proc = subprocess.run(dump_cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return (None, "error", "获取视频信息超时")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-800:]
        low = err.lower()
        if "video unavailable" in low or "is unavailable" in low or "unsupported url" in low or "not found" in low or "unable to extract" in low:
            msg = "视频不可达/链接无效"
        elif "sign in" in low or "age" in low or "confirm" in low or "restricted" in low:
            msg = "视频受限制(需登录/年龄验证/地区限制)"
        else:
            msg = "yt-dlp 获取信息失败"
        return (None, "error", f"{msg}\n{err}")

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return (None, "error", "解析元数据失败")

    video_id = info.get("id") or ""
    if not isinstance(video_id, str) or not VIDEO_ID_RE.fullmatch(video_id):
        return (None, "error", f"video_id 未通过白名单校验,拒绝写盘: {video_id!r}")
    title = info.get("title", "untitled")
    channel = info.get("channel") or info.get("uploader") or "unknown"
    duration = info.get("duration") or 0
    description = (info.get("description") or "")[:2000]
    url_final = f"https://www.youtube.com/watch?v={video_id}"
    safe_channel = safe_dirname(channel)
    vdir = os.path.join(root, safe_channel, video_id)
    chapters = extract_chapters(info)

    common_meta = {
        "id": video_id, "title": title, "channel": channel,
        "duration": duration, "duration_str": format_ts(duration),
        "description": description, "url": url_final, "proxy": sanitize_proxy(proxy),
        "chapters": chapters,  # 空数组也写入,结构稳定
    }

    # --skip-existing: 已有非空 transcript 则跳过
    transcript_path = os.path.join(vdir, "transcript.txt")
    if skip_existing and os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
        return (video_id, "skipped", f"已存在存档,跳过: {vdir}")

    # ---- Step 2: 挑字幕 ----
    chosen = pick_subtitle(info, langs)
    if not chosen:
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        return (video_id, "no_subtitle", f"{title}\n无可用字幕(手动/自动都没有): {vdir}")

    lang_code, track_key, is_auto = chosen

    # ---- Step 3: 下载字幕(失败自动重试一次) ----
    def build_cmd():
        cmd = [py, "-m", "yt_dlp", "--skip-download", "--proxy", proxy, "--no-warnings"]
        cmd += ["--write-auto-subs"] if is_auto else ["--write-subs"]
        cmd += ["--sub-langs", lang_code, "--sub-format", "vtt/best",
                "-o", os.path.join(vdir, "%(id)s.%(ext)s"), url]
        return cmd

    proc2 = None
    for attempt in (1, 2):
        try:
            proc2 = subprocess.run(build_cmd(), capture_output=True, text=True, timeout=180)
            if proc2.returncode == 0:
                break
        except subprocess.TimeoutExpired:
            proc2 = None
            if attempt == 1:
                continue
    # 下载后找 vtt
    vtt_file = next((os.path.join(vdir, fn) for fn in os.listdir(vdir)
                     if fn.endswith(".vtt")), None)
    if vtt_file is None:
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        return (video_id, "no_subtitle", f"{title}\n字幕下载失败或无字幕文件: {vdir}")

    with open(vtt_file, encoding="utf-8") as f:
        vtt_text = f.read()
    blocks = parse_vtt(vtt_text)
    if not blocks:
        write_meta(vdir, {**common_meta, "has_subtitle": False})
        return (video_id, "no_subtitle", f"{title}\n字幕内容为空: {vdir}")

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
    return (video_id, "ok", f"{title} | {channel} | {format_ts(duration)} | {lang_code} | {len(blocks)}块 | {vdir}")


def main():
    ap = argparse.ArgumentParser(description="抓取 YouTube 元数据+字幕(支持多 URL 批量)")
    ap.add_argument("urls", nargs="+", help="YouTube 视频 URL 或 ID(可传多个)")
    ap.add_argument("--out", default=None, help="输出根目录(默认 ~/Documents/video-notes)")
    ap.add_argument("--langs", default="en,zh", help="字幕语言偏好,默认 en,zh")
    ap.add_argument("--skip-existing", action="store_true",
                    help="已有非空 transcript 则跳过(模式 C 复用存档)")
    args = ap.parse_args()

    proxy = pick_proxy()
    if not proxy:
        print("ERROR: 未探测到可用代理,请确认 Clash/V2ray 已开启(常见端口 7897/7890/1087)。")
        sys.exit(2)
    print(f"PROXY: {sanitize_proxy(proxy)}")

    py = find_venv_python()
    if not py:
        print("ERROR: 找不到带 yt-dlp 的 python,请先安装: pip install yt-dlp")
        sys.exit(2)

    langs = [l.strip().lower() for l in args.langs.split(",") if l.strip()]
    root = args.out or os.path.expanduser("~/Documents/video-notes")

    print(f"待抓取 {len(args.urls)} 条视频...\n")
    results = []
    for i, url in enumerate(args.urls, 1):
        print(f"── [{i}/{len(args.urls)}] {url}")
        if not is_youtube_ref(url):
            print("   ✗ ERROR: 仅支持 YouTube 链接或视频 ID(youtube.com / youtu.be / 裸 ID)\n")
            results.append((None, "error", "非 YouTube 输入,已拒绝"))
            continue
        try:
            vid, status, message = fetch_one(url, proxy, py, root, langs, args.skip_existing)
            results.append((vid, status, message))
        except Exception as e:
            results.append((None, "error", str(e)))
        if status == "ok":
            print(f"   ✓ OK: {message}\n")
        elif status == "skipped":
            print(f"   ⏭ 跳过: {message}\n")
        elif status == "no_subtitle":
            print(f"   ⚠ 无字幕: {message}\n")
        else:
            print(f"   ✗ ERROR: {message}\n")

    # ---- 汇总 ----
    print("=" * 50)
    print(f"汇总: {len(results)} 条")
    ok_count = 0
    for vid, status, message in results:
        if status == "ok":
            ok_count += 1
            print(f"  ✓ OK       | {message.split('|')[0][:50]}")
        elif status == "skipped":
            print(f"  ⏭ 已存在   | {message}")
        elif status == "no_subtitle":
            print(f"  ⚠ 无字幕   | {message.splitlines()[0][:60]}")
        else:
            print(f"  ✗ ERROR    | {message.splitlines()[0][:60]}")

    # 退出码: 有 error → 3; 有 no_subtitle → 4; 全 ok/skipped → 0
    if any(s == "error" for _, s, _ in results):
        sys.exit(3)
    if any(s == "no_subtitle" for _, s, _ in results):
        sys.exit(4)
    sys.exit(0)


if __name__ == "__main__":
    main()
