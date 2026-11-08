"""Extraction de la date de lancement depuis le texte d'une page mission SpaceX.

Le flux ``launches-page-tiles`` laisse parfois ``launchDate``, ``launchTime`` et
``endDate`` à null. La date est alors seulement dans la prose, par exemple :
« preparing to launch as soon as Friday, November 13 [...]. The 75-minute launch
window will open at 4:45 p.m. CT. »
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

DATE_SOURCE_FEED = "feed"
DATE_SOURCE_MISSION_PAGE = "mission_page"

_FEED_DATE_FIELDS = ("launchDate", "launchTime", "endDate")

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Noms longs d'abord pour que « September » ne soit pas lu comme « Sept ».
_MONTH = (
    r"January|February|March|April|May|June|July|August|September|Sept|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
)
_ORDINAL = r"(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>20\d{2})"

_DATE_MDY = re.compile(
    rf"\b(?P<month>{_MONTH})\.?\s+(?P<day>\d{{1,2}}){_ORDINAL}\b(?:\s*,?\s*{_YEAR}\b)?",
    re.IGNORECASE,
)
_DATE_DMY = re.compile(
    rf"\b(?P<day>\d{{1,2}}){_ORDINAL}\s+(?P<month>{_MONTH})\.?\b(?:\s*,?\s*{_YEAR}\b)?",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*"
    r"(?P<ampm>a\.?\s*m\.?|p\.?\s*m\.?)"
    r"(?:\s*(?P<tz>CDT|CST|CT|EDT|EST|ET|PDT|PST|PT|UTC|GMT)\b)?",
    re.IGNORECASE,
)
_WINDOW = re.compile(r"\b(?P<minutes>\d+)\s*-\s*minutes?\b", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")

# CT/CDT/CST désignent l'heure légale de Starbase : zoneinfo choisit CST ou CDT.
_ZONES = {
    "CT": "America/Chicago",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "PT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "UTC": "UTC",
    "GMT": "UTC",
}


@dataclass(frozen=True)
class ParsedLaunch:
    """Instant UTC (éventuel) et fenêtre extraits d'une page mission."""

    when: datetime | None
    has_time: bool
    launch_window_minutes: int | None

    def __post_init__(self) -> None:
        if self.when is None:
            return
        if self.when.tzinfo is None:
            raise ValueError("when doit être conscient du fuseau")
        object.__setattr__(self, "when", self.when.astimezone(timezone.utc))

    @property
    def launch_date(self) -> str | None:
        """Date calendaire UTC ``YYYY-MM-DD`` consommée par ``launch_datetime``."""
        if self.when is None:
            return None
        return self.when.date().isoformat()

    @property
    def launch_time(self) -> str | None:
        """Heure UTC ``HH:MM:SS+00:00``, ou None si l'heure n'est pas connue."""
        if self.when is None or not self.has_time:
            return None
        return self.when.strftime("%H:%M:%S") + "+00:00"


def tile_needs_mission_page(tile: dict[str, Any]) -> bool:
    """True si launchDate, launchTime et endDate sont vides et qu'un lien existe."""
    if any(tile.get(field) for field in _FEED_DATE_FIELDS):
        return False
    return bool(tile.get("link"))


def tile_sort_key(tile: dict[str, Any], parsed: ParsedLaunch | None) -> tuple[str, str]:
    """Clé de tri : date du flux, sinon date lue sur la page mission."""
    if tile_needs_mission_page(tile) and parsed is not None and parsed.launch_date:
        return (parsed.launch_date, parsed.launch_time or "")
    return (str(tile.get("launchDate") or "9999"), str(tile.get("launchTime") or ""))


def apply_launch_fields(
    mission: dict[str, Any],
    tile: dict[str, Any],
    parsed: ParsedLaunch | None,
) -> dict[str, Any]:
    """Renseigne date_source et, à défaut du flux, la date lue sur la page mission.

    Les champs du flux (``launchDate`` / ``launchTime`` / ``endDate``) restent
    prioritaires dès que l'un d'eux est présent.
    """
    mission["launch_window_minutes"] = None
    if not tile_needs_mission_page(tile):
        mission["date_source"] = (
            DATE_SOURCE_FEED if any(tile.get(field) for field in _FEED_DATE_FIELDS) else None
        )
        return mission
    if parsed is None or (parsed.launch_date is None and parsed.launch_window_minutes is None):
        mission["date_source"] = None
        return mission
    if parsed.launch_date:
        mission["launch_date"] = parsed.launch_date
    if parsed.has_time and parsed.launch_time:
        mission["launch_time"] = parsed.launch_time
    mission["launch_window_minutes"] = parsed.launch_window_minutes
    mission["date_source"] = DATE_SOURCE_MISSION_PAGE
    return mission


def parse_mission_page(payload: dict[str, Any] | None, now: datetime | None = None) -> ParsedLaunch | None:
    """Lit ``paragraphs[].content`` d'une page ``/missions/{link}``."""
    if not isinstance(payload, dict):
        return None
    parts: list[str] = []
    for paragraph in payload.get("paragraphs") or []:
        if isinstance(paragraph, dict):
            content = paragraph.get("content")
        else:
            content = paragraph
        if isinstance(content, str) and content.strip():
            parts.append(content)
    if not parts:
        return None
    return parse_launch_prose("\n".join(parts), now=now)


def parse_launch_prose(text: str, now: datetime | None = None) -> ParsedLaunch | None:
    """Extrait mois/jour (année optionnelle), heure am/pm + fuseau, et fenêtre N-minute."""
    plain = _plain(text)
    if not plain:
        return None
    reference = _as_utc(now or datetime.now(timezone.utc))
    window = _window_minutes(plain)
    resolved = _resolve_date(plain, reference)
    if resolved is None and window is None:
        return None
    when, has_time = resolved if resolved is not None else (None, False)
    return ParsedLaunch(when=when, has_time=has_time, launch_window_minutes=window)


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", html.unescape(text or ""))).strip()


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _window_minutes(text: str) -> int | None:
    match = _WINDOW.search(text)
    if match is None:
        return None
    return int(match.group("minutes"))


def _month_number(name: str) -> int | None:
    return _MONTHS.get(name.lower().rstrip("."))


def _to_24(hour: int, ampm: str) -> int | None:
    if hour < 1 or hour > 12:
        return None
    kind = re.sub(r"[^ap]", "", ampm.lower())
    if kind == "a":
        return 0 if hour == 12 else hour
    if kind == "p":
        return 12 if hour == 12 else hour + 12
    return None


def _build(year: int, month: int, day: int, hour: int, minute: int, tz: datetime.tzinfo) -> datetime | None:
    if day < 1 or day > 31 or minute > 59 or hour > 23:
        return None
    try:
        return datetime(year, month, day, hour, minute, tzinfo=tz)
    except (ValueError, OverflowError):
        return None


def _date_matches(text: str) -> list[re.Match[str]]:
    found = [*_DATE_MDY.finditer(text), *_DATE_DMY.finditer(text)]
    found.sort(key=lambda match: match.start())
    return found


def _zoned_time(text: str) -> tuple[int, int, ZoneInfo] | None:
    """Première heure am/pm avec fuseau, de préférence celle qui suit la fenêtre."""
    found: list[tuple[re.Match[str], int, int, ZoneInfo]] = []
    for match in _TIME.finditer(text):
        hour = _to_24(int(match.group("hour")), match.group("ampm"))
        minute = int(match.group("minute"))
        label = match.group("tz")
        if hour is None or minute > 59 or not label:
            continue
        zone = _ZONES.get(label.upper())
        if zone is None:
            continue
        found.append((match, hour, minute, ZoneInfo(zone)))
    if not found:
        return None
    window = _WINDOW.search(text)
    if window is not None:
        after = [item for item in found if item[0].start() >= window.start()]
        if after:
            found = after
    _, hour, minute, zone = found[0]
    return hour, minute, zone


def _next_year(month: int, day: int, hour: int, minute: int, tz: datetime.tzinfo, today: datetime) -> datetime | None:
    """Prochaine occurrence du mois/jour (aujourd'hui inclus), dans ``tz``."""
    year = today.astimezone(tz).year
    local_today = today.astimezone(tz).date()
    built = _build(year, month, day, hour, minute, tz)
    if built is not None and built.date() >= local_today:
        return built
    for offset in range(1, 9):
        built = _build(year + offset, month, day, hour, minute, tz)
        if built is not None:
            return built
    return None


def _resolve_date(text: str, now: datetime) -> tuple[datetime, bool] | None:
    clock = _zoned_time(text)
    for match in _date_matches(text):
        month = _month_number(match.group("month"))
        if month is None:
            continue
        day = int(match.group("day"))
        year_text = match.group("year")
        year = int(year_text) if year_text else None
        if clock is None:
            tz: datetime.tzinfo = timezone.utc
            hour, minute, has_time = 0, 0, False
        else:
            hour, minute, tz = clock
            has_time = True
        if year is None:
            built = _next_year(month, day, hour, minute, tz, now)
        else:
            built = _build(year, month, day, hour, minute, tz)
        if built is None:
            continue
        return built, has_time
    return None


MISSION_DESCRIPTION_MAX = 1500
_HREF = re.compile(r"""href\s*=\s*["']?(https?://[^"'\s>]+)""", re.IGNORECASE)
_CMS_BASE = "https://content.spacex.com"


def image_url(image: Any) -> str | None:
    """URL absolue d'une image Strapi (format « large » de préférence)."""
    if not isinstance(image, dict):
        return None
    formats = image.get("formats") or {}
    url = None
    for size in ("large", "medium"):
        fmt = formats.get(size) if isinstance(formats, dict) else None
        if isinstance(fmt, dict) and fmt.get("url"):
            url = fmt["url"]
            break
    url = url or image.get("url")
    if not isinstance(url, str) or not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return _CMS_BASE + url
    return url if url.startswith(("http://", "https://")) else None


def extract_mission_details(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Image, description texte (limitée) et liens d'une page ``/missions/{link}``."""
    if not isinstance(payload, dict):
        return {}
    texts: list[str] = []
    links: list[str] = []
    for paragraph in payload.get("paragraphs") or []:
        content = paragraph.get("content") if isinstance(paragraph, dict) else paragraph
        if not isinstance(content, str):
            continue
        for href in _HREF.findall(content):
            if href not in links:
                links.append(href)
        plain = _plain(content)
        if plain:
            texts.append(plain)
    description = "\n\n".join(texts)
    if len(description) > MISSION_DESCRIPTION_MAX:
        description = description[: MISSION_DESCRIPTION_MAX - 1].rstrip() + "…"
    webcasts: list[str] = []
    for cast in payload.get("webcasts") or []:
        url = None
        if isinstance(cast, dict):
            url = cast.get("url") or cast.get("link") or cast.get("videoUrl")
        elif isinstance(cast, str):
            url = cast
        if url is None and isinstance(cast, dict):
            video = webcast_video(cast)
            url = video["url"] if video else None
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in webcasts:
            webcasts.append(url)
    videos = [v for v in (webcast_video(c) for c in payload.get("webcasts") or []) if v][:3]
    file_url = _file_url(payload.get("videoDesktop")) or _file_url(payload.get("videoMobile"))
    if file_url:
        videos.insert(0, {"type": "file", "url": file_url, "embed": file_url})
    return {
        "mission_image": image_url(payload.get("imageDesktop")) or image_url(payload.get("imageMobile")),
        "mission_image_mobile": image_url(payload.get("imageMobile")),
        "mission_description": description or None,
        "mission_links": links[:8],
        "webcast_links": webcasts[:5],
        "mission_videos": videos,
        "mission_infographic": image_url(payload.get("infographicDesktop")),
        "mission_infographic_mobile": image_url(payload.get("infographicMobile")),
        "mission_countdown": timeline_entries(payload.get("preLaunchTimeline")),
        "mission_timeline": timeline_entries(payload.get("postLaunchTimeline")),
    }


TIMELINE_MAX_ENTRIES = 30
TIMELINE_DESC_MAX = 160


def timeline_entries(timeline: Any) -> list[list[str]]:
    """``[[\"00:00:00\", \"Liftoff\"], ...]`` depuis un pre/postLaunchTimeline (taille bornée)."""
    if not isinstance(timeline, dict):
        return []
    out: list[list[str]] = []
    for entry in timeline.get("timelineEntries") or []:
        if not isinstance(entry, dict):
            continue
        time = _plain(str(entry.get("time") or ""))[:16]
        desc = _plain(str(entry.get("description") or ""))
        if not desc:
            continue
        if len(desc) > TIMELINE_DESC_MAX:
            desc = desc[: TIMELINE_DESC_MAX - 1].rstrip() + "…"
        out.append([time, desc])
        if len(out) >= TIMELINE_MAX_ENTRIES:
            break
    return out


def _file_url(media: Any) -> str | None:
    if not isinstance(media, dict):
        return None
    url = media.get("url")
    if isinstance(url, str) and url.startswith("/"):
        url = _CMS_BASE + url
    return url if isinstance(url, str) and url.startswith(("http://", "https://")) else None


def webcast_video(cast: Any) -> dict[str, str] | None:
    """Lien (et embed YouTube) d'un webcast ``{streamingVideoType, videoId}``."""
    if not isinstance(cast, dict):
        return None
    vid = str(cast.get("videoId") or "").strip()
    kind = str(cast.get("streamingVideoType") or "").lower()
    if not vid or not re.fullmatch(r"[A-Za-z0-9_\-]+(?:[&?#].*)?", vid):
        return None
    base = re.split(r"[&?#]", vid, maxsplit=1)[0]
    if "youtube" in kind:
        return {
            "type": "youtube",
            "url": f"https://www.youtube.com/watch?v={base}",
            "embed": f"https://www.youtube-nocookie.com/embed/{base}",
        }
    if kind == "x-live-studio":
        return {"type": "x", "url": f"https://x.com/i/broadcasts/{base}"}
    if kind in ("x.com", "x", "twitter"):
        return {"type": "x", "url": f"https://x.com/SpaceX/status/{base}"}
    return None
