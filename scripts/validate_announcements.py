#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FEED_PATH = Path(__file__).resolve().parents[1] / "public/8key/v1/announcements.json"
MAX_FILE_BYTES = 128 * 1024
MAX_ITEMS = 50
MAX_TITLE_LENGTH = 80
MAX_BODY_LENGTH = 4000
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
TOP_LEVEL_KEYS = {"schemaVersion", "items"}
REQUIRED_ITEM_KEYS = {
    "id",
    "revision",
    "title",
    "body",
    "publishedAt",
    "startsAt",
    "endsAt",
}
OPTIONAL_ITEM_KEYS = {"updatedAt"}


class ValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def parse_utc_timestamp(value: Any, field: str, item_id: str) -> datetime:
    require(isinstance(value, str), f"{item_id}.{field} must be a string")
    require(value.endswith("Z"), f"{item_id}.{field} must use UTC and end with Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValidationError(f"{item_id}.{field} is not a valid RFC 3339 timestamp") from error
    require(parsed.tzinfo is not None, f"{item_id}.{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_item(item: Any, index: int) -> tuple[str, datetime]:
    require(isinstance(item, dict), f"items[{index}] must be an object")
    keys = set(item)
    require(REQUIRED_ITEM_KEYS <= keys, f"items[{index}] is missing {sorted(REQUIRED_ITEM_KEYS - keys)}")
    require(keys <= REQUIRED_ITEM_KEYS | OPTIONAL_ITEM_KEYS, f"items[{index}] has unknown keys {sorted(keys - REQUIRED_ITEM_KEYS - OPTIONAL_ITEM_KEYS)}")

    item_id = item["id"]
    require(isinstance(item_id, str) and ID_PATTERN.fullmatch(item_id) is not None, f"items[{index}].id is invalid")

    revision = item["revision"]
    require(type(revision) is int and revision >= 1, f"{item_id}.revision must be an integer greater than zero")

    title = item["title"]
    require(isinstance(title, str) and 1 <= len(title) <= MAX_TITLE_LENGTH, f"{item_id}.title must contain 1-{MAX_TITLE_LENGTH} characters")
    require(title == title.strip(), f"{item_id}.title must not have leading or trailing whitespace")

    body = item["body"]
    require(isinstance(body, str) and 1 <= len(body) <= MAX_BODY_LENGTH, f"{item_id}.body must contain 1-{MAX_BODY_LENGTH} characters")
    require(body == body.strip(), f"{item_id}.body must not have leading or trailing whitespace")

    published_at = parse_utc_timestamp(item["publishedAt"], "publishedAt", item_id)
    starts_at = parse_utc_timestamp(item["startsAt"], "startsAt", item_id)
    ends_at = parse_utc_timestamp(item["endsAt"], "endsAt", item_id)
    require(starts_at < ends_at, f"{item_id}.startsAt must be earlier than endsAt")

    if "updatedAt" in item:
        updated_at = parse_utc_timestamp(item["updatedAt"], "updatedAt", item_id)
        require(updated_at >= published_at, f"{item_id}.updatedAt must not be earlier than publishedAt")

    return item_id, published_at


def validate_feed(raw: bytes) -> None:
    require(len(raw) <= MAX_FILE_BYTES, f"feed exceeds {MAX_FILE_BYTES} bytes")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("feed must be valid UTF-8 JSON") from error

    require(isinstance(document, dict), "feed root must be an object")
    require(set(document) == TOP_LEVEL_KEYS, f"feed root keys must be exactly {sorted(TOP_LEVEL_KEYS)}")
    require(document["schemaVersion"] == 1 and type(document["schemaVersion"]) is int, "schemaVersion must be 1")

    items = document["items"]
    require(isinstance(items, list), "items must be an array")
    require(len(items) <= MAX_ITEMS, f"items must contain at most {MAX_ITEMS} entries")

    ids: set[str] = set()
    published_dates: list[datetime] = []
    for index, item in enumerate(items):
        item_id, published_at = validate_item(item, index)
        require(item_id not in ids, f"duplicate id: {item_id}")
        ids.add(item_id)
        published_dates.append(published_at)

    require(published_dates == sorted(published_dates, reverse=True), "items must be sorted by publishedAt descending")


def main() -> int:
    try:
        validate_feed(FEED_PATH.read_bytes())
    except (OSError, ValidationError) as error:
        print(f"announcement feed validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {FEED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
