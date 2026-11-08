"""Public channel resolution, safe Atom parsing and restart-proof alerts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starship_tracker.const import DOMAIN
from custom_components.starship_tracker.youtube_coordinator import (
    YouTubeCoordinator,
    async_fetch_feed,
    async_resolve_channel,
    parse_channel_id,
    parse_feed,
)

CHANNEL = "UC" + "a" * 22
OTHER_CHANNEL = "UC" + "b" * 22
URL = "https://www.youtube.com/feeds/videos.xml"
FETCH = "custom_components.starship_tracker.youtube_coordinator.async_fetch_feed"


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
        f'{{"channelId":"{CHANNEL}"}}',
        f'{{"externalId": "{CHANNEL}"}}',
        f'<link href="https://www.youtube.com/channel/{CHANNEL}">',
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
            "https://www.youtube.com/c/Example", text=f'{{"channelId":"{CHANNEL}"}}'
        )
        aioclient_mock.get(
            "https://www.youtube.com/user/Example", text=f'{{"channelId":"{CHANNEL}"}}'
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
