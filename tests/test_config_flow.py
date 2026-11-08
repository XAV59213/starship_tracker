"""Tests du config flow Starship Tracker (100 % des étapes)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starship_tracker.const import CONF_API_KEY, DOMAIN
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
    assert result["data"] == {CONF_API_KEY: "abc"}


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
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_API_KEY: "new"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_API_KEY] == "new"
