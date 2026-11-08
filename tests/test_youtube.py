"""Public channel resolution, safe Atom parsing and restart-proof alerts."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starship_tracker.const import DOMAIN, YOUTUBE_KNOWN_HANDLES
from custom_components.starship_tracker.youtube_coordinator import (
    YOUTUBE_CONSENT_COOKIES,
    YOUTUBE_HEADERS,
    YouTubeConsentError,
    YouTubeCoordinator,
    async_fetch_feed,
    async_resolve_channel,
    merge_videos,
    parse_channel_id,
    parse_channel_tab,
    parse_feed,
)

CHANNEL = "UC" + "a" * 22
OTHER_CHANNEL = "UC" + "b" * 22
URL = "https://www.youtube.com/feeds/videos.xml"
FETCH = "custom_components.starship_tracker.youtube_coordinator.async_fetch_feed"
TABS = "custom_components.starship_tracker.youtube_coordinator.async_fetch_channel_videos"


def feed(entries):
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
        + "".join(
            f"<entry><yt:videoId>{vid}</yt:videoId><title>{title}</title><published>{date}</published></entry>"
            for vid, title, date in entries
        )
        + "</feed>"
    )


OLD = ("aaaaaaaaaaa", "Starship old", "2026-11-07T10:00:00Z")
NEW = ("bbbbbbbbbbb", "STARSHIP new &amp; flight", "2026-11-08T10:00:00+00:00")


def test_parse_feed_order_filter_and_attributes():
    videos = parse_feed(feed([OLD, ("ccccccccccc", "Falcon", OLD[2]), NEW]))
    assert [v["video_id"] for v in videos] == [NEW[0], OLD[0]]
    assert videos[0] == {
        "video_id": NEW[0],
        "title": "STARSHIP new & flight",
        "published": "2026-11-08T10:00:00+00:00",
        "url": f"https://www.youtube.com/watch?v={NEW[0]}",
        "thumbnail": f"https://i.ytimg.com/vi/{NEW[0]}/hqdefault.jpg",
    }
    assert len(parse_feed(feed([OLD, ("ccccccccccc", "Falcon", OLD[2])]), "")) == 2
    assert parse_feed(feed([OLD]), "artemis") == []
    assert parse_feed(feed([])) == []


def test_bad_entries_are_skipped():
    assert (
        parse_feed(
            feed(
                [
                    ("bad", "Starship", OLD[2]),
                    (OLD[0], "Starship", "invalid"),
                    (OLD[0], "Starship", "2026-11-08"),
                    (OLD[0], "", OLD[2]),
                ]
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "xml",
    [
        "<bad>",
        "<html/>",
        '<!DOCTYPE feed [<!ENTITY x "xx">]><feed/>',
        "x" * (1024 * 1024 + 1),
    ],
)
def test_unsafe_or_malformed_xml(xml):
    with pytest.raises((ValueError, ET.ParseError)):
        parse_feed(xml)


@pytest.mark.parametrize(
    "page",
    [
        f'<meta itemprop="identifier" content="{CHANNEL}">',
        f'<meta content="{CHANNEL}" itemprop="channelId">',
        f'{{"externalId": "{CHANNEL}"}}',
        f'<link rel="canonical" href="https://www.youtube.com/channel/{CHANNEL}">',
    ],
)
def test_channel_metadata(page):
    assert parse_channel_id(page) == CHANNEL
    with pytest.raises(ValueError):
        parse_channel_id("<html>consent</html>")


async def test_resolve_channel_urls_and_handles(hass, aioclient_mock):
    session = async_get_clientsession(hass)
    try:
        for value in (
            CHANNEL,
            "https://www.youtube.com/channel/" + CHANNEL,
            "https://m.youtube.com/channel/" + CHANNEL + "/videos",
        ):
            assert await async_resolve_channel(session, value) == CHANNEL
        assert aioclient_mock.call_count == 0
        aioclient_mock.get(
            "https://www.youtube.com/@Example", text=f'{{"externalId":"{CHANNEL}"}}'
        )
        aioclient_mock.get(
            "https://www.youtube.com/c/Example",
            text=f'<meta itemprop="identifier" content="{CHANNEL}">',
        )
        aioclient_mock.get(
            "https://www.youtube.com/user/Example",
            text=f'<meta itemprop="identifier" content="{CHANNEL}">',
        )
        for value in (
            "@Example",
            "https://www.youtube.com/@Example/streams",
            "https://youtube.com/c/Example",
            "https://youtube.com/user/Example",
        ):
            assert await async_resolve_channel(session, value) == CHANNEL
    finally:
        await session.close()


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.com/@Example",
        "http://youtube.com/@Example",
        "https://youtube.com.evil.com/@Example",
        "https://evil@youtube.com/@Example",
        "https://youtube.com:8443/@Example",
        "https://youtube.com/watch?v=x",
        "@../bad",
        "bad",
    ],
)
async def test_resolution_rejects_non_channels(value, hass, aioclient_mock):
    async with async_get_clientsession(hass) as session:
        with pytest.raises(ValueError):
            await async_resolve_channel(session, value)
    assert aioclient_mock.call_count == 0


async def test_resolution_http_failure_and_oversize(hass, aioclient_mock):
    aioclient_mock.get("https://www.youtube.com/@Missing", status=404)
    aioclient_mock.get(
        "https://www.youtube.com/@Huge", text="x" * (4 * 1024 * 1024 + 1)
    )
    async with async_get_clientsession(hass) as session:
        for value in ("@Missing", "@Huge"):
            with pytest.raises(ValueError):
                await async_resolve_channel(session, value)


async def test_fetch_feed(hass, aioclient_mock):
    aioclient_mock.get(URL + "?channel_id=" + CHANNEL, text=feed([OLD]))
    async with async_get_clientsession(hass) as session:
        assert (await async_fetch_feed(session, CHANNEL, "starship"))[0][
            "video_id"
        ] == OLD[0]


def coordinator(hass, channel=CHANNEL, keyword="starship", language="fr"):
    entry = MockConfigEntry(domain=DOMAIN, entry_id="youtube_test", data={})
    return YouTubeCoordinator(hass, entry, language, channel, keyword)


async def test_event_baseline_new_and_restart(hass):
    events = []
    hass.bus.async_listen("starship_tracker_youtube_video", events.append)
    c = coordinator(hass)
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([OLD])))):
        assert (await c._async_update_data())["video_id"] == OLD[0]
    await hass.async_block_till_done()
    assert not events
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([NEW, OLD])))):
        await c._async_update_data()
        await c._async_update_data()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {
        "language": "fr",
        "title": "STARSHIP new & flight",
        "url": f"https://www.youtube.com/watch?v={NEW[0]}",
        "channel": CHANNEL,
        "published": "2026-11-08T10:00:00+00:00",
    }
    # A genuinely new coordinator loads the real HA Store, not an in-memory mock.
    restarted = coordinator(hass)
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([NEW, OLD])))):
        assert (await restarted._async_update_data())["video_id"] == NEW[0]
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_empty_baseline_then_new_and_channel_switch(hass):
    events = []
    hass.bus.async_listen("starship_tracker_youtube_video", events.append)
    c = coordinator(hass, language="en")
    with patch(FETCH, AsyncMock(return_value=[])):
        assert await c._async_update_data() is None
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([NEW])))):
        await c._async_update_data()
        # A changed channel or filter is a new baseline, not a notification storm.
        await coordinator(
            hass, channel=OTHER_CHANNEL, language="en"
        )._async_update_data()
        await coordinator(hass, keyword="", language="en")._async_update_data()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["language"] == "en"


async def test_failed_first_poll_does_not_initialize_or_alert(hass):
    c = coordinator(hass)
    events = []
    hass.bus.async_listen("starship_tracker_youtube_video", events.append)
    with patch(FETCH, AsyncMock(side_effect=TimeoutError)), pytest.raises(UpdateFailed):
        await c._async_update_data()
    assert not c._initialized
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([NEW])))):
        await c._async_update_data()
    await hass.async_block_till_done()
    assert not events


async def test_persist_before_alert_and_keep_latest_when_feed_rolls_over(hass):
    c = coordinator(hass)
    with patch(FETCH, AsyncMock(return_value=parse_feed(feed([OLD])))):
        await c._async_update_data()
    events = []
    hass.bus.async_listen("starship_tracker_youtube_video", events.append)
    with (
        patch(FETCH, AsyncMock(return_value=parse_feed(feed([NEW])))),
        patch.object(c._store, "async_save", AsyncMock(side_effect=OSError)),
        pytest.raises(OSError),
    ):
        await c._async_update_data()
    await hass.async_block_till_done()
    assert not events
    with patch(FETCH, AsyncMock(return_value=[])):
        assert (await c._async_update_data())["video_id"] == OLD[0]


def _tab_page(items, *, grid=True):
    body = {"contents": items}
    if grid:
        body = {"contents": {"richGridRenderer": {"contents": items}}}
    return "<script>var ytInitialData = " + json.dumps(body) + ";</script>"


def _lockup(video_id, title, texts, badges=None, start=None):
    item = {
        "contentId": video_id,
        "metadata": {"lockupMetadataViewModel": {
            "title": {"content": title},
            "metadata": {"contentMetadataViewModel": {"metadataRows": [
                {"metadataParts": [{"text": {"content": text}} for text in texts]},
            ]}},
        }},
        "contentImage": {"thumbnailViewModel": {"overlays": [{
            "thumbnailBottomOverlayViewModel": {"badges": [
                {"thumbnailBadgeViewModel": badge} for badge in (badges or [])
            ]},
        }]}},
    }
    if start is not None:
        item["upcomingEventData"] = {"startTime": str(start)}
    return {"richItemRenderer": {"content": {"lockupViewModel": item}}}


def test_stream_tab_upcoming_live_and_ended():
    now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    page = _tab_page([
        _lockup("eeeeeeeeeee", "Lancement sans mot cle", ["Scheduled for Nov 15, 2026, 8:00 PM"], [
            {"text": "UPCOMING", "badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_UPCOMING"},
        ]),
        _lockup("fffffffffff", "Starship en cours", ["12K watching"], [
            {"text": "LIVE", "badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE"},
        ]),
        _lockup("ggggggggggg", "Starship replay", ["24K", "Streamed 8d ago"], [
            {"text": "56:26", "badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_DEFAULT"},
        ]),
        _lockup("hhhhhhhhhhh", "Hors sujet", ["Streamed 2d ago"], [
            {"text": "10:00", "badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_DEFAULT"},
        ]),
    ])
    videos = {video["video_id"]: video for video in parse_channel_tab(page, "starship", now, streams=True)}
    assert set(videos) == {"eeeeeeeeeee", "fffffffffff", "ggggggggggg"}
    assert videos["eeeeeeeeeee"]["live_status"] == "upcoming"
    assert videos["eeeeeeeeeee"]["scheduled"].startswith("2026-11-15T20:00:00")
    assert videos["fffffffffff"]["live_status"] == "live"
    assert "live_status" in videos["fffffffffff"]
    assert videos["ggggggggggg"]["live_status"] == "ended"
    assert "scheduled" not in videos["ggggggggggg"]
    assert videos["ggggggggggg"]["published"].startswith("2026-10-31T12:00:00")


def test_stream_tab_relative_upcoming_and_videos_tab_stays_plain():
    now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    upcoming = _lockup("iiiiiiiiiii", "Starship premiere", ["Premieres in 3 hours"], [
        {"text": "UPCOMING", "badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_UPCOMING"},
    ])
    plain = _lockup("jjjjjjjjjjj", "Starship montage", ["4 days ago"])
    broken = {"richItemRenderer": {"content": {"lockupViewModel": {
        "contentId": "kkkkkkkkkkk", "metadata": None, "contentImage": {"thumbnailViewModel": {"overlays": "nope"}},
    }}}}
    streams = parse_channel_tab(_tab_page([upcoming, broken]), "starship", now, streams=True)
    assert streams[0]["live_status"] == "upcoming"
    assert streams[0]["scheduled"] == (now + timedelta(hours=3)).isoformat()
    videos = parse_channel_tab(_tab_page([plain, broken]), "starship", now, streams=False)
    assert videos[0]["video_id"] == "jjjjjjjjjjj"
    assert "live_status" not in videos[0]
    assert parse_channel_tab("<html>no data</html>", "starship", now, streams=True) == []
    assert parse_channel_tab("<script>var ytInitialData = {;</script>", "starship", now) == []


def test_video_renderer_start_time_and_merge_keeps_rss_date():
    now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    start = datetime(2026, 11, 20, 18, 30, tzinfo=UTC)
    renderer = {"videoRenderer": {
        "videoId": "lllllllllll",
        "title": {"runs": [{"text": "Compte a rebours"}]},
        "upcomingEventData": {"startTime": str(int(start.timestamp()))},
        "thumbnailOverlays": [{"thumbnailOverlayTimeStatusRenderer": {"style": "UPCOMING", "text": {"simpleText": "UPCOMING"}}}],
    }}
    page = _tab_page([{"richItemRenderer": {"content": renderer}}])
    found = parse_channel_tab(page, "starship", now, streams=True)
    assert found[0]["live_status"] == "upcoming"
    assert found[0]["scheduled"] == start.isoformat()
    rss = {"video_id": "lllllllllll", "title": "Compte a rebours", "url": found[0]["url"], "published": "2026-11-08T12:00:00+00:00", "thumbnail": found[0]["thumbnail"]}
    merged = merge_videos([rss], found)
    assert merged[0]["published"] == rss["published"]
    assert merged[0]["live_status"] == "upcoming"
    assert merged[0]["scheduled"] == start.isoformat()


async def test_channel_tab_failure_keeps_rss_result(hass, caplog):
    c = coordinator(hass)
    with (
        patch(FETCH, AsyncMock(return_value=parse_feed(feed([OLD])))),
        patch(TABS, AsyncMock(side_effect=AttributeError("getaddrinfo"))),
        caplog.at_level(logging.DEBUG),
    ):
        data = await c._async_update_data()
    assert data["video_id"] == OLD[0]
    assert [video["video_id"] for video in data["videos"]] == [OLD[0]]
    assert any("YouTube tabs" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "canonical",
    [
        '<link rel="canonical" href="https://www.youtube.com/channel/UCSUu1lih2RifWkKtDOJdsBA">',
        "<link href='https://www.youtube.com/channel/UCSUu1lih2RifWkKtDOJdsBA' rel='canonical'/>",
    ],
)
def test_canonical_wins_over_recommendations_and_external_id(canonical):
    page = '{"channelId":"UCf0LRbPxIUFuoFfh-Dh9guQ","externalId":"' + CHANNEL + '"}'
    assert parse_channel_id(page + canonical) == "UCSUu1lih2RifWkKtDOJdsBA"


@pytest.mark.parametrize(
    "page",
    [
        '{"channelId":"UCf0LRbPxIUFuoFfh-Dh9guQ"}',
        '<a href="https://www.youtube.com/channel/UCf0LRbPxIUFuoFfh-Dh9guQ">Recommended</a>',
        '<link rel="alternate" href="https://www.youtube.com/channel/UCf0LRbPxIUFuoFfh-Dh9guQ">',
        '<link rel="canonical" href="https://evil.com/channel/UCf0LRbPxIUFuoFfh-Dh9guQ">',
    ],
)
def test_recommendations_are_never_used_as_channel_identity(page):
    with pytest.raises(ValueError):
        parse_channel_id(page)


@pytest.mark.parametrize(
    "handle,channel",
    [
        ("@UFOTINIK", "UCmzE9RqR_6_F6ib_yirMn2Q"),
        ("@NASASpaceflight", "UCSUu1lih2RifWkKtDOJdsBA"),
        ("@StarBaseFR", "UCLg3UuuZ8_gn9Z3XyrzDKhg"),
    ],
)
async def test_suggested_handle_fallback_without_network(hass, handle, channel):
    assert YOUTUBE_KNOWN_HANDLES[handle.casefold()] == channel
    session = async_get_clientsession(hass)
    with patch.object(session, "get", side_effect=TimeoutError) as request:
        for value in (
            handle.upper(),
            "https://www.youtube.com/" + handle + "/videos",
            channel,
        ):
            assert await async_resolve_channel(session, value) == channel
    request.assert_not_called()


async def test_channel_request_has_browser_headers_and_anonymous_consent(
    hass, aioclient_mock
):
    aioclient_mock.get(
        "https://www.youtube.com/@OtherChannel",
        text=f'<link href="https://www.youtube.com/channel/{CHANNEL}" rel="canonical">',
    )
    session = async_get_clientsession(hass)
    with patch.object(session, "get", wraps=session.get) as request:
        assert await async_resolve_channel(session, "@OtherChannel") == CHANNEL
    assert request.call_args.kwargs["headers"] == YOUTUBE_HEADERS
    assert "Mozilla/5.0" in request.call_args.kwargs["headers"]["User-Agent"]
    assert "en" in request.call_args.kwargs["headers"]["Accept-Language"]
    assert request.call_args.kwargs["cookies"] == {"CONSENT": "YES+1", "SOCS": "CAI"}
    assert request.call_args.kwargs["allow_redirects"] is False


async def test_consent_redirect_is_reported_without_following(hass, aioclient_mock):
    aioclient_mock.get(
        "https://www.youtube.com/@OtherChannel",
        status=303,
        headers={"Location": "https://consent.youtube.com/m?continue=example"},
    )
    with pytest.raises(YouTubeConsentError):
        await async_resolve_channel(async_get_clientsession(hass), "@OtherChannel")
    assert aioclient_mock.call_count == 1


async def test_rss_request_has_consent_preferences(hass, aioclient_mock):
    aioclient_mock.get(URL + "?channel_id=" + CHANNEL, text=feed([OLD]))
    session = async_get_clientsession(hass)
    with patch.object(session, "get", wraps=session.get) as request:
        assert await async_fetch_feed(session, CHANNEL, "")
    assert request.call_args.kwargs["headers"] == YOUTUBE_HEADERS
    assert request.call_args.kwargs["cookies"] == YOUTUBE_CONSENT_COOKIES
