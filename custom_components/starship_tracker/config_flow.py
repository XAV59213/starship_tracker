"""Config flow de Starship Tracker."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, DOMAIN
from .coordinator import InvalidApiKey, async_fetch_news

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


async def _validate_key(hass: HomeAssistant, api_key: str) -> str | None:
    """Teste la clé NewsAPI ; renvoie un code d'erreur ou None."""
    try:
        await async_fetch_news(async_get_clientsession(hass), api_key)
    except InvalidApiKey:
        return "invalid_auth"
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        return "unknown"
    return None


class StarshipTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Une seule étape : saisie de la clé NewsAPI."""

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

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={"register_url": "https://newsapi.org/register"},
        )


class StarshipTrackerOptionsFlow(OptionsFlow):
    """Modifier la clé NewsAPI sans réinstaller l'intégration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await _validate_key(self.hass, api_key)) is not None:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, CONF_API_KEY: api_key}
                )
                self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={"register_url": "https://newsapi.org/register"},
        )
