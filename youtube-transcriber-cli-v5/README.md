# YouTube Transcript Collector v1.3

A beginner-friendly Python tool for collecting YouTube transcripts from one video or a batch. It provides both a local web interface and a command-line interface and does not require a YouTube API key.

> For personal research, archival, accessibility, and licensed-use workflows only. Users are responsible for platform and publisher terms. Do not redistribute copyrighted content.

## What is new in v1.3

- Deduplicates videos by the normalized 11-character YouTube video ID.
- Uses stricter YouTube hostname validation.
- Supports plain text, timestamped text, JSON, SRT, and WebVTT.
- Supports multiple preferred transcript languages.
- Shows available transcript languages when the requested language is missing.
- Adds per-video progress in the web app.
- Adds per-result copy, download, retry, and Open YouTube controls.
- Adds batch search, Copy All, combined download, and Retry Failed.
- Lets the web user choose whether files are automatically saved.
- Centralizes output-file handling.
- Adds explicit `requests` dependency and automated tests.
- Ignores local output files and Python cache files in Git.

## Project structure

```text
youtube-transcriber-cli-v5/
├─ app/
│  ├─ assets/
│  │  └─ logo.png        # optional; your existing logo can stay here
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ output.py
│  ├─ transcriber.py
│  └─ web.py
├─ output/
│  └─ .gitkeep
├─ tests/
│  ├─ test_output.py
│  └─ test_transcriber.py
├─ .gitignore
├─ main.py
├─ web_app.py
├─ README.md
├─ requirements.txt
└─ requirements-dev.txt
```

## Windows setup

Open PowerShell in the `youtube-transcriber-cli-v5` folder.

```powershell
python -m ensurepip --upgrade
python -m pip install -r requirements.txt
```

## Start the web app

```powershell
python web_app.py
```

Open:

```text
http://127.0.0.1:8000
```

Press `Ctrl+C` in PowerShell when you want to stop the local server.

## Web app workflow

1. Paste one YouTube URL or video ID per line.
2. Enter preferred language codes such as `en` or `en, es`.
3. Choose an output format.
4. Leave **Save files to output/** checked if you want local files.
5. Click **Get transcripts**.
6. Use Copy, Download, Open YouTube, search, Retry Failed, or combined download as needed.

## CLI examples

One video:

```powershell
python main.py "https://www.youtube.com/watch?v=GAxk62-9yYc"
```

From a text file:

```powershell
python main.py --input-file urls.txt
```

Preferred languages:

```powershell
python main.py "URL" --languages en es
```

Timestamped text:

```powershell
python main.py "URL" --format timestamped
```

SRT:

```powershell
python main.py "URL" --format srt
```

WebVTT:

```powershell
python main.py "URL" --format vtt
```

JSON:

```powershell
python main.py "URL" --format json
```

Do not save:

```powershell
python main.py "URL" --no-save
```

Do not overwrite existing transcript files:

```powershell
python main.py "URL" --skip-existing
```

The older single-language form remains supported:

```powershell
python main.py "URL" --language en
```

## Run the automated tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Notes

- A transcript must exist and be retrievable from YouTube.
- Some videos have transcripts disabled or unavailable.
- Some network environments or hosting providers may be blocked by YouTube.
- Video title/channel/date metadata is best-effort and transcript collection continues when metadata is incomplete.
- `app/assets/logo.png` is optional. If it is absent, the web UI shows a built-in `YT` mark instead.
