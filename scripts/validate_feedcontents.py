#!/usr/bin/env python3
"""Validate public/scroll/v1/feedcontents.json.

Structural rules (keys, types, patterns, lengths, enums) live in
schema/feedcontents-v1.schema.json and are enforced here via jsonschema,
so the schema file is the single source of truth. This script adds only
the checks a JSON Schema cannot express: filesystem lookups (image
existence, size, orphans), cross-card rules (duplicate ids and image
paths, publishedAt ordering), and cross-field rules (updatedAt >=
publishedAt, stripped whitespace, UTC "Z" timestamps).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
FEED_DIR = REPO_ROOT / "public/scroll/v1"
FEED_PATH = FEED_DIR / "feedcontents.json"
IMAGES_DIR = FEED_DIR / "images"
SCHEMA_PATH = REPO_ROOT / "schema/feedcontents-v1.schema.json"
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 1024 * 1024


class FeedValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FeedValidationError(message)


def parse_utc_timestamp(value: str, field: str, card_id: str) -> datetime:
    require(value.endswith("Z"), f"{card_id}.{field} must use UTC and end with Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise FeedValidationError(f"{card_id}.{field} is not a valid RFC 3339 timestamp") from error
    return parsed.astimezone(timezone.utc)


def validate_schema(document: Any) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(f"{'/'.join(str(p) for p in error.absolute_path) or '(root)'}: {error.message}" for error in errors)
        raise FeedValidationError(f"schema violation — {details}")


def validate_image(image_path: str, card_id: str) -> None:
    # Image URLs are cached by clients: replacements must use a new file
    # name (see README), which orphan detection below indirectly enforces.
    file_path = FEED_DIR / image_path
    require(file_path.is_file(), f"{card_id}.imagePath does not exist: {image_path}")
    size = file_path.stat().st_size
    require(size <= MAX_IMAGE_BYTES, f"{card_id}.imagePath exceeds {MAX_IMAGE_BYTES} bytes ({size} bytes)")


def validate_card(card: dict[str, Any]) -> tuple[str, datetime, str | None]:
    card_id = card["id"]

    for field in ("title", "excerpt", "body"):
        require(card[field] == card[field].strip(), f"{card_id}.{field} must not have leading or trailing whitespace")

    image_path: str | None = card.get("imagePath")
    if image_path is not None:
        validate_image(image_path, card_id)

    published_at = parse_utc_timestamp(card["publishedAt"], "publishedAt", card_id)

    if "updatedAt" in card:
        updated_at = parse_utc_timestamp(card["updatedAt"], "updatedAt", card_id)
        require(updated_at >= published_at, f"{card_id}.updatedAt must not be earlier than publishedAt")

    return card_id, published_at, image_path


def validate_feed(raw: bytes) -> None:
    require(len(raw) <= MAX_FILE_BYTES, f"feed exceeds {MAX_FILE_BYTES} bytes")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FeedValidationError("feed must be valid UTF-8 JSON") from error

    validate_schema(document)

    ids: set[str] = set()
    published_dates: list[datetime] = []
    referenced_images: set[str] = set()
    for card in document["cards"]:
        card_id, published_at, image_path = validate_card(card)
        require(card_id not in ids, f"duplicate id: {card_id}")
        ids.add(card_id)
        published_dates.append(published_at)
        if image_path is not None:
            require(image_path not in referenced_images, f"duplicate imagePath: {image_path}")
            referenced_images.add(image_path)

    require(published_dates == sorted(published_dates, reverse=True), "cards must be sorted by publishedAt descending")

    if IMAGES_DIR.is_dir():
        on_disk = {f"images/{path.name}" for path in IMAGES_DIR.iterdir() if path.is_file() and not path.name.startswith(".")}
        orphans = on_disk - referenced_images
        require(not orphans, f"orphaned images not referenced by any card: {sorted(orphans)}")


def main() -> int:
    try:
        validate_feed(FEED_PATH.read_bytes())
    except (OSError, FeedValidationError) as error:
        print(f"scroll feed validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {FEED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
