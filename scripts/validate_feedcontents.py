#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FEED_DIR = Path(__file__).resolve().parents[1] / "public/scroll/v1"
FEED_PATH = FEED_DIR / "feedcontents.json"
IMAGES_DIR = FEED_DIR / "images"
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 1024 * 1024
MAX_CARDS = 200
MAX_TITLE_LENGTH = 80
MAX_EXCERPT_LENGTH = 200
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
IMAGE_PATH_PATTERN = re.compile(r"^images/[a-z0-9][a-z0-9._-]*\.(png|jpg|jpeg|webp)$")
GENRES = {"article", "paper", "novel"}
TOP_LEVEL_KEYS = {"schemaVersion", "cards"}
REQUIRED_CARD_KEYS = {
    "id",
    "revision",
    "genre",
    "title",
    "excerpt",
    "body",
    "publishedAt",
}
OPTIONAL_CARD_KEYS = {"imagePath", "updatedAt"}


class ValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def parse_utc_timestamp(value: Any, field: str, card_id: str) -> datetime:
    require(isinstance(value, str), f"{card_id}.{field} must be a string")
    require(value.endswith("Z"), f"{card_id}.{field} must use UTC and end with Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValidationError(f"{card_id}.{field} is not a valid RFC 3339 timestamp") from error
    require(parsed.tzinfo is not None, f"{card_id}.{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_image(image_path: str, card_id: str) -> None:
    require(IMAGE_PATH_PATTERN.fullmatch(image_path) is not None, f"{card_id}.imagePath is invalid")
    file_path = FEED_DIR / image_path
    require(file_path.is_file(), f"{card_id}.imagePath does not exist: {image_path}")
    size = file_path.stat().st_size
    require(size <= MAX_IMAGE_BYTES, f"{card_id}.imagePath exceeds {MAX_IMAGE_BYTES} bytes ({size} bytes)")


def validate_card(card: Any, index: int) -> tuple[str, datetime, str | None]:
    require(isinstance(card, dict), f"cards[{index}] must be an object")
    keys = set(card)
    require(REQUIRED_CARD_KEYS <= keys, f"cards[{index}] is missing {sorted(REQUIRED_CARD_KEYS - keys)}")
    require(keys <= REQUIRED_CARD_KEYS | OPTIONAL_CARD_KEYS, f"cards[{index}] has unknown keys {sorted(keys - REQUIRED_CARD_KEYS - OPTIONAL_CARD_KEYS)}")

    card_id = card["id"]
    require(isinstance(card_id, str) and ID_PATTERN.fullmatch(card_id) is not None, f"cards[{index}].id is invalid")

    revision = card["revision"]
    require(type(revision) is int and revision >= 1, f"{card_id}.revision must be an integer greater than zero")

    require(card["genre"] in GENRES, f"{card_id}.genre must be one of {sorted(GENRES)}")

    title = card["title"]
    require(isinstance(title, str) and 1 <= len(title) <= MAX_TITLE_LENGTH, f"{card_id}.title must contain 1-{MAX_TITLE_LENGTH} characters")
    require(title == title.strip(), f"{card_id}.title must not have leading or trailing whitespace")

    excerpt = card["excerpt"]
    require(isinstance(excerpt, str) and 1 <= len(excerpt) <= MAX_EXCERPT_LENGTH, f"{card_id}.excerpt must contain 1-{MAX_EXCERPT_LENGTH} characters")
    require(excerpt == excerpt.strip(), f"{card_id}.excerpt must not have leading or trailing whitespace")

    body = card["body"]
    require(isinstance(body, str) and len(body) >= 1, f"{card_id}.body must not be empty")
    require(body == body.strip(), f"{card_id}.body must not have leading or trailing whitespace")

    image_path: str | None = None
    if "imagePath" in card:
        image_path = card["imagePath"]
        require(isinstance(image_path, str), f"{card_id}.imagePath must be a string")
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
        raise ValidationError("feed must be valid UTF-8 JSON") from error

    require(isinstance(document, dict), "feed root must be an object")
    require(set(document) == TOP_LEVEL_KEYS, f"feed root keys must be exactly {sorted(TOP_LEVEL_KEYS)}")
    require(document["schemaVersion"] == 1 and type(document["schemaVersion"]) is int, "schemaVersion must be 1")

    cards = document["cards"]
    require(isinstance(cards, list), "cards must be an array")
    require(len(cards) <= MAX_CARDS, f"cards must contain at most {MAX_CARDS} entries")

    ids: set[str] = set()
    published_dates: list[datetime] = []
    referenced_images: set[str] = set()
    for index, card in enumerate(cards):
        card_id, published_at, image_path = validate_card(card, index)
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
    except (OSError, ValidationError) as error:
        print(f"scroll feed validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {FEED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
