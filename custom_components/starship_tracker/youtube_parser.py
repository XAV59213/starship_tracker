"""Pure parsing of public YouTube channel tabs (no network, no Home Assistant)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from collections.abc import Iterator
from typing import Any

VIDEO_ID = re.compile(r"[\w-]{11}", re.ASCII)


_AGO = re.compile(r"(\d+)\s*(mo|months?|y|years?|w|weeks?|d|days?|h|hours?|min|minutes?|m|s|seconds?)\b", re.I)
_AGO_UNITS = {"s": 1, "m": 60, "min": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}


def _ago_to_iso(text: str, now: datetime) -> str | None:
    """Estimate a publish date from YouTube's relative text ("4d ago", "2 years ago")."""
    match = _AGO.search(text or "")
    if not match:
        return None
    unit = match.group(2).lower()
    key = "mo" if unit.startswith("mo") else "min" if unit.startswith("min") else unit[0]
    return (now - timedelta(seconds=int(match.group(1)) * _AGO_UNITS[key])).isoformat()


_LIVE_TEXT = re.compile(r"\b(watching|en direct)\b", re.I)
_UPCOMING_TEXT = re.compile(r"\b(upcoming|premieres?|scheduled|à venir|programmé|programme)\b", re.I)
_ENDED_TEXT = re.compile(r"\b(streamed|diffusé|diffuse)\b", re.I)
_PAST_TEXT = re.compile(r"\bago\b|il y a", re.I)
_IN = re.compile(
    r"\b(?:in|premieres in|premiere in|starts in|dans)\s+(\d+)\s*"
    r"(minutes?|mins?|min|hours?|hrs?|heures?|heure|days?|jours?|jour|weeks?|semaines?|semaine|h|d|w)\b",
    re.I,
)
_ABS_DATE = re.compile(
    r"\b(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})"
    r"(?:,?\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?)?",
    re.I,
)
_SLASH_DATE = re.compile(
    r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{2,4})"
    r"(?:,?\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?)?",
    re.I,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_SCHEDULED_PREFIX = re.compile(
    r"^(?:scheduled for|premieres|premiere|starts|programmé pour|programme pour)\s+",
    re.I,
)


def _lockups(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        if isinstance(node.get("lockupViewModel"), dict):
            yield node["lockupViewModel"]
        for value in node.values():
            yield from _lockups(value)
    elif isinstance(node, list):
        for value in node:
            yield from _lockups(value)


def _renderers(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        for key in ("videoRenderer", "gridVideoRenderer"):
            if isinstance(node.get(key), dict):
                yield node[key]
        for value in node.values():
            yield from _renderers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _renderers(value)


def _grids(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        for key in ("richGridRenderer", "gridRenderer"):
            if isinstance(node.get(key), dict):
                yield node[key]
        for value in node.values():
            yield from _grids(value)
    elif isinstance(node, list):
        for value in node:
            yield from _grids(value)


def _text_content(node: Any) -> str:
    if isinstance(node, str):
        return node.strip()
    if not isinstance(node, dict):
        return ""
    for key in ("simpleText", "content"):
        if isinstance(node.get(key), str):
            return str(node[key]).strip()
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(
            str(part.get("text") or "") for part in runs if isinstance(part, dict)
        ).strip()
    return ""


def _badge_models(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Thumbnail badges, including the live and upcoming overlay styles."""
    overlays = (
        ((item.get("contentImage") or {}).get("thumbnailViewModel") or {}).get("overlays")
        or item.get("thumbnailOverlays")
        or []
    )
    models: list[dict[str, Any]] = []
    if not isinstance(overlays, list):
        overlays = []
    for overlay in overlays:
        if not isinstance(overlay, dict):
            continue
        bottom = overlay.get("thumbnailBottomOverlayViewModel") or {}
        for badge in bottom.get("badges") or []:
            model = badge.get("thumbnailBadgeViewModel") if isinstance(badge, dict) else None
            if isinstance(model, dict):
                models.append(model)
        top = overlay.get("thumbnailOverlayBadgeViewModel") or {}
        for badge in top.get("thumbnailBadges") or []:
            model = badge.get("thumbnailBadgeViewModel") if isinstance(badge, dict) else None
            if isinstance(model, dict):
                models.append(model)
        status = overlay.get("thumbnailOverlayTimeStatusRenderer")
        if isinstance(status, dict) and status:
            models.append({"text": _text_content(status.get("text")), "badgeStyle": status.get("style") or ""})
    for badge in item.get("badges") or []:
        if not isinstance(badge, dict):
            continue
        meta = badge.get("metadataBadgeRenderer") or {}
        if isinstance(meta, dict) and meta:
            models.append({"text": _text_content(meta.get("label")), "badgeStyle": meta.get("style") or ""})
    return models


def _metadata_texts(item: dict[str, Any]) -> list[str]:
    meta = (item.get("metadata") or {}).get("lockupMetadataViewModel") or {}
    rows = ((meta.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or []
    texts: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            for part in row.get("metadataParts") or []:
                if isinstance(part, dict) and (text := _text_content(part.get("text"))):
                    texts.append(text)
    for key in ("publishedTimeText", "videoInfo"):
        if text := _text_content(item.get(key)):
            texts.append(text)
    return texts


def _start_times(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        data = node.get("upcomingEventData")
        if isinstance(data, dict) and data.get("startTime") not in (None, ""):
            yield str(data["startTime"])
        for value in node.values():
            yield from _start_times(value)
    elif isinstance(node, list):
        for value in node:
            yield from _start_times(value)


def _unix_to_iso(value: str) -> str | None:
    if not re.fullmatch(r"\d{10,13}", value):
        return None
    seconds = int(value)
    if seconds > 10**12:
        seconds //= 1000
    try:
        return datetime.fromtimestamp(seconds, UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _clock(hour: int, minute: int, ampm: str | None) -> tuple[int, int] | None:
    if not 0 <= minute <= 59:
        return None
    if ampm:
        if not 1 <= hour <= 12:
            return None
        if ampm.lower() == "pm" and hour != 12:
            hour += 12
        if ampm.lower() == "am" and hour == 12:
            hour = 0
    elif not 0 <= hour <= 23:
        return None
    return hour, minute


def _stamp(year: int, month: int, day: int, hour: int, minute: int) -> str | None:
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day, hour, minute, tzinfo=UTC).isoformat()
    except ValueError:
        return None


def _parse_when(text: str, now: datetime) -> str | None:
    """Best-effort start time. Locale-independent; unknown text stays empty."""
    cleaned = _SCHEDULED_PREFIX.sub("", (text or "").strip()).rstrip(".").strip()
    if not cleaned or _PAST_TEXT.search(cleaned):
        return None
    if iso := _unix_to_iso(cleaned):
        return iso
    if match := _ABS_DATE.search(cleaned):
        month = _MONTHS[match.group("mon")[:3].lower()]
        clock = _clock(
            int(match.group("hour") or 0),
            int(match.group("minute") or 0),
            match.group("ampm"),
        )
        if clock and (iso := _stamp(int(match.group("year")), month, int(match.group("day")), *clock)):
            return iso
    if match := _SLASH_DATE.search(cleaned):
        year = int(match.group("year"))
        clock = _clock(
            int(match.group("hour") or 0),
            int(match.group("minute") or 0),
            match.group("ampm"),
        )
        if clock and (iso := _stamp(year, int(match.group("month")), int(match.group("day")), *clock)):
            return iso
    if match := _IN.search(cleaned):
        count = int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith("min") or unit == "m":
            seconds = count * 60
        elif unit.startswith("h"):
            seconds = count * 3600
        elif unit.startswith("d") or unit.startswith("jour"):
            seconds = count * 86400
        elif unit.startswith("w") or unit.startswith("sem"):
            seconds = count * 604800
        else:
            return None
        return (now + timedelta(seconds=seconds)).isoformat()
    return None


def _scheduled_iso(texts: list[str], labels: list[str], starts: list[str], now: datetime) -> str | None:
    for value in starts:
        if iso := _unix_to_iso(value):
            return iso
    for text in (*labels, *texts):
        if iso := _parse_when(text, now):
            return iso
    return None


def _is_future(iso: str, now: datetime) -> bool:
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment > now


def _live_status(
    styles: list[str],
    labels: list[str],
    texts: list[str],
    scheduled: str | None,
    now: datetime,
    *,
    streams: bool,
) -> str:
    """upcoming, live, ended, or empty when the tab does not say."""
    style_blob = " ".join(styles).upper()
    label_blob = " ".join(labels)
    text_blob = " ".join(texts)
    if (
        "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE" in style_blob
        or "BADGE_STYLE_TYPE_LIVE_NOW" in style_blob
        or re.search(r"(^|_)LIVE($|_)", style_blob)
        or any(label.casefold() in {"live", "en direct"} for label in labels)
        or _LIVE_TEXT.search(label_blob)
        or _LIVE_TEXT.search(text_blob)
    ):
        return "live"
    if _ENDED_TEXT.search(text_blob) or _ENDED_TEXT.search(label_blob):
        return "ended"
    if (
        "UPCOMING" in style_blob
        or _UPCOMING_TEXT.search(label_blob)
        or _UPCOMING_TEXT.search(text_blob)
        or (scheduled and _is_future(scheduled, now))
    ):
        return "upcoming"
    if streams and (_PAST_TEXT.search(text_blob) or _PAST_TEXT.search(label_blob)):
        return "ended"
    return ""


def _video_from_item(
    item: dict[str, Any], keyword: str, now: datetime, *, streams: bool, allow_any_live: bool
) -> dict[str, Any] | None:
    video_id = str(item.get("contentId") or item.get("videoId") or "")
    meta = (item.get("metadata") or {}).get("lockupMetadataViewModel") or {}
    title = _text_content(meta.get("title")) or _text_content(item.get("title"))
    if not VIDEO_ID.fullmatch(video_id) or not title:
        return None
    texts = _metadata_texts(item)
    badges = _badge_models(item)
    styles = [str(badge.get("badgeStyle") or "") for badge in badges]
    labels = [label for label in (_text_content(badge.get("text")) for badge in badges) if label]
    starts = list(_start_times(item))
    exact_start = any(_unix_to_iso(value) for value in starts)
    scheduled = _scheduled_iso(texts, labels, starts, now)
    status = _live_status(styles, labels, texts, scheduled, now, streams=streams)
    published = next((iso for iso in (_ago_to_iso(text, now) for text in texts if _PAST_TEXT.search(text)) if iso), None)
    if status in {"upcoming", "live"} and not published:
        published = scheduled or now.isoformat()
    if status == "upcoming" and not scheduled and published and _is_future(published, now):
        scheduled = published
    if not published:
        return None
    if keyword.casefold() not in title.casefold() and not (allow_any_live and status in {"upcoming", "live"}):
        return None
    video: dict[str, Any] = {
        "video_id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published": published,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }
    if status:
        video["live_status"] = status
    if status == "upcoming" and scheduled:
        video["scheduled"] = scheduled
        if not exact_start:
            # Text dates follow YouTube's display time zone: approximate.
            video["scheduled_approx"] = True
    return video


def _remember(videos: dict[str, dict[str, Any]], order: list[str], video: dict[str, Any]) -> None:
    current = videos.get(video["video_id"])
    if current is None:
        videos[video["video_id"]] = video
        order.append(video["video_id"])
        return
    for key in ("live_status", "scheduled", "scheduled_approx"):
        if video.get(key) and not current.get(key):
            current[key] = video[key]


def parse_channel_tab(
    page: str, keyword: str, now: datetime, *, streams: bool = False
) -> list[dict[str, Any]]:
    """Read one public channel tab. Streams may carry upcoming, live and ended states.

    Missing or unexpected markup yields what can be read, never an exception.
    Every video, live or not, must match the keyword (Starship only).
    """
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return []
    grids = list(_grids(data))
    items: list[Any] = []
    for grid in grids or [data]:
        items.extend(_lockups(grid))
        items.extend(_renderers(grid))
    videos: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            video = _video_from_item(
                item, keyword, now, streams=streams, allow_any_live=False
            )
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
        if video:
            _remember(videos, order, video)
    return [videos[video_id] for video_id in order]


def merge_videos(*lists: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    """Deduplicate by video id (RSS dates win) and sort newest first.

    A later copy can still add live_status or scheduled when the RSS entry has none.
    """
    merged: dict[str, dict[str, Any]] = {}
    for videos in lists:
        for video in videos:
            current = merged.get(video["video_id"])
            if current is None:
                merged[video["video_id"]] = dict(video)
                continue
            for key in ("live_status", "scheduled", "scheduled_approx"):
                if video.get(key) and not current.get(key):
                    current[key] = video[key]
    return sorted(merged.values(), key=lambda v: datetime.fromisoformat(v["published"]), reverse=True)[:limit]


