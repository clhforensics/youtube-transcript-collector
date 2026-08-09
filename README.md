# YouTube Transcript Collector v1.3

A beginner-friendly Python utility for collecting YouTube transcripts for personal research, archival, accessibility, and licensed-use workflows.

The application includes:

- A local browser interface
- A command-line interface
- Single-video and batch collection
- Plain text, timestamped text, JSON, SRT, and WebVTT output
- Multiple preferred transcript languages
- Per-video batch progress and failure recovery
- Transcript search, copy, download, combined download, and retry tools
- Automatic filename creation using available video metadata
- Optional automatic saving to the local `output/` folder
- Video-ID normalization to prevent duplicate collection from different YouTube URL forms
- Automated tests for URL parsing and output formatting

> **Important:** Users are responsible for YouTube/platform terms and publisher rights. Do not redistribute copyrighted content without permission.

## Application folder

All application code is inside:

```text
youtube-transcriber-cli-v5/
```

For installation, web-app instructions, CLI examples, and testing instructions, open:

```text
youtube-transcriber-cli-v5/README.md
```

## Quick start on Windows

Open PowerShell inside `youtube-transcriber-cli-v5` and run:

```powershell
python -m pip install -r requirements.txt
python web_app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Version 1.3 highlights

Version 1.3 keeps the same lightweight Python architecture while improving reliability and usability:

- Strict YouTube hostname validation
- Duplicate detection by normalized 11-character video ID
- Timestamped transcript output
- SRT and WebVTT subtitle export
- Preferred language fallback
- Available-language feedback when a requested language is missing
- Per-video batch progress
- Individual and combined downloads
- Search across collected transcript results
- Retry controls for failed videos
- Shared output-file handling
- Repository cleanup through `.gitignore`
- Automated tests

No API key is required by this application.
