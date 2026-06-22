
import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._ -]+")
UPLOAD_DATE_PATTERN = re.compile(r'"uploadDate":"(\d{4}-\d{2}-\d{2})"')
TITLE_PATTERN = re.compile(r'"title":"([^"]+)"')
CHANNEL_PATTERN = re.compile(r'"ownerChannelName":"([^"]+)"')
REQUEST_TIMEOUT = 12


class TranscriptionError(Exception):
    pass


@dataclass
class Segment:
    text: str
    start: float
    duration: float


def extract_video_id(url_or_id: str) -> str:
    candidate = url_or_id.strip()
    if VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    path = parsed.path

    if "youtu.be" in host:
        video_id = path.strip("/").split("/")[0]
        if VIDEO_ID_PATTERN.fullmatch(video_id):
            return video_id

    if "youtube.com" in host or "m.youtube.com" in host:
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


def sanitize_filename(value: str, fallback: str) -> str:
    cleaned = value.strip()
    cleaned = SAFE_FILENAME_PATTERN.sub("", cleaned)
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
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except Exception:
        return value


def extract_metadata_from_html(page_html: str) -> dict[str, str | None]:
    published_date = None
    title = None
    channel_name = None

    date_match = UPLOAD_DATE_PATTERN.search(page_html)
    if date_match:
        published_date = date_match.group(1)

    title_match = TITLE_PATTERN.search(page_html)
    if title_match:
        title = decode_json_escaped(title_match.group(1))

    channel_match = CHANNEL_PATTERN.search(page_html)
    if channel_match:
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
            metadata["channel_name"] = payload.get("author_name") or metadata["channel_name"]
    except Exception:
        pass

    try:
        response = requests.get(source_url, timeout=REQUEST_TIMEOUT, headers=headers)
        if response.ok:
            page_html = response.text
            extracted = extract_metadata_from_html(page_html)
            metadata["title"] = extracted.get("title") or metadata["title"]
            metadata["channel_name"] = extracted.get("channel_name") or metadata["channel_name"]
            metadata["published_date"] = extracted.get("published_date") or metadata["published_date"]
    except Exception:
        pass

    return metadata


def get_transcript_for_url(url: str, language: str = "en") -> dict[str, Any]:
    video_id = extract_video_id(url)
    api = YouTubeTranscriptApi()

    try:
        fetched = api.fetch(video_id, languages=[language])
    except NoTranscriptFound as exc:
        raise TranscriptionError(
            f"No transcript found for video {video_id} in language '{language}'."
        ) from exc
    except TranscriptsDisabled as exc:
        raise TranscriptionError(f"Transcripts are disabled for video {video_id}.") from exc
    except VideoUnavailable as exc:
        raise TranscriptionError(f"Video {video_id} is unavailable.") from exc
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptionError(
            f"Could not retrieve transcript for video {video_id}."
        ) from exc
    except Exception as exc:
        raise TranscriptionError(
            f"Unexpected transcript error for video {video_id}: {exc}"
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
    cleaned = [segment.text.strip() for segment in segments if segment.text.strip()]
    return "\n".join(cleaned)


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
