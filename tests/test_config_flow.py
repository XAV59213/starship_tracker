"""Tests du config flow Starship Tracker (100 % des étapes)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starship_tracker.const import CONF_API_KEY, DOMAIN, DEFAULT_YOUTUBE_FR, DEFAULT_YOUTUBE_EN, DEFAULT_YOUTUBE_FR2
from custom_components.starship_tracker.youtube_coordinator import YouTubeConsentError
from custom_components.starship_tracker.coordinator import InvalidApiKey

FETCH = "custom_components.starship_tracker.config_flow.async_fetch_news"
SETUP = "custom_components.starship_tracker.async_setup_entry"


@pytest.fixture
def mock_setup():
    with patch(SETUP, return_value=True) as m:
        yield m


async def test_user_flow_success(hass: HomeAssistant, mock_setup) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: " abc "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "abc", "youtube_starbase_fr": False, "youtube_starbase_filter": False}


@pytest.mark.parametrize(
    ("exc", "error"),
    [(InvalidApiKey, "invalid_auth"), (aiohttp.ClientError, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_user_flow_errors_recover(hass: HomeAssistant, mock_setup, exc, error) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(FETCH, AsyncMock(side_effect=exc)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "bad"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "good"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "x"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, mock_setup) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "old"})
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch(FETCH, AsyncMock(side_effect=InvalidApiKey)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "bad"})
    assert result["errors"] == {"base": "invalid_auth"}
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new"


async def test_reconfigure(hass: HomeAssistant, mock_setup) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "old"})
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with patch(FETCH, AsyncMock(side_effect=TimeoutError)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "x"})
    assert result["errors"] == {"base": "cannot_connect"}
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "new"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_KEY] == "new"


async def test_options_flow(hass: HomeAssistant, mock_setup) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "old"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(FETCH, AsyncMock(side_effect=InvalidApiKey)):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "bad"})
    assert result["errors"] == {"base": "invalid_auth"}
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_API_KEY: "new", "translate_fr": False}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_API_KEY] == "new"
    assert entry.options == {"translate_fr": False, "youtube_starbase_fr": False, "youtube_starbase_filter": False}


@pytest.mark.parametrize(("exc", "error"), [(ValueError, "invalid_youtube_channel"), (TimeoutError, "youtube_resolution_timeout"), (aiohttp.ClientError, "youtube_cannot_connect"), (YouTubeConsentError, "youtube_consent")])
async def test_youtube_user_validation(hass, mock_setup, exc, error):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(FETCH, AsyncMock(return_value=[])), patch("custom_components.starship_tracker.config_flow.async_resolve_channel", AsyncMock(side_effect=exc)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr": "@Example"})
    assert result["errors"] == {"youtube_channel_fr": error}
    channel = "UC" + "a" * 22
    with patch(FETCH, AsyncMock(return_value=[])), patch("custom_components.starship_tracker.config_flow.async_resolve_channel", AsyncMock(return_value=channel)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr": "@Example", "youtube_keyword": " Starship "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["youtube_channel_fr"] == channel
    assert result["data"]["youtube_keyword"] == "Starship"


async def test_youtube_options_clear_and_keep_ids(hass, mock_setup):
    channel = "UC" + "a" * 22
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k", "youtube_channel_fr": channel})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_en": "wrong"})
    assert result["errors"] == {"youtube_channel_en": "invalid_youtube_channel"}
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr": "", "youtube_channel_en": channel, "youtube_keyword": ""})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["youtube_channel_fr"] == ""
    assert entry.options["youtube_channel_en"] == channel
    assert entry.options["youtube_keyword"] == ""


async def test_youtube_suggested_defaults(hass, mock_setup):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    suggestions = {key.schema: key.description.get("suggested_value") for key in result["data_schema"].schema if key.description}
    assert suggestions["youtube_channel_fr"] == DEFAULT_YOUTUBE_FR
    assert suggestions["youtube_channel_en"] == DEFAULT_YOUTUBE_EN
    assert suggestions["youtube_keyword"] == "starship"


async def test_starbase_optional_and_not_resolved_when_disabled(hass, mock_setup):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    suggestions = {key.schema: key.description.get("suggested_value") for key in result["data_schema"].schema if key.description}
    assert suggestions["youtube_channel_fr2"] == DEFAULT_YOUTUBE_FR2
    with patch(FETCH, AsyncMock(return_value=[])), patch("custom_components.starship_tracker.config_flow.async_resolve_channel", AsyncMock()) as resolve:
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr2": "@StarBaseFR", "youtube_starbase_fr": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    resolve.assert_not_called()
    assert entry.options["youtube_starbase_fr"] is False
    assert "youtube_channel_fr2" not in entry.options


async def test_starbase_enable_validation_and_clear(hass, mock_setup):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(FETCH, AsyncMock(return_value=[])), patch("custom_components.starship_tracker.config_flow.async_resolve_channel", AsyncMock(side_effect=ValueError)):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr2": "@Missing", "youtube_starbase_fr": True})
    assert result["errors"] == {"youtube_channel_fr2": "invalid_youtube_channel"}
    channel = "UC" + "c" * 22
    with patch(FETCH, AsyncMock(return_value=[])), patch("custom_components.starship_tracker.config_flow.async_resolve_channel", AsyncMock(return_value=channel)):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr2": "@StarBaseFR", "youtube_starbase_fr": True, "youtube_starbase_filter": False})
    assert entry.options["youtube_channel_fr2"] == channel
    assert entry.options["youtube_starbase_fr"] is True
    assert entry.options["youtube_starbase_filter"] is False
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(FETCH, AsyncMock(return_value=[])):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "k", "youtube_channel_fr2": "", "youtube_starbase_fr": True})
    assert entry.options["youtube_channel_fr2"] == ""


async def test_channel_ids_save_without_rss_or_resolution_request(hass, mock_setup):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_API_KEY: 'k'})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(FETCH, AsyncMock(return_value=[])), patch('custom_components.starship_tracker.youtube_coordinator.async_fetch_feed', AsyncMock(side_effect=TimeoutError)) as rss, patch('aiohttp.ClientSession.get', side_effect=TimeoutError) as request:
        result = await hass.config_entries.options.async_configure(result['flow_id'], {
            CONF_API_KEY: 'k', 'youtube_channel_fr': DEFAULT_YOUTUBE_FR,
            'youtube_channel_en': DEFAULT_YOUTUBE_EN, 'youtube_starbase_fr': True,
            'youtube_channel_fr2': DEFAULT_YOUTUBE_FR2,
        })
    assert result['type'] is FlowResultType.CREATE_ENTRY
    assert entry.options['youtube_channel_fr'] == DEFAULT_YOUTUBE_FR
    assert entry.options['youtube_channel_en'] == DEFAULT_YOUTUBE_EN
    assert entry.options['youtube_channel_fr2'] == DEFAULT_YOUTUBE_FR2
    rss.assert_not_called()
    request.assert_not_called()
