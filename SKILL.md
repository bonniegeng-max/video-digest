---
name: video-digest
version: 2.0.1
description: Check the pinned transcript environment, fetch public YouTube captions into a restricted temporary cache, retrieve excerpts by video ID, and turn those captions or a supplied transcript into timestamped Quick, Deep, or Research notes.
allowed-tools: RunCommand, Read, Write, WebSearch, WebFetch
metadata:
  openclaw:
    requires:
      bins: [python3]
    install:
      - kind: uv
        package: "yt-dlp==2026.8.19"
        bins: [yt-dlp]
---

# Video Deep Reader

## What It Does

Turn a YouTube video or supplied transcript into a useful reading artifact:

- **Quick**: decide in a minute whether the video is worth watching.
- **Deep**: understand the argument, evidence, structure, and important timestamps.
- **Research**: verify selected material claims against public primary sources.

The bundled fetch helper retrieves public metadata and subtitles; Research mode may additionally verify selected claims with public sources. The agent creates the semantic notes from these inputs.

Bundled components are deliberately separate:

- `doctor.py` checks the local dependency and optional network readiness.
- `fetch_video.py` retrieves public metadata and subtitles into the declared temporary cache.
- `retrieve.py` returns timestamped excerpts from that cache by validated video ID.
- The agent applies this file and `references/output-modes.md` to create the semantic notes.

## When to Use

Invoke when the user:

- provides a YouTube URL or video ID and asks to summarize, analyze, or understand it;
- pastes or uploads a transcript and asks for video notes;
- asks a follow-up question about a previously fetched video;
- wants to compare several videos or decide which one deserves deeper attention;
- asks to verify important claims made in a video.

A bare YouTube URL is enough to start. Do not require the phrase “视频深读.”

Do not invoke for:

- downloading the video or audio;
- bypassing login, age, geographic, paywall, or access controls;
- summarizing a video that has neither accessible subtitles nor a user-supplied transcript;
- publishing derived content without an explicit request.

## Output Language

Respond in the language of the user's current request. If unclear, ask once. Preserve quotations in their original language and add a translation only when useful.

Pass `--ui-lang zh` to bundled scripts for Chinese CLI messages; otherwise use the English default.

## Select the Mode

| Request signal | Mode | Default output |
|---|---|---|
| Bare link, “总结”, “讲了什么”, “值不值得看” | Quick | One-screen decision card |
| “深读”, “完整笔记”, “论证过程”, “详细整理” | Deep | Timestamped structured notes |
| “核验”, “查证”, “research”, “是真的吗” | Research | Deep notes plus selected claim verification |
| Two or more links | Batch Quick | One Quick card per video |

If the requested depth is ambiguous, use Quick as the content mode. Still follow host confirmation requirements for package installation, file creation, and every other state-changing action.

## Step 1: Check the Environment

Run the read-only doctor before the first URL fetch in a session:

```bash
python3 <skill_dir>/scripts/doctor.py --ui-lang zh
```

Add `--network` only when a network diagnosis is needed. Doctor never installs packages or changes configuration.

If the pinned dependency is missing, show the exact repair command:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r <skill_dir>/requirements.lock
```

Do not install anything without explicit user approval.

## Step 2: Get a Transcript

### YouTube URL or video ID

Run:

```bash
python3 <skill_dir>/scripts/fetch_video.py "<youtube-url>" --ui-lang zh
```

For a local proxy, pass only the loopback port:

```bash
python3 <skill_dir>/scripts/fetch_video.py "<youtube-url>" --proxy-port 7890 --ui-lang zh
```

The script:

- validates YouTube hosts and video IDs;
- calls the pinned `yt-dlp` Python API directly;
- never invokes a shell or external executable;
- accepts only a loopback proxy port and no proxy credentials;
- writes `meta.json` and `transcript.txt` to the managed system temporary directory;
- prints the cache directory as JSON.

Temporary cache is not a durable archive. Create a user-visible note file only when the user explicitly requests one.

### Supplied transcript

If the user provides transcript text or a transcript file, skip YouTube fetching. Treat it as `User-provided transcript` and preserve any timestamps already present.

### No subtitles or failed fetch

Do not stop at “unsupported.” Offer the smallest viable fallback:

1. Ask the user to paste or upload a transcript.
2. If the user already supplied an audio/video file, use an available transcription capability only with the user's request.
3. If neither is available, explain the exact limitation without inventing content.

## Step 3: Produce the Requested Output

Follow `references/output-modes.md`.

### Quick

Keep it to one screen:

- title, channel, duration, and source link;
- 2–3 sentence summary;
- five timestamped takeaways;
- one “worth watching if…” judgment;
- important uncertainty or missing context.

### Deep

Include:

- concise overview;
- timestamped structure;
- argument map: claim → reasoning → evidence → limitation;
- `Video statement` and `Author opinion` as separate labels;
- notable quotations;
- unanswered questions and useful follow-ups.

Do not call a statement a verified fact merely because it appears in the video.

### Research

Start from Deep, then verify only material claims that affect the conclusion.

- Prefer primary sources, official documentation, papers, or original datasets.
- Attach each verification result to the corresponding video timestamp.
- Label each claim `Supported`, `Partly supported`, `Contradicted`, or `Not verified`.
- State source date and scope.
- Do not perform broad web research when the user only asked for a summary.

### Batch Quick

For each video provide:

- one-sentence thesis;
- three key timestamps;
- evidence quality;
- novelty;
- recommendation: Deep now / Save / Skip.

Compare videos only on common dimensions.

## Follow-up Retrieval

The retrieval script accepts a video ID, never an arbitrary file path:

```bash
python3 <skill_dir>/scripts/retrieve.py <video-id> "keyword" --ui-lang zh
python3 <skill_dir>/scripts/retrieve.py <video-id> --at 3:20 --ui-lang zh
python3 <skill_dir>/scripts/retrieve.py <video-id> --list --ui-lang zh
```

It reads only transcripts created under the managed temporary cache. Quote the relevant timestamp range in the answer.

## Content Integrity

- Preserve what the source actually says; remove filler, not substance.
- Separate a video's claims from external verification.
- Keep numbers, dates, named entities, caveats, and uncertainty.
- Trust visible slide text over an obvious transcription error when the user supplies frames or screenshots.
- Do not attribute a claim to a speaker unless the source supports the attribution.
- Do not turn the summary into promotional copy unless explicitly requested.

## Completion Standard

- The selected mode matches the request.
- Every major point can be traced to a timestamp or labeled transcript section.
- Claims and opinions remain separate.
- Research mode includes source-backed verification and scope.
- Fetch failures produce a usable transcript fallback.
- No package installation, durable file write, publishing, or external state change occurs without explicit approval.
