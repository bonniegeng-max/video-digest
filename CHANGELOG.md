# Changelog

## 2.0.0 — 2026-09-16

- Repositioned the skill as `Video Deep Reader`.
- Added Quick, Deep, Research, and Batch Quick output contracts.
- Made a bare YouTube URL sufficient to trigger a useful Quick result.
- Added a transcript-first fallback when YouTube subtitles are unavailable.
- Added a read-only environment Doctor.
- Pinned `yt-dlp==2026.8.19` with a verified wheel hash.
- Replaced subprocess execution with the pinned `yt-dlp` Python API.
- Restricted proxy input to a loopback port without credentials.
- Moved fetched material from persistent Documents storage to a managed temporary cache.
- Restricted follow-up retrieval to valid video IDs in the managed cache.
- Changed language behavior to follow the user's current request.
- Removed automatic note persistence and index mutation.
