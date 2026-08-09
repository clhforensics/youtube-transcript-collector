from __future__ import annotations

import base64
import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.output import extension_for_format, save_output
from app.transcriber import (
    TranscriptionError,
    choose_best_filename,
    extract_video_id,
    get_transcript_for_url,
    render_transcript,
)

HOST = "127.0.0.1"
PORT = 8000
OUTPUT_DIR = "output"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISCLAIMER = (
    "For personal research, archival, accessibility, and licensed-use workflows only. "
    "Users are responsible for platform and publisher terms. Do not redistribute "
    "copyrighted content."
)


def load_logo_data_uri() -> str:
    asset_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    if not asset_path.exists():
        return ""
    mime = mimetypes.guess_type(asset_path.name)[0] or "image/png"
    data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def render_page() -> str:
    logo_uri = load_logo_data_uri()
    logo_html = (
        f'<img class="brand-logo" src="{logo_uri}" alt="Application logo">'
        if logo_uri
        else '<div class="brand-mark" aria-hidden="true">YT</div>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube Transcript Collector</title>
<style>
:root {{
  color-scheme: light;
  --navy:#14213d; --navy-2:#1d2d50; --red:#d62828; --red-dark:#a91f1f;
  --bg:#f6f7fb; --card:#ffffff; --text:#172033; --muted:#667085;
  --border:#d9dee8; --error:#b42318; --shadow:0 18px 45px rgba(20,33,61,.10);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:linear-gradient(180deg,#eef1f7 0,#f8f9fc 280px); color:var(--text);
}}
button,input,textarea,select {{ font:inherit; }}
button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,a:focus-visible {{
  outline:3px solid rgba(214,40,40,.30); outline-offset:2px;
}}
.shell {{ width:min(1180px,calc(100% - 32px)); margin:0 auto; padding:28px 0 60px; }}
.hero {{
  background:linear-gradient(135deg,var(--navy),var(--navy-2)); color:white; border-radius:22px;
  padding:28px; box-shadow:var(--shadow); display:flex; gap:18px; align-items:center;
}}
.brand-logo {{ width:76px; height:76px; object-fit:contain; background:white; border-radius:16px; padding:7px; }}
.brand-mark {{ width:76px; height:76px; display:grid; place-items:center; border-radius:16px; background:white; color:var(--red); font-weight:900; font-size:26px; }}
.hero h1 {{ margin:0 0 6px; font-size:clamp(25px,4vw,38px); }}
.hero p {{ margin:0; color:#dfe6f3; max-width:760px; }}
.panel {{ margin-top:22px; background:var(--card); border:1px solid var(--border); border-radius:18px; padding:22px; box-shadow:var(--shadow); }}
.grid {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:16px; }}
.field {{ display:flex; flex-direction:column; gap:7px; }}
.field.wide {{ grid-column:1/-1; }}
label {{ font-weight:750; font-size:14px; }}
.help {{ color:var(--muted); font-size:12px; }}
textarea,input,select {{
  width:100%; border:1px solid var(--border); border-radius:11px; padding:12px 13px; background:white; color:var(--text);
}}
textarea {{ min-height:145px; resize:vertical; }}
.actions {{ display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:16px; }}
button,.button-link {{
  border:0; border-radius:10px; padding:10px 14px; font-weight:800; cursor:pointer; text-decoration:none;
}}
.primary {{ background:var(--red); color:white; }}
.primary:hover {{ background:var(--red-dark); }}
.secondary {{ background:#eef1f6; color:var(--navy); }}
.ghost {{ background:white; color:var(--navy); border:1px solid var(--border); }}
button:disabled {{ opacity:.55; cursor:not-allowed; }}
.checkbox {{ display:flex; gap:8px; align-items:center; font-weight:650; }}
.checkbox input {{ width:auto; }}
.progress-wrap {{ display:none; margin-top:18px; }}
.progress-head {{ display:flex; justify-content:space-between; gap:12px; font-size:14px; margin-bottom:8px; }}
.progress {{ height:10px; background:#e7ebf2; border-radius:999px; overflow:hidden; }}
.progress > div {{ height:100%; width:0; background:var(--red); transition:width .2s ease; }}
.summary {{ display:none; margin-top:22px; grid-template-columns:repeat(4,1fr); gap:12px; }}
.summary-item {{ background:white; border:1px solid var(--border); border-radius:14px; padding:15px; }}
.summary-item span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
.summary-item strong {{ display:block; margin-top:3px; font-size:22px; }}
.toolbar {{ display:none; margin-top:18px; gap:10px; flex-wrap:wrap; align-items:center; }}
.toolbar input {{ flex:1 1 260px; }}
.results {{ display:grid; gap:15px; margin-top:18px; }}
.card {{ background:white; border:1px solid var(--border); border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(20,33,61,.06); }}
.card-head {{ display:flex; justify-content:space-between; gap:16px; padding:18px; border-bottom:1px solid #eef1f5; }}
.card-title {{ min-width:0; }}
.eyebrow {{ color:var(--red); text-transform:uppercase; font-weight:850; font-size:11px; letter-spacing:.08em; }}
.card h2 {{ margin:4px 0 5px; font-size:19px; overflow-wrap:anywhere; }}
.sub {{ color:var(--muted); font-size:13px; }}
.badges {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }}
.badge {{ background:#f1f3f7; color:var(--navy); border-radius:999px; padding:5px 8px; font-size:11px; font-weight:800; }}
.card-actions {{ display:flex; flex-wrap:wrap; gap:7px; align-content:flex-start; justify-content:flex-end; }}
.card-actions button,.card-actions a {{ padding:8px 10px; font-size:12px; }}
.content {{ padding:16px 18px; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:480px; overflow:auto; margin:0; background:#f8f9fb; border:1px solid #eceff4; border-radius:10px; padding:14px; line-height:1.5; }}
.error-card {{ border-color:#efb4ae; }}
.error-box {{ color:var(--error); background:#fff4f2; padding:14px; border-radius:10px; }}
.available {{ margin-top:10px; color:var(--muted); font-size:13px; }}
.empty {{ color:var(--muted); text-align:center; padding:28px; border:1px dashed var(--border); border-radius:14px; background:rgba(255,255,255,.7); }}
footer {{ margin-top:24px; color:var(--muted); font-size:12px; text-align:center; }}
@media(max-width:800px) {{
  .grid {{ grid-template-columns:1fr; }}
  .summary {{ grid-template-columns:repeat(2,1fr); }}
  .card-head {{ flex-direction:column; }}
  .card-actions {{ justify-content:flex-start; }}
}}
@media(prefers-reduced-motion:reduce) {{ * {{ transition:none !important; scroll-behavior:auto !important; }} }}
</style>
</head>
<body>
<main class="shell">
  <section class="hero">
    {logo_html}
    <div>
      <h1>YouTube Transcript Collector</h1>
      <p>Collect, search, copy, and download transcripts one video at a time or in a batch.</p>
    </div>
  </section>

  <section class="panel">
    <div class="grid">
      <div class="field wide">
        <label for="urls">YouTube URLs or video IDs</label>
        <textarea id="urls" aria-describedby="urls-help" placeholder="Paste one URL or video ID per line"></textarea>
        <div class="help" id="urls-help">Duplicate videos are removed automatically, even when different YouTube URL formats are used.</div>
      </div>

      <div class="field">
        <label for="languages">Preferred languages</label>
        <input id="languages" value="en" placeholder="en, es">
        <div class="help">Comma-separated language codes in priority order.</div>
      </div>

      <div class="field">
        <label for="format">Output format</label>
        <select id="format">
          <option value="text">Plain text</option>
          <option value="timestamped">Timestamped text</option>
          <option value="json">JSON</option>
          <option value="srt">SRT subtitles</option>
          <option value="vtt">WebVTT subtitles</option>
        </select>
      </div>

      <div class="field">
        <label>Saving</label>
        <label class="checkbox"><input id="save" type="checkbox" checked> Save files to output/</label>
      </div>
    </div>

    <div class="actions">
      <button class="primary" id="start">Get transcripts</button>
      <button class="secondary" id="clear" type="button">Clear</button>
    </div>

    <div class="progress-wrap" id="progressWrap" aria-live="polite">
      <div class="progress-head"><span id="progressText">Ready</span><strong id="progressPct">0%</strong></div>
      <div class="progress" aria-label="Batch progress"><div id="progressBar"></div></div>
    </div>
  </section>

  <section class="summary" id="summary" aria-live="polite">
    <div class="summary-item"><span>Total</span><strong id="sumTotal">0</strong></div>
    <div class="summary-item"><span>Completed</span><strong id="sumSuccess">0</strong></div>
    <div class="summary-item"><span>Failed</span><strong id="sumFailed">0</strong></div>
    <div class="summary-item"><span>Characters</span><strong id="sumChars">0</strong></div>
  </section>

  <section class="toolbar" id="toolbar">
    <input id="search" placeholder="Search all transcript results..." aria-label="Search all transcript results">
    <button class="secondary" id="copyAll" type="button">Copy all</button>
    <button class="secondary" id="downloadAll" type="button">Download combined</button>
    <button class="secondary" id="retryFailed" type="button">Retry failed</button>
  </section>

  <section class="results" id="results">
    <div class="empty">Your transcript results will appear here.</div>
  </section>

  <footer>{DISCLAIMER}</footer>
</main>

<script>
const state = {{ items: [], format: "text", languages: ["en"], save: true }};
const el = id => document.getElementById(id);

function clientVideoId(value) {{
  const trimmed = value.trim();
  if (/^[A-Za-z0-9_-]{{11}}$/.test(trimmed)) return trimmed;
  try {{
    const url = new URL(trimmed);
    const host = url.hostname.toLowerCase();
    if (host === "youtu.be" || host === "www.youtu.be") {{
      const id = url.pathname.split("/").filter(Boolean)[0] || "";
      return /^[A-Za-z0-9_-]{{11}}$/.test(id) ? id : null;
    }}
    if (["youtube.com","www.youtube.com","m.youtube.com","music.youtube.com"].includes(host)) {{
      if (url.pathname === "/watch") {{
        const id = url.searchParams.get("v") || "";
        return /^[A-Za-z0-9_-]{{11}}$/.test(id) ? id : null;
      }}
      const parts = url.pathname.split("/").filter(Boolean);
      if (parts.length >= 2 && ["shorts","embed","live"].includes(parts[0])) {{
        return /^[A-Za-z0-9_-]{{11}}$/.test(parts[1]) ? parts[1] : null;
      }}
    }}
  }} catch (_) {{}}
  return null;
}}

function parseInputs(raw) {{
  const lines = raw.replace(/\\r/g, "\\n").split("\\n").map(v => v.trim()).filter(Boolean);
  const unique = [];
  const seen = new Set();
  for (const value of lines) {{
    if (value.startsWith("#")) continue;
    const key = clientVideoId(value) || value;
    if (!seen.has(key)) {{ seen.add(key); unique.push(value); }}
  }}
  return unique;
}}

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[c]));
}}

function fileExtension(fmt) {{
  return ({{text:"txt",timestamped:"txt",json:"json",srt:"srt",vtt:"vtt"}})[fmt] || "txt";
}}

function downloadText(filename, content) {{
  const blob = new Blob([content], {{type:"text/plain;charset=utf-8"}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}}

function updateSummary() {{
  const success = state.items.filter(i => i.status === "success");
  const failed = state.items.filter(i => i.status === "error");
  el("summary").style.display = state.items.length ? "grid" : "none";
  el("toolbar").style.display = state.items.length ? "flex" : "none";
  el("sumTotal").textContent = state.items.length;
  el("sumSuccess").textContent = success.length;
  el("sumFailed").textContent = failed.length;
  el("sumChars").textContent = success.reduce((n, i) => n + i.content.length, 0).toLocaleString();
  el("retryFailed").disabled = failed.length === 0;
}}

function renderResults() {{
  const query = el("search").value.trim().toLowerCase();
  const container = el("results");
  container.innerHTML = "";

  const visible = state.items.filter(item => {{
    if (!query) return true;
    const haystack = [item.title, item.channel_name, item.video_id, item.content, item.error].join(" ").toLowerCase();
    return haystack.includes(query);
  }});

  if (!visible.length) {{
    container.innerHTML = `<div class="empty">${{state.items.length ? "No results match your search." : "Your transcript results will appear here."}}</div>`;
    return;
  }}

  visible.forEach((item, index) => {{
    const card = document.createElement("article");
    card.className = "card" + (item.status === "error" ? " error-card" : "");
    if (item.status === "success") {{
      const ext = fileExtension(state.format);
      const title = escapeHtml(item.title || item.video_id);
      card.innerHTML = `
        <div class="card-head">
          <div class="card-title">
            <div class="eyebrow">Transcript ${{index + 1}}</div>
            <h2>${{title}}</h2>
            <div class="sub">${{escapeHtml(item.channel_name || "Unknown channel")}} · ${{escapeHtml(item.published_date || "Unknown date")}}</div>
            <div class="badges">
              <span class="badge">${{escapeHtml(item.language)}} (${{escapeHtml(item.language_code)}})</span>
              <span class="badge">${{item.is_generated ? "Auto captions" : "Manual captions"}}</span>
              <span class="badge">${{escapeHtml(state.format.toUpperCase())}}</span>
            </div>
          </div>
          <div class="card-actions">
            <button class="secondary copy-one" type="button">Copy</button>
            <button class="secondary download-one" type="button">Download</button>
            <a class="button-link ghost" target="_blank" rel="noopener" href="${{escapeHtml(item.source_url)}}">Open YouTube</a>
          </div>
        </div>
        <div class="content">
          <pre>${{escapeHtml(item.content)}}</pre>
          <div class="help" style="margin-top:8px">Video ID: ${{escapeHtml(item.video_id)}}${{item.saved_path ? " · Saved: " + escapeHtml(item.saved_path) : ""}}</div>
        </div>`;
      card.querySelector(".copy-one").addEventListener("click", async e => {{
        await navigator.clipboard.writeText(item.content);
        const old = e.currentTarget.textContent; e.currentTarget.textContent = "Copied";
        setTimeout(() => e.currentTarget.textContent = old, 1200);
      }});
      card.querySelector(".download-one").addEventListener("click", () => {{
        downloadText(`${{item.filename}}.${{ext}}`, item.content);
      }});
    }} else {{
      const available = (item.available_languages || []).map(l =>
        `${{escapeHtml(l.language)}} (${{escapeHtml(l.language_code)}})${{l.is_generated ? " — auto" : " — manual"}}`
      ).join("<br>");
      card.innerHTML = `
        <div class="card-head">
          <div class="card-title">
            <div class="eyebrow">Could not process</div>
            <h2>${{escapeHtml(item.input)}}</h2>
          </div>
          <div class="card-actions"><button class="secondary retry-one" type="button">Retry</button></div>
        </div>
        <div class="content">
          <div class="error-box"><strong>${{escapeHtml(item.error_code || "ERROR")}}</strong><br>${{escapeHtml(item.error)}}</div>
          ${{available ? `<div class="available"><strong>Available transcript languages:</strong><br>${{available}}</div>` : ""}}
        </div>`;
      card.querySelector(".retry-one").addEventListener("click", () => retryItem(item));
    }}
    container.appendChild(card);
  }});
}}

async function processInput(input, existingItem=null) {{
  const payload = {{ input, languages: state.languages, format: state.format, save: state.save }};
  const response = await fetch("/api/transcribe", {{
    method: "POST",
    headers: {{"Content-Type":"application/json"}},
    body: JSON.stringify(payload)
  }});
  const data = await response.json();
  const item = response.ok
    ? {{status:"success", input, ...data}}
    : {{status:"error", input, ...data}};

  if (existingItem) {{
    const idx = state.items.indexOf(existingItem);
    if (idx >= 0) state.items[idx] = item;
  }} else {{
    const sameIdIndex = data.video_id ? state.items.findIndex(x => x.video_id === data.video_id) : -1;
    if (sameIdIndex >= 0) state.items[sameIdIndex] = item;
    else state.items.push(item);
  }}
  updateSummary(); renderResults();
  return item;
}}

async function runBatch(inputs) {{
  state.items = [];
  state.format = el("format").value;
  state.languages = el("languages").value.split(",").map(v => v.trim()).filter(Boolean);
  state.save = el("save").checked;
  if (!state.languages.length) state.languages = ["en"];
  updateSummary(); renderResults();

  el("start").disabled = true;
  el("progressWrap").style.display = "block";

  for (let i=0; i<inputs.length; i++) {{
    el("progressText").textContent = `Processing ${{i + 1}} of ${{inputs.length}}`;
    const pct = Math.round((i / inputs.length) * 100);
    el("progressPct").textContent = pct + "%";
    el("progressBar").style.width = pct + "%";
    try {{
      await processInput(inputs[i]);
    }} catch (err) {{
      state.items.push({{status:"error", input:inputs[i], error:"Network or local server error: " + err, error_code:"NETWORK_ERROR"}});
      updateSummary(); renderResults();
    }}
  }}

  el("progressText").textContent = "Batch complete";
  el("progressPct").textContent = "100%";
  el("progressBar").style.width = "100%";
  el("start").disabled = false;
}}

async function retryItem(item) {{
  try {{
    await processInput(item.input, item);
  }} catch (err) {{
    item.error = "Network or local server error: " + err;
    updateSummary(); renderResults();
  }}
}}

el("start").addEventListener("click", () => {{
  const inputs = parseInputs(el("urls").value);
  if (!inputs.length) {{
    alert("Paste at least one YouTube URL or video ID.");
    return;
  }}
  runBatch(inputs);
}});

el("clear").addEventListener("click", () => {{
  el("urls").value = "";
  el("search").value = "";
  state.items = [];
  el("progressWrap").style.display = "none";
  updateSummary(); renderResults();
}});

el("search").addEventListener("input", renderResults);

el("copyAll").addEventListener("click", async () => {{
  const success = state.items.filter(i => i.status === "success");
  const combined = success.map(i =>
`==================================================
TITLE: ${{i.title || i.video_id}}
CHANNEL: ${{i.channel_name || "Unknown"}}
URL: ${{i.source_url}}
==================================================

${{i.content}}`).join("\\n\\n");
  await navigator.clipboard.writeText(combined);
  el("copyAll").textContent = "Copied all";
  setTimeout(() => el("copyAll").textContent = "Copy all", 1200);
}});

el("downloadAll").addEventListener("click", () => {{
  const success = state.items.filter(i => i.status === "success");
  const combined = success.map(i =>
`==================================================
TITLE: ${{i.title || i.video_id}}
CHANNEL: ${{i.channel_name || "Unknown"}}
URL: ${{i.source_url}}
==================================================

${{i.content}}`).join("\\n\\n");
  downloadText("youtube-transcripts-combined.txt", combined);
}});

el("retryFailed").addEventListener("click", async () => {{
  const failed = state.items.filter(i => i.status === "error");
  for (const item of failed) await retryItem(item);
}});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "YouTubeTranscriptCollector/1.3"

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, payload: dict) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, content, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, render_page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/health":
            self._json(200, {"ok": True, "version": "1.3"})
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/transcribe":
            self._json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                self._json(400, {"error": "Invalid request body."})
                return

            body = json.loads(self.rfile.read(length).decode("utf-8"))
            raw_input = str(body.get("input", "")).strip()
            fmt = str(body.get("format", "text")).strip()
            languages = body.get("languages") or ["en"]
            should_save = bool(body.get("save", True))

            if not isinstance(languages, list):
                languages = ["en"]
            languages = [str(item).strip() for item in languages if str(item).strip()]
            if not languages:
                languages = ["en"]

            video_id = extract_video_id(raw_input)
            result = get_transcript_for_url(video_id, languages=languages)
            content = render_transcript(result, fmt)
            filename = choose_best_filename(result)
            saved_path = None

            if should_save:
                saved = save_output(OUTPUT_DIR, filename, content, fmt)
                saved_path = str(saved)

            self._json(
                200,
                {
                    "video_id": result["video_id"],
                    "title": result.get("title"),
                    "channel_name": result.get("channel_name"),
                    "published_date": result.get("published_date"),
                    "source_url": result.get("source_url"),
                    "language": result["language"],
                    "language_code": result["language_code"],
                    "is_generated": result["is_generated"],
                    "content": content,
                    "filename": filename,
                    "extension": extension_for_format(fmt),
                    "saved_path": saved_path,
                },
            )
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON request.", "error_code": "INVALID_REQUEST"})
        except ValueError as exc:
            self._json(400, {"error": str(exc), "error_code": "INVALID_INPUT"})
        except TranscriptionError as exc:
            self._json(
                422,
                {
                    "error": str(exc),
                    "error_code": exc.code,
                    "available_languages": exc.available_languages,
                },
            )
        except Exception as exc:
            logger.exception("Unhandled request error")
            self._json(
                500,
                {
                    "error": f"Unexpected local server error: {exc}",
                    "error_code": "SERVER_ERROR",
                },
            )

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("YouTube Transcript Collector v1.3")
    print(f"Open http://{HOST}:{PORT} in your browser.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
