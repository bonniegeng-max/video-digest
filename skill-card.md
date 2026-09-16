## Description

Video Deep Reader turns a YouTube link, video ID, or supplied transcript into timestamped Quick, Deep, or Research notes.

## Publisher

[bonniegeng-max](https://clawhub.ai/bonniegeng-max)

## License

MIT

## Use Cases

- Decide whether a video is worth watching.
- Create complete timestamped learning notes.
- Separate video statements from author opinions.
- Verify selected material claims against primary sources.
- Compare several videos using the same criteria.
- Answer follow-up questions from a managed transcript cache.

## Dependencies

- Python 3.9 or newer
- `yt-dlp==2026.8.19`, pinned in `requirements.lock`
- YouTube network access for URL-based fetching

The skill also works from a user-supplied transcript without YouTube access or `yt-dlp`.

## Boundaries

- Fetching accepts only YouTube URLs or strict video IDs.
- The fetcher uses the pinned Python API and does not execute a shell.
- Transcript retrieval cannot read arbitrary paths.
- Cached transcripts use the system temporary directory.
- Research mode uses public web sources only when requested.
- No installation, publishing, login, or durable file write happens automatically.

## Version

2.0.4
