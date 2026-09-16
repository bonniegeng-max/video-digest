# Changelog

## 2.0.1 — 2026-09-17

- Declared the Doctor, temporary cache writes, transcript retrieval, and agent note-generation layers in the top-level manifest description.
- Added explicit temporary-write scope to allowed tools.
- Clarified the boundary between caption fetching and Research-mode web verification.
- Replaced ambiguous autonomy wording with host confirmation requirements for every state-changing action.
- Increased fixed localhost port-probe timeouts to avoid a scanner false positive.

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
