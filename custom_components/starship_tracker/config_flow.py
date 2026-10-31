"""Config flow de Starship Tracker."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, DOMAIN
from .coordinator import InvalidApiKey, async_fetch_news

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class StarshipTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Une seule étape : saisie de la clé NewsAPI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await async_fetch_news(async_get_clientsession(self.hass), api_key)
            except InvalidApiKey:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Starship Tracker", data={CONF_API_KEY: api_key})

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)
