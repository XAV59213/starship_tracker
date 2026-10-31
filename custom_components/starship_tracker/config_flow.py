"""Config flow de Starship Tracker."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, CONF_X_BEARER_TOKEN, DOMAIN
from .coordinator import InvalidApiKey, async_fetch_news
from .live_coordinator import InvalidXToken, async_fetch_live

PLACEHOLDERS = {
    "register_url": "https://newsapi.org/register",
    "x_dev_url": "https://developer.x.com",
}


async def _validate_x(hass: HomeAssistant, token: str | None, errors: dict[str, str]) -> None:
    if not token:
        return
    try:
        await async_fetch_live(async_get_clientsession(hass), token)
    except InvalidXToken:
        errors[CONF_X_BEARER_TOKEN] = "invalid_x_token"
    except (aiohttp.ClientError, TimeoutError):
        errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        errors["base"] = "unknown"


class StarshipTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Clé NewsAPI (obligatoire) + bearer token X (optionnel, détection live)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StarshipTrackerOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            x_token = (user_input.get(CONF_X_BEARER_TOKEN) or "").strip() or None
            try:
                await async_fetch_news(async_get_clientsession(self.hass), api_key)
            except InvalidApiKey:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            if not errors:
                await _validate_x(self.hass, x_token, errors)
            if not errors:
                data = {CONF_API_KEY: api_key}
                if x_token:
                    data[CONF_X_BEARER_TOKEN] = x_token
                return self.async_create_entry(title="Starship Tracker", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_X_BEARER_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )


class StarshipTrackerOptionsFlow(OptionsFlow):
    """Ajout / changement du bearer token X après installation."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            x_token = (user_input.get(CONF_X_BEARER_TOKEN) or "").strip()
            await _validate_x(self.hass, x_token or None, errors)
            if not errors:
                return self.async_create_entry(data={CONF_X_BEARER_TOKEN: x_token})

        current = self.config_entry.options.get(
            CONF_X_BEARER_TOKEN, self.config_entry.data.get(CONF_X_BEARER_TOKEN, "")
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_X_BEARER_TOKEN, description={"suggested_value": current}): str}
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )
