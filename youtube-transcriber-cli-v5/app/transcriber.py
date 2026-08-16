from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._ -]+")
UPLOAD_DATE_PATTERN = re.compile(r'"uploadDate":"(\d{4}-\d{2}-\d{2})"')
TITLE_PATTERN = re.compile(r'"title":"([^"]+)"')
CHANNEL_PATTERN = re.compile(r'"ownerChannelName":"([^"]+)"')
REQUEST_TIMEOUT = 12

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


class TranscriptionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "UNKNOWN_ERROR",
        available_languages: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.available_languages = available_languages or []


@dataclass(frozen=True)
class Segment:
    text: str
    start: float
    duration: float


@dataclass(frozen=True)
class VideoInput:
    original: str
    video_id: str


def extract_video_id(url_or_id: str) -> str:
    candidate = url_or_id.strip()
    if VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    path = parsed.path

    if host in SHORT_HOSTS:
        video_id = path.strip("/").split("/")[0]
        if VIDEO_ID_PATTERN.fullmatch(video_id):
            return video_id

    if host in YOUTUBE_HOSTS:
        if path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if VIDEO_ID_PATTERN.fullmatch(video_id):
                return video_id

        path_parts = [part for part in path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            video_id = path_parts[1]
            if VIDEO_ID_PATTERN.fullmatch(video_id):
                return video_id

    raise ValueError(f"Invalid YouTube URL or video ID: {url_or_id}")


def normalize_inputs(values: Iterable[str]) -> list[VideoInput]:
    normalized: list[VideoInput] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        video_id = extract_video_id(cleaned)
        if video_id in seen:
            continue
        seen.add(video_id)
        normalized.append(VideoInput(original=cleaned, video_id=video_id))

    return normalized


def sanitize_filename(value: str, fallback: str) -> str:
    cleaned = SAFE_FILENAME_PATTERN.sub("", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    return cleaned[:120] or fallback


def choose_best_filename(result: dict[str, Any]) -> str:
    parts = [
        sanitize_filename(result.get("published_date") or "", ""),
        sanitize_filename(result.get("channel_name") or "", ""),
        sanitize_filename(result.get("title") or "", ""),
        result["video_id"],
    ]
    filtered = [part for part in parts if part]
    return " - ".join(filtered)[:220]


def decode_json_escaped(value: str) -> str:
    return json.loads('"' + value + '"') if value else value


def extract_metadata_from_html(page_html: str) -> dict[str, str | None]:
    published_date = None
    title = None
    channel_name = None

    if date_match := UPLOAD_DATE_PATTERN.search(page_html):
        published_date = date_match.group(1)
    if title_match := TITLE_PATTERN.search(page_html):
        title = decode_json_escaped(title_match.group(1))
    if channel_match := CHANNEL_PATTERN.search(page_html):
        channel_name = decode_json_escaped(channel_match.group(1))

    return {
        "title": title,
        "channel_name": channel_name,
        "published_date": published_date,
    }


def fetch_video_metadata(video_id: str) -> dict[str, str | None]:
    source_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        )
    }
    metadata: dict[str, str | None] = {
        "title": None,
        "channel_name": None,
        "published_date": None,
        "source_url": source_url,
    }

    try:
        oembed_url = (
            "https://www.youtube.com/oembed?url="
            f"{quote_plus(source_url)}&format=json"
        )
        response = requests.get(oembed_url, timeout=REQUEST_TIMEOUT, headers=headers)
        if response.ok:
            payload = response.json()
            metadata["title"] = payload.get("title") or metadata["title"]
            metadata["channel_name"] = (
                payload.get("author_name") or metadata["channel_name"]
            )
    except requests.RequestException:
        logger.debug("YouTube oEmbed metadata request failed", exc_info=True)
    except ValueError:
        logger.debug("YouTube oEmbed returned invalid JSON", exc_info=True)

    try:
        response = requests.get(source_url, timeout=REQUEST_TIMEOUT, headers=headers)
        if response.ok:
            extracted = extract_metadata_from_html(response.text)
            metadata["title"] = extracted.get("title") or metadata["title"]
            metadata["channel_name"] = (
                extracted.get("channel_name") or metadata["channel_name"]
            )
            metadata["published_date"] = (
                extracted.get("published_date") or metadata["published_date"]
            )
    except requests.RequestException:
        logger.debug("YouTube HTML metadata request failed", exc_info=True)

    return metadata


def list_available_transcripts(video_id: str) -> list[dict[str, Any]]:
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except Exception:
        logger.debug("Could not list transcript tracks", exc_info=True)
        return []

    items: list[dict[str, Any]] = []
    for transcript in transcript_list:
        items.append(
            {
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable,
            }
        )
    return items


def get_transcript_for_url(
    url: str,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    video_id = extract_video_id(url)
    preferred = [item.strip() for item in (languages or ["en"]) if item.strip()]
    if not preferred:
        preferred = ["en"]

    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=preferred)
    except NoTranscriptFound as exc:
        available = list_available_transcripts(video_id)
        requested = ", ".join(preferred)
        raise TranscriptionError(
            f"No transcript found for video {video_id} in requested language(s): {requested}.",
            code="LANGUAGE_NOT_FOUND",
            available_languages=available,
        ) from exc
    except TranscriptsDisabled as exc:
        raise TranscriptionError(
            f"Transcripts are disabled for video {video_id}.",
            code="TRANSCRIPTS_DISABLED",
        ) from exc
    except VideoUnavailable as exc:
        raise TranscriptionError(
            f"Video {video_id} is unavailable.",
            code="VIDEO_UNAVAILABLE",
        ) from exc
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptionError(
            f"Could not retrieve transcript for video {video_id}.",
            code="REQUEST_BLOCKED_OR_UNAVAILABLE",
        ) from exc
    except Exception as exc:
        raise TranscriptionError(
            f"Unexpected transcript error for video {video_id}: {exc}",
            code="UNKNOWN_ERROR",
        ) from exc

    metadata = fetch_video_metadata(video_id)
    segments = [
        Segment(text=snippet.text, start=snippet.start, duration=snippet.duration)
        for snippet in fetched
    ]
    return {
        "video_id": fetched.video_id,
        "title": metadata.get("title") or fetched.video_id,
        "channel_name": metadata.get("channel_name"),
        "published_date": metadata.get("published_date"),
        "source_url": metadata.get("source_url"),
        "language": fetched.language,
        "language_code": fetched.language_code,
        "is_generated": fetched.is_generated,
        "segments": segments,
    }


def transcript_to_text(segments: list[Segment]) -> str:
    return "\n".join(
        segment.text.strip() for segment in segments if segment.text.strip()
    )


def _format_clock(seconds: float, *, milliseconds: bool = False, srt: bool = False) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if milliseconds:
        sep = "," if srt else "."
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def transcript_to_timestamped_text(segments: list[Segment]) -> str:
    lines = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            lines.append(f"[{_format_clock(segment.start)}] {text}")
    return "\n".join(lines)


def transcript_to_srt(segments: list[Segment]) -> str:
    blocks = []
    cue_number = 1
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        start = _format_clock(segment.start, milliseconds=True, srt=True)
        end = _format_clock(
            segment.start + max(segment.duration, 0.001),
            milliseconds=True,
            srt=True,
        )
        blocks.append(f"{cue_number}\n{start} --> {end}\n{text}")
        cue_number += 1
    return "\n\n".join(blocks)


def transcript_to_vtt(segments: list[Segment]) -> str:
    blocks = ["WEBVTT"]
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        start = _format_clock(segment.start, milliseconds=True)
        end = _format_clock(
            segment.start + max(segment.duration, 0.001),
            milliseconds=True,
        )
        blocks.append(f"{start} --> {end}\n{text}")
    return "\n\n".join(blocks)


def transcript_to_json(result: dict[str, Any]) -> str:
    payload = {
        "video_id": result["video_id"],
        "title": result.get("title"),
        "channel_name": result.get("channel_name"),
        "published_date": result.get("published_date"),
        "source_url": result.get("source_url"),
        "language": result["language"],
        "language_code": result["language_code"],
        "is_generated": result["is_generated"],
        "segments": [asdict(segment) for segment in result["segments"]],
        "text": transcript_to_text(result["segments"]),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_transcript(result: dict[str, Any], fmt: str) -> str:
    if fmt == "text":
        return transcript_to_text(result["segments"])
    if fmt == "timestamped":
        return transcript_to_timestamped_text(result["segments"])
    if fmt == "json":
        return transcript_to_json(result)
    if fmt == "srt":
        return transcript_to_srt(result["segments"])
    if fmt == "vtt":
        return transcript_to_vtt(result["segments"])
    raise ValueError(f"Unsupported output format: {fmt}")
