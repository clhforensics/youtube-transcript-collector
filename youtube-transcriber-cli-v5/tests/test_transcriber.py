import pytest

from app.transcriber import (
    Segment,
    decode_json_escaped,
    extract_video_id,
    normalize_inputs,
    sanitize_filename,
    transcript_to_srt,
    transcript_to_timestamped_text,
    transcript_to_vtt,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://youtu.be/GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://www.youtube.com/watch?v=GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://m.youtube.com/watch?v=GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://www.youtube.com/shorts/GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://www.youtube.com/embed/GAxk62-9yYc", "GAxk62-9yYc"),
        ("https://www.youtube.com/live/GAxk62-9yYc", "GAxk62-9yYc"),
    ],
)
def test_extract_video_id(value, expected):
    assert extract_video_id(value) == expected


def test_rejects_lookalike_domain():
    with pytest.raises(ValueError):
        extract_video_id("https://youtube.com.example.org/watch?v=GAxk62-9yYc")


def test_normalize_inputs_deduplicates_by_video_id():
    values = [
        "https://youtu.be/GAxk62-9yYc",
        "https://www.youtube.com/watch?v=GAxk62-9yYc",
        "GAxk62-9yYc",
    ]
    normalized = normalize_inputs(values)
    assert len(normalized) == 1
    assert normalized[0].video_id == "GAxk62-9yYc"


def test_sanitize_filename():
    assert sanitize_filename('Bad:/Name*?', "fallback") == "BadName"


def test_timestamped_text():
    segments = [Segment("Hello", 2.4, 1.0)]
    assert transcript_to_timestamped_text(segments) == "[00:00:02] Hello"


def test_srt_and_vtt():
    segments = [Segment("Hello", 1.25, 2.5)]
    srt = transcript_to_srt(segments)
    vtt = transcript_to_vtt(segments)
    assert "00:00:01,250 --> 00:00:03,750" in srt
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.250 --> 00:00:03.750" in vtt


def test_decode_json_escaped_non_ascii():
    assert decode_json_escaped("caf\\u00e9") == "café"
