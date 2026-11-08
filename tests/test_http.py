"""Tests de bout en bout via aioclient_mock (vraies fonctions HTTP)."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.starship_tracker.const import (
    CONF_API_KEY,
    DOMAIN,
    EVENT_LAUNCH_SOON,
    EVENT_LIVE_STARTED,
    NEWS_API_URL,
    SPACEX_ALL_TILES_URL,
    SPACEX_STATS_URL,
    SPACEX_TILES_URL,
)
from custom_components.starship_tracker.diagnostics import async_get_config_entry_diagnostics

MISSION = "https://content.spacex.com/api/spacex-website/missions/"


def _tile(**kw):
    t = {"title": "Starship Flight 15", "link": "starship-flight-15", "vehicle": "Starship",
         "launchDate": None, "launchTime": None, "endDate": None, "launchSite": "Starbase",
         "missionStatus": "upcoming", "isLive": False, "imageDesktop": {"url": "/cms-assets/t.png"}}
    t.update(kw)
    return t


PAST = _tile(title="Starship Flight 14", link="starship-flight-14", missionStatus="final",
             launchDate="2026-09-28", launchTime="23:30:00")
PAGE = {"paragraphs": [{"content": "Launch as soon as Friday, November 13. The 75-minute launch window will open at 4:45 p.m. CT."}],
        "webcasts": [{"streamingVideoType": "x-live-studio", "videoId": "abc"}]}


def _mock(aioclient_mock, upcoming, news_status=200):
    aioclient_mock.clear_requests()
    aioclient_mock.get(SPACEX_TILES_URL, json=upcoming)
    aioclient_mock.get(SPACEX_ALL_TILES_URL, json=[PAST, _tile(vehicle="Falcon 9", link="f9")])
    aioclient_mock.get(MISSION + "starship-flight-15", json=PAGE)
    aioclient_mock.get(MISSION + "starship-flight-14", status=404)
    aioclient_mock.get(SPACEX_STATS_URL, json={"totalLaunches": "715", "totalLandings": 677, "totalReflights": "x"})
    if news_status == 200:
        aioclient_mock.get(NEWS_API_URL, json={"status": "ok", "articles": [{"title": "a", "url": "https://n", "publishedAt": "2026"}]})
    else:
        aioclient_mock.get(NEWS_API_URL, status=news_status, json={"status": "error", "message": "boom"})


@pytest.fixture
async def entry(hass: HomeAssistant, aioclient_mock):
    _mock(aioclient_mock, [_tile()])
    e = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    e.add_to_hass(hass)
    with patch("custom_components.starship_tracker._async_register_card", AsyncMock()):
        assert await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
    return e


async def test_full_http_path(hass: HomeAssistant, entry, aioclient_mock) -> None:
    states = {s.entity_id: s for s in hass.states.async_all()}
    nxt = next(s for s in states.values() if s.attributes.get("link") == "starship-flight-15")
    assert nxt.attributes["date_source"] == "mission_page"
    assert nxt.attributes["launch_time"] == "22:45:00+00:00"
    assert nxt.attributes["mission_videos"][0]["url"] == "https://x.com/i/broadcasts/abc"
    assert any(s.state == "715" for s in states.values())
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert diag["stats"]["data"]["total_reflights"] is None


async def test_button_and_failures(hass: HomeAssistant, entry, aioclient_mock) -> None:
    button = next(s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("button."))
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    aioclient_mock.clear_requests()
    aioclient_mock.get(SPACEX_TILES_URL, status=500)
    aioclient_mock.get(SPACEX_ALL_TILES_URL, status=500)
    aioclient_mock.get(SPACEX_STATS_URL, status=500)
    aioclient_mock.get(NEWS_API_URL, status=500, json={"status": "error"})
    # Le flux upcoming échoue mais le cache /launches complet garde les données.
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    entry.runtime_data.live._all_starship = None
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)


async def test_events(hass: HomeAssistant, entry, aioclient_mock) -> None:
    started, soon = [], []
    hass.bus.async_listen(EVENT_LIVE_STARTED, lambda e: started.append(e))
    hass.bus.async_listen(EVENT_LAUNCH_SOON, lambda e: soon.append(e))
    when = dt_util.utcnow() + timedelta(minutes=30)
    _mock(aioclient_mock, [_tile(isLive=True, launchDate=when.date().isoformat(), launchTime=when.strftime("%H:%M:%S"))])
    await entry.runtime_data.live.async_refresh()
    await hass.async_block_till_done()
    assert len(started) == 1 and len(soon) == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()


async def test_card_registered(hass: HomeAssistant, aioclient_mock) -> None:
    _mock(aioclient_mock, [_tile()])
    e = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    assert hass.data[f"{DOMAIN}_card"] is True
    from custom_components.starship_tracker import _async_register_card
    await _async_register_card(hass)  # deuxième appel : déjà enregistrée
