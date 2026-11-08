"""Optional, keyless YouTube channel feeds and persistent video notifications."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, YOUTUBE_KNOWN_HANDLES
from .youtube_parser import merge_videos, parse_channel_tab  # re-exported

_LOGGER = logging.getLogger(__name__)
CHANNEL_ID = re.compile(r"UC[\w-]{22}", re.ASCII)
VIDEO_ID = re.compile(r"[\w-]{11}", re.ASCII)
MAX_RESPONSE = 1024 * 1024
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


YOUTUBE_TIMEOUT = 15
YOUTUBE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}
# Anonymous consent preferences, not account/authentication cookies. These are
# supplied per request, never read from a user's browser or credential storage.
YOUTUBE_CONSENT_COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI"}


class YouTubeConsentError(ValueError):
    """The public page still redirects to an EU consent screen."""


class _ChannelMetadataParser(HTMLParser):
    """Read channel-owned head metadata, not IDs of recommended channels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical: list[str] = []
        self.identifiers: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            tag == "link"
            and "canonical" in (attributes.get("rel") or "").lower().split()
        ):
            url = urlparse(attributes.get("href") or "")
            path = url.path.rstrip("/")
            if (
                url.scheme == "https"
                and url.hostname in {"youtube.com", "www.youtube.com"}
                and path.startswith("/channel/")
                and CHANNEL_ID.fullmatch(path[9:])
            ):
                self.canonical.append(path[9:])
        elif tag == "meta":
            kind = (
                attributes.get("itemprop") or attributes.get("name") or ""
            ).casefold()
            content = attributes.get("content") or ""
            if kind in {"identifier", "channelid"} and CHANNEL_ID.fullmatch(content):
                self.identifiers.append(content)


def parse_channel_id(page: str) -> str:
    """Prefer canonical channel URLs, then externalId, then explicit meta IDs.

    Generic JSON channelId occurs in recommended videos and is never trusted.
    """
    metadata = _ChannelMetadataParser()
    metadata.feed(page)
    if metadata.canonical:
        return metadata.canonical[0]
    if match := re.search(r'"externalId"\s*:\s*"(UC[\w-]{22})"', page, re.ASCII):
        return match.group(1)
    if metadata.identifiers:
        return metadata.identifiers[0]
    raise ValueError("No channel-owned YouTube metadata found; use a UC channel ID")


async def _read_text(
    response: aiohttp.ClientResponse, limit: int = MAX_RESPONSE
) -> str:
    """Bound memory usage for public HTML and XML."""
    data = bytearray()
    async for chunk in response.content.iter_chunked(16384):
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError("YouTube response too large")
    return data.decode("utf-8-sig")


async def async_resolve_channel(session: aiohttp.ClientSession, value: str) -> str:
    """Accept an ID, handle or public YouTube channel URL; restrict fetch hosts."""
    value = value.strip()
    if CHANNEL_ID.fullmatch(value):
        return value
    if value.startswith("@"):
        path = "/" + value
    else:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname
            not in {"youtube.com", "www.youtube.com", "m.youtube.com"}
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Use a YouTube channel URL, @handle or UC channel ID")
        path = parsed.path.rstrip("/")
        # URLs copied from a channel's Videos/Live tab are accepted too.
        path = re.sub(r"/(videos|streams|shorts|featured|about)$", "", path)
    if path.startswith("/channel/") and CHANNEL_ID.fullmatch(path[9:]):
        return path[9:]
    if not re.fullmatch(r"/(?:@[\w.-]{1,100}|(?:c|user)/[\w.-]{1,100})", path):
        raise ValueError("Not a YouTube channel")
    # The three suggested channels are pinned to verified public IDs. This is
    # also our offline/consent fallback: no network is needed for these aliases.
    if known_id := YOUTUBE_KNOWN_HANDLES.get(path[1:].casefold()):
        return known_id
    async with asyncio.timeout(YOUTUBE_TIMEOUT):
        async with session.get(
            "https://www.youtube.com" + path,
            allow_redirects=False,
            headers=YOUTUBE_HEADERS,
            cookies=YOUTUBE_CONSENT_COOKIES,
        ) as response:
            location = response.headers.get("Location", "")
            if response.status in {301, 302, 303, 307, 308} and urlparse(
                location
            ).hostname in {"consent.youtube.com", "consent.google.com"}:
                raise YouTubeConsentError(
                    "YouTube consent required; enter the UC channel ID"
                )
            if response.status != 200:
                raise ValueError("YouTube channel page unavailable")
            return parse_channel_id(await _read_text(response, 4 * MAX_RESPONSE))


def parse_feed(xml: str, keyword: str = "starship") -> list[dict[str, str]]:
    """Read bounded Atom XML, rejecting DTD/entity declarations before parsing.

    ElementTree never fetches external entities. Rejecting declarations also
    prevents internal entity expansion; only UTF-8 text is accepted by the fetcher.
    """
    if (
        len(xml) > MAX_RESPONSE
        or "<!DOCTYPE" in xml.upper()
        or "<!ENTITY" in xml.upper()
    ):
        raise ValueError("Unsafe YouTube feed")
    root = ET.fromstring(xml)
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("Not an Atom feed")
    videos = []
    for entry in root.findall("a:entry", NS):
        video_id = entry.findtext("yt:videoId", "", NS)
        title = entry.findtext("a:title", "", NS).strip()
        published = entry.findtext("a:published", "", NS)
        if (
            not VIDEO_ID.fullmatch(video_id)
            or not title
            or keyword.casefold() not in title.casefold()
        ):
            continue
        try:
            dt = datetime.fromisoformat(published)
            if dt.tzinfo is None:
                continue
        except ValueError:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published": dt.isoformat(),
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            }
        )
    return sorted(
        videos,
        key=lambda video: datetime.fromisoformat(video["published"]),
        reverse=True,
    )


async def async_fetch_feed(
    session: aiohttp.ClientSession, channel: str, keyword: str
) -> list[dict[str, str]]:
    """Fetch the channel's recent public uploads (YouTube RSS has a limited history)."""
    async with asyncio.timeout(YOUTUBE_TIMEOUT):
        async with session.get(
            "https://www.youtube.com/feeds/videos.xml",
            params={"channel_id": channel},
            headers=YOUTUBE_HEADERS,
            cookies=YOUTUBE_CONSENT_COOKIES,
        ) as response:
            response.raise_for_status()
            return parse_feed(await _read_text(response), keyword)


async def async_fetch_channel_videos(
    session: aiohttp.ClientSession, channel: str, keyword: str
) -> list[dict[str, str]]:
    """Older matching videos/lives from public channel tabs (best effort)."""
    now = datetime.now(UTC)
    found: list[dict[str, str]] = []
    for tab in ("videos", "streams"):
        try:
            async with asyncio.timeout(YOUTUBE_TIMEOUT):
                async with session.get(
                    f"https://www.youtube.com/channel/{channel}/{tab}",
                    params={"hl": "en"}, headers=YOUTUBE_HEADERS, cookies=YOUTUBE_CONSENT_COOKIES,
                ) as response:
                    response.raise_for_status()
                    found += parse_channel_tab(
                        await _read_text(response, 6 * MAX_RESPONSE),
                        keyword,
                        now,
                        streams=tab == "streams",
                    )
        except Exception as err:  # noqa: BLE001 - best effort, never blocks the RSS sensor
            _LOGGER.debug("YouTube tab %s/%s: %s", channel, tab, err)
    return found


class YouTubeCoordinator(DataUpdateCoordinator[dict[str, str] | None]):
    """Independent coordinator per language: one broken channel cannot hide another."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        language: str,
        channel: str,
        keyword: str,
        *,
        source: str | None = None,
    ) -> None:
        source = source or language
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_youtube_{source}",
            update_interval=timedelta(minutes=10),
        )
        self.language = language
        self.channel = channel
        self.keyword = keyword
        scope = hashlib.sha256(f"{channel}:{keyword.casefold()}".encode()).hexdigest()[
            :16
        ]
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.youtube.{source}.{scope}"
        )
        self._loaded = False
        self._initialized = False
        self._seen: list[str] = []
        self._latest: dict[str, str] | None = None
        self._live_states: dict[str, str] = {}

    async def _async_update_data(self) -> dict[str, str] | None:
        if not self._loaded:
            saved = await self._store.async_load() or {}
            self._initialized = bool(saved.get("initialized", False))
            self._seen = saved.get("seen", [])
            self._latest = saved.get("latest")
            self._live_states = saved.get("live_states", {})
            self._loaded = True
        try:
            videos = await async_fetch_feed(
                async_get_clientsession(self.hass), self.channel, self.keyword
            )
        except (aiohttp.ClientError, TimeoutError, ValueError, ET.ParseError) as err:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="youtube_failed", translation_placeholders={"language": self.language, "error": str(err)}) from err
        new = [
            video for video in reversed(videos) if video["video_id"] not in self._seen
        ]
        latest = self._latest
        if videos and (
            not latest
            or datetime.fromisoformat(videos[0]["published"])
            >= datetime.fromisoformat(latest["published"])
        ):
            latest = {**videos[0], "channel": self.channel}
        if latest:
            # Last 50 Starship videos for the card carousel: RSS plus public channel tabs.
            # Tabs are best effort: any failure must leave the RSS sensor available.
            try:
                extra = await async_fetch_channel_videos(
                    async_get_clientsession(self.hass), self.channel, self.keyword
                )
            except Exception as err:  # noqa: BLE001 - best effort, never blocks the RSS sensor
                _LOGGER.debug("YouTube tabs %s: %s", self.channel, err)
                extra = []
            latest = {**latest, "videos": merge_videos(videos, extra)}
        live_states = {
            video["video_id"]: video["live_status"]
            for video in (latest or {}).get("videos", [])
            if video.get("live_status") in ("upcoming", "live")
        }
        live_changes = [
            video
            for video in (latest or {}).get("videos", [])
            if video["video_id"] in live_states
            and self._live_states.get(video["video_id"]) != live_states[video["video_id"]]
        ]
        seen = list(
            dict.fromkeys([*self._seen, *(video["video_id"] for video in new)])
        )[-200:]
        if (
            not self._initialized
            or seen != self._seen
            or latest != self._latest
            or live_states != self._live_states
        ):
            # Persist before firing: a restart must never replay an already notified video.
            await self._store.async_save(
                {"initialized": True, "seen": seen, "latest": latest, "live_states": live_states}
            )
        if self._initialized:
            for video in new:
                self.hass.bus.async_fire(
                    f"{DOMAIN}_youtube_video",
                    {
                        "language": self.language,
                        "channel": self.channel,
                        **{key: video[key] for key in ("title", "url", "published")},
                    },
                )
            for video in live_changes:
                # upcoming or live, once per state per video (persisted).
                self.hass.bus.async_fire(
                    f"{DOMAIN}_youtube_live",
                    {
                        "language": self.language,
                        "channel": self.channel,
                        "status": video["live_status"],
                        "scheduled": video.get("scheduled"),
                        **{key: video[key] for key in ("title", "url")},
                    },
                )
        self._initialized = True
        self._live_states = live_states
        self._seen = seen
        self._latest = latest
        return latest
