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

    template_path = Path(__file__).resolve().parent.parent / "templates" / "index.html"
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("LOGO_HTML_HERE", logo_html)
    html = html.replace("DISCLAIMER_HERE", DISCLAIMER)
    return html


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
