#!/usr/bin/env python3
"""Check Video Deep Reader dependencies without installing or changing anything."""

import argparse
import json
import sys
import urllib.request

PINNED_VERSION = "2026.8.19"
REPAIR = (
    "python3 -m venv .venv && "
    ".venv/bin/python -m pip install --require-hashes -r requirements.lock"
)


def yt_dlp_status():
    try:
        import yt_dlp
    except ImportError:
        return {"ok": False, "installed": None, "required": PINNED_VERSION}
    installed = yt_dlp.version.__version__
    normalize = lambda value: tuple(int(part) for part in value.split("."))
    return {
        "ok": normalize(installed) == normalize(PINNED_VERSION),
        "installed": installed,
        "required": PINNED_VERSION,
    }


def network_status(proxy_port=None):
    handlers = []
    if proxy_port:
        proxy = f"http://127.0.0.1:{proxy_port}"
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    try:
        request = urllib.request.Request("https://www.youtube.com", method="HEAD")
        status = opener.open(request, timeout=6).status
        return {"checked": True, "ok": status < 400, "status": status}
    except Exception as exc:
        return {"checked": True, "ok": False, "error": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description="Read-only Video Deep Reader check.")
    parser.add_argument("--network", action="store_true", help="Also test YouTube access")
    parser.add_argument("--proxy-port", type=int, choices=range(1, 65536))
    parser.add_argument("--ui-lang", choices=("en", "zh"), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = {
        "python": {
            "ok": sys.version_info >= (3, 9),
            "version": ".".join(map(str, sys.version_info[:3])),
            "required": ">=3.9",
        },
        "yt_dlp": yt_dlp_status(),
        "network": {"checked": False},
    }
    if args.network:
        notice = (
            "将向 YouTube 发送一次有时限的连通性检查。"
            if args.ui_lang == "zh"
            else "Sending one bounded connectivity check to YouTube."
        )
        print(notice, file=sys.stderr)
        result["network"] = network_status(args.proxy_port)
    result["ready"] = (
        result["python"]["ok"]
        and result["yt_dlp"]["ok"]
        and (not args.network or result["network"]["ok"])
    )
    if not result["yt_dlp"]["ok"]:
        result["repair"] = REPAIR

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.ui_lang == "zh":
        print("Video Deep Reader 环境检查")
        print(f"- Python：{'通过' if result['python']['ok'] else '不通过'}")
        print(f"- yt-dlp：{'通过' if result['yt_dlp']['ok'] else '不通过'}")
        if args.network:
            print(f"- YouTube 网络：{'通过' if result['network']['ok'] else '不通过'}")
        if result.get("repair"):
            print(f"- 修复命令：{result['repair']}")
    else:
        print("Video Deep Reader environment check")
        print(f"- Python: {'pass' if result['python']['ok'] else 'fail'}")
        print(f"- yt-dlp: {'pass' if result['yt_dlp']['ok'] else 'fail'}")
        if args.network:
            print(f"- YouTube network: {'pass' if result['network']['ok'] else 'fail'}")
        if result.get("repair"):
            print(f"- Repair: {result['repair']}")
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
