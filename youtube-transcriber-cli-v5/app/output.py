from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXTENSIONS = {
    "text": "txt",
    "timestamped": "txt",
    "json": "json",
    "srt": "srt",
    "vtt": "vtt",
}


def extension_for_format(fmt: str) -> str:
    try:
        return EXTENSIONS[fmt]
    except KeyError as exc:
        raise ValueError(f"Unsupported output format: {fmt}") from exc


def save_output(
    output_dir: str | Path,
    base_name: str,
    content: str,
    fmt: str,
    *,
    overwrite: bool = True,
) -> Path:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    extension = extension_for_format(fmt)
    target = folder / f"{base_name}.{extension}"

    if not overwrite and target.exists():
        return target

    target.write_text(content, encoding="utf-8")
    return target


def save_manifest(
    output_dir: str | Path,
    items: list[dict[str, Any]],
    *,
    filename: str = "batch-manifest.json",
) -> Path:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    target.write_text(
        json.dumps({"videos": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
