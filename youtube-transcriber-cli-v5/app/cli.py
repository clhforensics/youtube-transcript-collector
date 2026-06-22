
import argparse
from pathlib import Path

from app.transcriber import (
    TranscriptionError,
    choose_best_filename,
    get_transcript_for_url,
    transcript_to_json,
    transcript_to_text,
)

DISCLAIMER = (
    "NOTE: For personal research, archival, accessibility, and licensed-use workflows "
    "only. Users are responsible for platform and publisher terms. Do not redistribute "
    "copyrighted content."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch transcript text from one or more YouTube URLs.",
        epilog=DISCLAIMER,
    )
    parser.add_argument("urls", nargs="*", help="One or more YouTube video URLs.")
    parser.add_argument("--input-file", help="Path to a text file containing one YouTube URL per line.")
    parser.add_argument("--language", default="en", help="Preferred transcript language code. Default: en")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format. Default: text")
    parser.add_argument("--no-save", action="store_true", help="Do not save transcript files automatically.")
    parser.add_argument("--output-dir", default="output", help="Folder used for saved transcripts. Default: output")
    return parser


def read_urls_from_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def collect_urls(cli_urls: list[str], input_file: str | None) -> list[str]:
    urls = list(cli_urls)
    if input_file:
        urls.extend(read_urls_from_file(input_file))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def save_output(output_dir: str, base_name: str, content: str, fmt: str) -> Path:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    extension = "json" if fmt == "json" else "txt"
    target = folder / f"{base_name}.{extension}"
    target.write_text(content, encoding="utf-8")
    return target


def print_metadata(result: dict, saved_path: Path | None) -> None:
    title = result.get("title") or result["video_id"]
    print(f"Title: {title}")
    if result.get("channel_name"):
        print(f"Channel: {result['channel_name']}")
    if result.get("published_date"):
        print(f"Published: {result['published_date']}")
    print(f"Video ID: {result['video_id']}")
    if saved_path is not None:
        print(f"Saved: {saved_path}")
    print("-" * 72)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    urls = collect_urls(args.urls, args.input_file)
    if not urls:
        parser.error("Provide at least one YouTube URL or use --input-file.")

    exit_code = 0
    should_save = not args.no_save

    print(DISCLAIMER)
    print()

    for index, url in enumerate(urls, start=1):
        if len(urls) > 1:
            print(f"[{index}/{len(urls)}] {url}")

        try:
            result = get_transcript_for_url(url=url, language=args.language)
            rendered = transcript_to_json(result) if args.format == "json" else transcript_to_text(result["segments"])

            saved_path = None
            if should_save:
                base_name = choose_best_filename(result)
                saved_path = save_output(args.output_dir, base_name, rendered, args.format)

            print_metadata(result, saved_path)
            print(rendered)
            print()

        except (TranscriptionError, FileNotFoundError, ValueError) as exc:
            exit_code = 1
            print(f"ERROR: {exc}\n")

    return exit_code
