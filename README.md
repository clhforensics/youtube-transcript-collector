
# YouTube Transcript Collector RC

A beginner-friendly tool that takes one or more YouTube URLs and returns transcript text or JSON.

## What is new in this release candidate

- Pulls transcript text from one URL or a full batch
- Saves each result automatically
- Includes video title, channel name, and published date when available
- Web app uses your provided logo and a red/navy color system
- Copy button for each transcript result
- Simple local web interface and CLI
- No API key required

## Important disclaimer

Quick and dirty transcript extractor.

**NOTE:** For personal research, archival, accessibility, and licensed-use workflows only; users are responsible for platform and publisher terms; **DO NOT** redistribute copyrighted content.

## Project structure

```text
youtube-transcriber-cli-v5/
├─ app/
│  ├─ assets/
│  │  └─ logo.png
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ transcriber.py
│  └─ web.py
├─ main.py
├─ web_app.py
├─ README.md
└─ requirements.txt
```

## First-time setup on Windows

Open PowerShell in the project folder and run:

```powershell
python -m ensurepip --upgrade
python -m pip install -r requirements.txt
```

## CLI usage

One URL:

```powershell
python main.py "https://www.youtube.com/watch?v=GAxk62-9yYc"
```

Multiple URLs:

```powershell
python main.py "URL_1" "URL_2"
```

From a text file:

```powershell
python main.py --input-file urls.txt
```

JSON output:

```powershell
python main.py "https://www.youtube.com/watch?v=GAxk62-9yYc" --format json
```

Do not save files:

```powershell
python main.py "https://www.youtube.com/watch?v=GAxk62-9yYc" --no-save
```

### CLI output includes

- Title
- Channel name when available
- Published date when available
- Video ID
- Saved file path

Saved filenames now prefer:

```text
YYYY-MM-DD - Channel Name - Video Title - VIDEOID.txt
```

If any metadata is missing, the app falls back gracefully.

## Web app usage

Start the web app:

```powershell
python web_app.py
```

Then open this in your browser:

```text
http://127.0.0.1:8000
```

Paste one or many YouTube URLs, choose text or json, and click **Get transcripts**.

## Notes

- This tool only works when a YouTube transcript is available.
- Some videos do not have captions or do not allow transcript retrieval.
- Video metadata is fetched without an API key and may be partially unavailable for some videos.
- When metadata cannot be found, transcript extraction still continues.
- When a transcript cannot be retrieved, the app shows an error instead of crashing.
