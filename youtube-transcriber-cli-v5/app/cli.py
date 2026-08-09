from __future__ import annotations

import argparse
from pathlib import Path

from app.output import save_output
from app.transcriber import (
    TranscriptionError,
    choose_best_filename,
    get_transcript_for_url,
    normalize_inputs,
    render_transcript,
)

DISCLAIMER = (
    "NOTE: For personal research, archival, accessibility, and licensed-use workflows "
    "only. Users are responsible for platform and publisher terms. Do not redistribute "
    "copyrighted content."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch transcripts from one or more YouTube videos.",
        epilog=DISCLAIMER,
    )
    parser.add_argument("urls", nargs="*", help="One or more YouTube URLs or video IDs.")
    parser.add_argument(
        "--input-file",
        help="Text file containing one YouTube URL or video ID per line.",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en"],
        help="Preferred language codes in priority order. Default: en",
    )
    parser.add_argument(
        "--language",
        dest="legacy_language",
        help="Backward-compatible single-language option.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "timestamped", "json", "srt", "vtt"],
        default="text",
        help="Output format. Default: text",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save transcript files automatically.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Folder used for saved transcripts. Default: output",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not overwrite an existing transcript file.",
    )
    return parser


def read_urls_from_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return file_path.read_text(encoding="utf-8").splitlines()


def collect_inputs(cli_urls: list[str], input_file: str | None):
    values = list(cli_urls)
    if input_file:
        values.extend(read_urls_from_file(input_file))
    return normalize_inputs(values)


def print_metadata(result: dict, saved_path: Path | None) -> None:
    title = result.get("title") or result["video_id"]
    print(f"Title: {title}")
    if result.get("channel_name"):
        print(f"Channel: {result['channel_name']}")
    if result.get("published_date"):
        print(f"Published: {result['published_date']}")
    print(f"Video ID: {result['video_id']}")
    print(f"Language: {result['language']} ({result['language_code']})")
    print(f"Captions: {'Auto-generated' if result['is_generated'] else 'Manual'}")
    if saved_path is not None:
        print(f"Saved: {saved_path}")
    print("-" * 72)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        inputs = collect_inputs(args.urls, args.input_file)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    if not inputs:
        parser.error("Provide at least one YouTube URL/video ID or use --input-file.")

    languages = [args.legacy_language] if args.legacy_language else args.languages
    should_save = not args.no_save
    exit_code = 0

    print(DISCLAIMER)
    print()

    for index, video_input in enumerate(inputs, start=1):
        print(f"[{index}/{len(inputs)}] {video_input.original}")
        try:
            result = get_transcript_for_url(
                url=video_input.video_id,
                languages=languages,
            )
            rendered = render_transcript(result, args.format)
            saved_path = None

            if should_save:
                saved_path = save_output(
                    args.output_dir,
                    choose_best_filename(result),
                    rendered,
                    args.format,
                    overwrite=not args.skip_existing,
                )

            print_metadata(result, saved_path)
            print(rendered)
            print()
        except (TranscriptionError, ValueError) as exc:
            exit_code = 1
            print(f"ERROR: {exc}")
            if isinstance(exc, TranscriptionError) and exc.available_languages:
                available = ", ".join(
                    f"{item['language']} ({item['language_code']})"
                    for item in exc.available_languages
                )
                print(f"Available transcript languages: {available}")
            print()

    return exit_code
