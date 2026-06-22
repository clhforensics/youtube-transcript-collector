
from __future__ import annotations

import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from app.transcriber import (
    TranscriptionError,
    choose_best_filename,
    get_transcript_for_url,
    transcript_to_json,
    transcript_to_text,
)

HOST = "127.0.0.1"
PORT = 8000
OUTPUT_DIR = "output"
DISCLAIMER = (
    "For personal research, archival, accessibility, and licensed-use workflows only. "
    "Users are responsible for platform and publisher terms. Do not redistribute "
    "copyrighted content."
)


def save_output(output_dir: str, base_name: str, content: str, fmt: str) -> Path:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    extension = "json" if fmt == "json" else "txt"
    target = folder / f"{base_name}.{extension}"
    target.write_text(content, encoding="utf-8")
    return target


def parse_bulk_urls(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.replace("\r", "\n").split("\n")]
    urls: list[str] = []
    seen: set[str] = set()

    for line in lines:
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            urls.append(line)

    return urls


def load_logo_data_uri() -> str:
    asset_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    if not asset_path.exists():
        return ""
    data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def render_page(
    *,
    raw_urls: str = "",
    language: str = "en",
    fmt: str = "text",
    results: list[dict] | None = None,
    error: str = "",
) -> str:
    results = results or []
    success_count = len(results)
    total_chars = sum(len(item["content"]) for item in results)
    logo_uri = load_logo_data_uri()

    results_html = ""
    if error:
        results_html += f'<div class="alert alert-error">{html.escape(error)}</div>'

    if results:
        results_html += f'''
<section class="summary-bar">
  <div class="summary-pill">
    <span class="summary-label">Completed</span>
    <strong>{success_count}</strong>
  </div>
  <div class="summary-pill">
    <span class="summary-label">Format</span>
    <strong>{html.escape(fmt.upper())}</strong>
  </div>
  <div class="summary-pill">
    <span class="summary-label">Characters</span>
    <strong>{total_chars:,}</strong>
  </div>
</section>
'''

    for item in results:
        pretty_title = html.escape(item.get("title") or item["video_id"])
        generation_badge = "Auto captions" if item.get("is_generated") else "Manual captions"
        published_value = html.escape(item.get("published_date") or "Unknown")
        channel_value = html.escape(item.get("channel_name") or "Unknown")
        results_html += f'''
<section class="result-card">
  <div class="result-header">
    <div class="result-heading">
      <div class="eyebrow">Transcript {html.escape(str(item["index"]))}</div>
      <h2>{pretty_title}</h2>
      <div class="result-subtitle">{channel_value} · {published_value}</div>
    </div>
    <button type="button" class="copy-btn" data-target="{html.escape(item["target_id"])}">Copy</button>
  </div>

  <div class="meta-grid">
    <div class="meta-item">
      <span class="meta-label">Saved</span>
      <code>{html.escape(item["saved_path"])}</code>
    </div>
    <div class="meta-item">
      <span class="meta-label">Format</span>
      <span class="badge">{html.escape(item["format"].upper())}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Video ID</span>
      <code>{html.escape(item["video_id"])}</code>
    </div>
    <div class="meta-item">
      <span class="meta-label">Language</span>
      <span class="badge">{html.escape(item["language_code"])}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Caption type</span>
      <span class="badge">{html.escape(generation_badge)}</span>
    </div>
  </div>

  <textarea id="{html.escape(item["target_id"])}" readonly>{html.escape(item["content"])}</textarea>
</section>
'''

    text_selected = "selected" if fmt == "text" else ""
    json_selected = "selected" if fmt == "json" else ""
    logo_html = f'<img src="{logo_uri}" alt="YouTube Transcript Collector logo" class="logo">' if logo_uri else ""

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>YouTube Transcript Collector</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: rgba(255, 255, 255, 0.92);
      --line: #d7e0ec;
      --text: #0c2245;
      --muted: #5e6f88;
      --red: #ef1d1d;
      --red-dark: #c61313;
      --navy: #0b2c5a;
      --navy-deep: #081d3d;
      --warm: #ff8b2b;
      --shadow: 0 24px 60px rgba(8, 29, 61, 0.10);
      --shadow-soft: 0 16px 40px rgba(8, 29, 61, 0.07);
      --radius: 24px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, "Segoe UI", Roboto, Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(239, 29, 29, 0.08), transparent 22%),
        radial-gradient(circle at top right, rgba(255, 139, 43, 0.09), transparent 18%),
        linear-gradient(180deg, #f7f9fc 0%, #eef2f8 100%);
    }}

    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 18px 54px;
    }}

    .hero,
    .result-card,
    .summary-bar,
    .alert {{
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.9);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
    }}

    .hero {{
      overflow: hidden;
      position: relative;
      margin-bottom: 20px;
    }}

    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(135deg, rgba(239, 29, 29, 0.06), transparent 35%),
        linear-gradient(315deg, rgba(11, 44, 90, 0.06), transparent 30%);
      pointer-events: none;
    }}

    .hero-content {{
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
      gap: 28px;
      padding: 28px;
      align-items: center;
    }}

    .logo {{
      display: block;
      width: 100%;
      max-width: 390px;
      height: auto;
      filter: drop-shadow(0 18px 40px rgba(8, 29, 61, 0.10));
    }}

    .brand-row {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(11, 44, 90, 0.06);
      border: 1px solid rgba(11, 44, 90, 0.08);
      color: var(--navy);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }}

    .brand-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--red), var(--warm));
      box-shadow: 0 0 0 6px rgba(239, 29, 29, 0.10);
    }}

    h1 {{
      margin: 0 0 12px;
      font-size: clamp(2rem, 4vw, 3.25rem);
      line-height: 1.02;
      letter-spacing: -0.04em;
      color: var(--navy-deep);
    }}

    .lead {{
      margin: 0 0 20px;
      max-width: 720px;
      color: var(--muted);
      line-height: 1.68;
      font-size: 1.03rem;
    }}

    .quick-notes {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 22px;
    }}

    .quick-note,
    .summary-pill,
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
    }}

    .quick-note {{
      padding: 10px 14px;
      background: white;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
      box-shadow: var(--shadow-soft);
    }}

    label {{
      display: block;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--navy);
    }}

    input,
    select,
    textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      font: inherit;
      color: var(--text);
      background: rgba(255, 255, 255, 0.98);
      outline: none;
      transition: border-color 0.18s ease, box-shadow 0.18s ease;
    }}

    input:focus,
    select:focus,
    textarea:focus {{
      border-color: rgba(11, 44, 90, 0.35);
      box-shadow: 0 0 0 4px rgba(239, 29, 29, 0.10);
    }}

    #urls {{
      min-height: 176px;
      resize: vertical;
      line-height: 1.58;
    }}

    .hint {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 220px 185px;
      gap: 14px;
      align-items: end;
      margin-top: 18px;
    }}

    button {{
      border: 0;
      border-radius: 18px;
      padding: 15px 18px;
      font: inherit;
      font-weight: 800;
      letter-spacing: 0.01em;
      cursor: pointer;
      color: white;
      background: linear-gradient(135deg, var(--red), #ff5533);
      box-shadow: 0 14px 30px rgba(239, 29, 29, 0.22);
      transition: transform 0.16s ease, box-shadow 0.16s ease, filter 0.16s ease;
    }}

    button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 18px 34px rgba(239, 29, 29, 0.28);
      filter: brightness(1.02);
    }}

    .summary-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 18px 0;
      padding: 14px;
      box-shadow: var(--shadow-soft);
    }}

    .summary-pill {{
      padding: 12px 16px;
      background: white;
      border: 1px solid var(--line);
    }}

    .summary-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .summary-pill strong {{
      font-size: 15px;
      color: var(--navy-deep);
    }}

    .result-card {{
      padding: 22px;
      margin-bottom: 18px;
    }}

    .result-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }}

    .eyebrow {{
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--red-dark);
      margin-bottom: 6px;
    }}

    h2 {{
      margin: 0;
      font-size: 1.35rem;
      line-height: 1.25;
      letter-spacing: -0.02em;
      color: var(--navy-deep);
    }}

    .result-subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .copy-btn {{
      min-width: 94px;
      padding: 12px 14px;
      border-radius: 14px;
      box-shadow: none;
      background: linear-gradient(135deg, var(--navy), var(--navy-deep));
    }}

    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}

    .meta-item {{
      padding: 12px 14px;
      border-radius: 16px;
      background: #fbfcfe;
      border: 1px solid var(--line);
      min-height: 76px;
    }}

    .meta-label {{
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    code {{
      display: inline-block;
      max-width: 100%;
      overflow-wrap: anywhere;
      padding: 4px 8px;
      border-radius: 10px;
      background: #eef4ff;
      color: var(--navy);
      font-family: "Cascadia Code", Consolas, monospace;
      font-size: 12px;
    }}

    .badge {{
      padding: 6px 10px;
      background: rgba(11, 44, 90, 0.08);
      color: var(--navy);
      font-size: 13px;
      font-weight: 800;
    }}

    .result-card textarea {{
      min-height: 280px;
      resize: vertical;
      line-height: 1.58;
      font-family: "Cascadia Code", Consolas, monospace;
      font-size: 14px;
      background: rgba(255, 255, 255, 0.98);
    }}

    .alert {{
      margin-bottom: 16px;
      padding: 16px 18px;
      white-space: pre-wrap;
      box-shadow: var(--shadow-soft);
    }}

    .alert-error {{
      background: rgba(255, 242, 242, 0.96);
      border-color: rgba(239, 29, 29, 0.18);
      color: #8e1b1b;
    }}

    .app-footer {{
      margin-top: 22px;
      padding: 16px 18px 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}

    .app-footer strong {{
      color: var(--navy-deep);
    }}

    @media (max-width: 1040px) {{
      .hero-content {{
        grid-template-columns: 1fr;
      }}

      .logo {{
        max-width: 300px;
      }}

      .meta-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 760px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}

      .result-header {{
        flex-direction: column;
        align-items: flex-start;
      }}

      button,
      .copy-btn {{
        width: 100%;
      }}
    }}

    @media (max-width: 560px) {{
      .wrap {{
        padding: 16px 12px 28px;
      }}

      .hero-content,
      .result-card {{
        padding: 18px;
      }}

      .meta-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="hero-content">
        <div>
          <div class="brand-row"><span class="brand-dot"></span> Release candidate</div>
          <h1>Pull clean transcripts from one YouTube URL or a full batch.</h1>
          <p class="lead">
            Paste one or many YouTube URLs, choose text or JSON, and the app will fetch transcripts,
            add the video title, channel name, and published date when available, save each result
            automatically, and let you copy any transcript with one click.
          </p>

          <div class="quick-notes">
            <div class="quick-note">Automatic save to <code>output</code></div>
            <div class="quick-note">Video titles and channel names</div>
            <div class="quick-note">Date included when available</div>
          </div>

          <form method="post" action="/">
            <label for="urls">YouTube URLs</label>
            <textarea id="urls" name="urls" placeholder="Paste one YouTube URL per line">{html.escape(raw_urls)}</textarea>
            <div class="hint">Tip: duplicate links are ignored automatically.</div>

            <div class="grid">
              <div>
                <label for="language">Language code</label>
                <input id="language" name="language" value="{html.escape(language)}" placeholder="en">
              </div>
              <div>
                <label for="format">Output format</label>
                <select id="format" name="format">
                  <option value="text" {text_selected}>text</option>
                  <option value="json" {json_selected}>json</option>
                </select>
              </div>
              <div>
                <button type="submit">Get transcripts</button>
              </div>
            </div>
          </form>
        </div>

        <div>{logo_html}</div>
      </div>
    </section>

    {results_html}

    <footer class="app-footer">
      <strong>Disclaimer:</strong> {html.escape(DISCLAIMER)}
    </footer>
  </main>

  <script>
    document.querySelectorAll(".copy-btn").forEach(function(button) {{
      button.addEventListener("click", async function() {{
        const id = button.getAttribute("data-target");
        const target = document.getElementById(id);
        if (!target) return;

        try {{
          await navigator.clipboard.writeText(target.value);
        }} catch (error) {{
          target.select();
          document.execCommand("copy");
        }}

        const original = button.textContent;
        button.textContent = "Copied";
        setTimeout(function() {{
          button.textContent = original;
        }}, 1200);
      }});
    }});
  </script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send_html(render_page())

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(body)

        raw_urls = (form.get("urls", [""])[0]).strip()
        language = (form.get("language", ["en"])[0] or "en").strip()
        fmt = (form.get("format", ["text"])[0] or "text").strip().lower()
        if fmt not in {"text", "json"}:
            fmt = "text"

        urls = parse_bulk_urls(raw_urls)
        if not urls:
            self._send_html(
                render_page(
                    raw_urls=raw_urls,
                    language=language,
                    fmt=fmt,
                    error="Please paste at least one YouTube URL.",
                )
            )
            return

        results = []
        errors = []

        for index, url in enumerate(urls, start=1):
            try:
                result = get_transcript_for_url(url=url, language=language)
                content = transcript_to_json(result) if fmt == "json" else transcript_to_text(result["segments"])
                base_name = choose_best_filename(result)
                saved_path = save_output(OUTPUT_DIR, base_name, content, fmt)
                results.append(
                    {
                        "index": index,
                        "title": result.get("title") or result["video_id"],
                        "channel_name": result.get("channel_name"),
                        "published_date": result.get("published_date"),
                        "video_id": result["video_id"],
                        "language_code": result["language_code"],
                        "is_generated": result["is_generated"],
                        "format": fmt,
                        "saved_path": str(saved_path),
                        "content": content,
                        "target_id": f"result-{index}",
                    }
                )
            except (TranscriptionError, ValueError) as exc:
                errors.append(f"{url}: {exc}")

        error_text = ""
        if errors:
            error_text = "Some URLs could not be processed:\n" + "\n".join(errors)

        self._send_html(
            render_page(
                raw_urls=raw_urls,
                language=language,
                fmt=fmt,
                results=results,
                error=error_text,
            )
        )

    def _send_html(self, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        return


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Open http://{HOST}:{PORT}")
    print(DISCLAIMER)
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
