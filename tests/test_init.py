"""Tests de setup / unload / indisponibilité / réauth."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starship_tracker.const import CONF_API_KEY, DOMAIN
from custom_components.starship_tracker.coordinator import InvalidApiKey

P = "custom_components.starship_tracker"
TILE = {
    "title": "Starship Flight 15", "link": "starship-flight-15", "vehicle": "Starship",
    "launchDate": "2026-11-13", "launchTime": "22:45:00", "launchSite": "Starbase, Texas",
    "missionStatus": "upcoming", "isLive": False,
}
PAGE = {
    "paragraphs": [{"content": "Flight 15 is go."}],
    "imageDesktop": {"url": "/cms-assets/f15.png"},
    "infographicDesktop": {"url": "/cms-assets/traj.jpg"},
    "postLaunchTimeline": {"timelineEntries": [{"time": "00:00:00", "description": "Liftoff"}]},
}


def _patches(tiles=None, news=None):
    return (
        patch(f"{P}._async_register_card", AsyncMock()),
        patch(f"{P}.live_coordinator.async_fetch_tiles", AsyncMock(return_value=[TILE]) if tiles is None else tiles),
        patch(f"{P}.live_coordinator.async_fetch_mission", AsyncMock(return_value=PAGE)),
        patch(f"{P}.coordinator.async_fetch_news", news or AsyncMock(return_value=[{"title": "a", "link": "https://x", "published": None}])),
        patch(f"{P}.stats_coordinator.SpaceXStatsCoordinator._async_update_data", AsyncMock(return_value={"total_launches": 1, "total_landings": 2, "total_reflights": 3})),
    )


async def _setup(hass, entry, patches):
    for p in patches:
        p.start()
    try:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()


async def test_setup_unload(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    await _setup(hass, entry, _patches())
    assert entry.state is ConfigEntryState.LOADED
    states = [s for s in hass.states.async_all() if s.entity_id.startswith(("sensor.", "binary_sensor.", "button."))]
    assert len(states) >= 10
    nxt = next(s for s in states if s.attributes.get("link") == "starship-flight-15")
    assert nxt.attributes["mission_image"] == "https://content.spacex.com/cms-assets/f15.png"
    assert nxt.attributes["mission_timeline"] == [["00:00:00", "Liftoff"]]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_spacex_down(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    await _setup(hass, entry, _patches(tiles=AsyncMock(side_effect=UpdateFailed("down"))))
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_key_starts_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    await _setup(hass, entry, _patches(news=AsyncMock(side_effect=InvalidApiKey)))
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_youtube_sensors_and_independent_failure(hass: HomeAssistant) -> None:
    channel = "UC" + "a" * 22
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"}, options={
        "youtube_channel_fr": channel, "youtube_channel_en": "UC" + "b" * 22,
    })
    entry.add_to_hass(hass)
    video = {"video_id": "aaaaaaaaaaa", "title": "Starship " + "x" * 300,
             "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "published": "2026-11-08T10:00:00+00:00",
             "thumbnail": "https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg"}
    with patch(f"{P}.youtube_coordinator.async_fetch_feed", AsyncMock(side_effect=[[video], TimeoutError])):
        await _setup(hass, entry, _patches())
    assert entry.state is ConfigEntryState.LOADED
    fr = hass.states.get('sensor.starship_tracker_youtube_fr')
    en = hass.states.get('sensor.starship_tracker_youtube_en')
    assert fr is not None
    assert fr.state == video['title'][:255]
    assert fr.attributes['title'] == video['title']
    assert fr.attributes['channel'] == channel
    assert en is not None and en.state == 'unavailable'
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("use_filter", [False, True])
async def test_starbase_sensor_filter_and_fr_event(hass, use_filter):
    channel = "UC" + "c" * 22
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"}, options={
        "youtube_channel_fr2": channel, "youtube_starbase_fr": True,
        "youtube_starbase_filter": use_filter, "youtube_keyword": "starship",
    })
    entry.add_to_hass(hass)
    video = {"video_id": "ccccccccccc", "title": "Le suivi hebdomadaire du projet",
             "url": "https://www.youtube.com/watch?v=ccccccccccc", "published": "2026-11-08T10:00:00+00:00",
             "thumbnail": "https://i.ytimg.com/vi/ccccccccccc/hqdefault.jpg"}
    with patch(f"{P}.youtube_coordinator.async_fetch_feed", AsyncMock(return_value=[video])) as fetch:
        await _setup(hass, entry, _patches())
    assert entry.state is ConfigEntryState.LOADED
    assert fetch.call_count == 1
    assert fetch.call_args.args[1:] == (channel, 'starship' if use_filter else '')
    sensor = hass.states.get('sensor.starship_tracker_youtube_fr_starbase')
    assert sensor is not None and sensor.state == video['title']
    assert hass.states.get('sensor.starship_tracker_youtube_fr') is None
    assert hass.states.get('sensor.starship_tracker_youtube_en') is None
    events = []
    hass.bus.async_listen('starship_tracker_youtube_video', events.append)
    coordinator = entry.runtime_data.youtube['fr_starbase']
    with patch(f"{P}.youtube_coordinator.async_fetch_feed", AsyncMock(return_value=[{**video, 'video_id': 'ddddddddddd'}])):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data['language'] == 'fr'
    assert events[0].data['channel'] == channel
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_starbase_disabled_does_not_poll(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"}, options={
        'youtube_channel_fr2': 'UC' + 'c' * 22, 'youtube_starbase_fr': False,
    })
    entry.add_to_hass(hass)
    with patch(f"{P}.youtube_coordinator.async_fetch_feed", AsyncMock()) as fetch:
        await _setup(hass, entry, _patches())
    fetch.assert_not_called()
    assert hass.states.get('sensor.starship_tracker_youtube_fr_starbase') is None
    assert await hass.config_entries.async_unload(entry.entry_id)
