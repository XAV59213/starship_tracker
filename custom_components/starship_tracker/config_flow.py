"""Config flow de Starship Tracker."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, CONF_TRANSLATE, CONF_YOUTUBE_FR, CONF_YOUTUBE_EN, CONF_YOUTUBE_KEYWORD, DEFAULT_YOUTUBE_FR, DEFAULT_YOUTUBE_EN, CONF_YOUTUBE_FR2, CONF_YOUTUBE_STARBASE_FR, CONF_YOUTUBE_STARBASE_FILTER, DEFAULT_YOUTUBE_FR2, DOMAIN
from .coordinator import InvalidApiKey, async_fetch_news
from .youtube_coordinator import YouTubeConsentError, async_resolve_channel

KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})
DATA_SCHEMA = KEY_SCHEMA.extend({
    vol.Optional(CONF_YOUTUBE_FR, description={"suggested_value": DEFAULT_YOUTUBE_FR}): str,
    vol.Optional(CONF_YOUTUBE_EN, description={"suggested_value": DEFAULT_YOUTUBE_EN}): str,
    vol.Optional(CONF_YOUTUBE_KEYWORD, description={"suggested_value": "starship"}): str,
    vol.Optional(CONF_YOUTUBE_STARBASE_FR, default=False): bool,
    vol.Optional(CONF_YOUTUBE_FR2, description={"suggested_value": DEFAULT_YOUTUBE_FR2}): str,
    vol.Optional(CONF_YOUTUBE_STARBASE_FILTER, default=False): bool,
})


async def _youtube_options(hass: HomeAssistant, user_input: dict[str, Any], errors: dict[str, str]) -> dict[str, Any]:
    """Resolve once when saving; only store IDs, never fetch arbitrary URLs."""
    result: dict[str, Any] = {}
    for key in (CONF_YOUTUBE_FR, CONF_YOUTUBE_EN, CONF_YOUTUBE_FR2):
        if key == CONF_YOUTUBE_FR2 and not user_input.get(CONF_YOUTUBE_STARBASE_FR, False):
            continue
        if key not in user_input:
            continue
        value = user_input[key].strip()
        if not value:
            result[key] = ""
            continue
        try:
            result[key] = await async_resolve_channel(async_get_clientsession(hass), value)
        except TimeoutError:
            errors[key] = "youtube_resolution_timeout"
        except YouTubeConsentError:
            errors[key] = "youtube_consent"
        except aiohttp.ClientError:
            errors[key] = "youtube_cannot_connect"
        except (ValueError, UnicodeError):
            errors[key] = "invalid_youtube_channel"
    if CONF_YOUTUBE_KEYWORD in user_input:
        result[CONF_YOUTUBE_KEYWORD] = user_input[CONF_YOUTUBE_KEYWORD].strip()
    for key in (CONF_YOUTUBE_STARBASE_FR, CONF_YOUTUBE_STARBASE_FILTER):
        if key in user_input:
            result[key] = bool(user_input[key])
    return result


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
            if (error := await _validate_key(self.hass, api_key)) is not None:
                errors["base"] = error
            else:
                youtube = await _youtube_options(self.hass, user_input, errors)
                if not errors:
                    return self.async_create_entry(title="Starship Tracker", data={CONF_API_KEY: api_key, **youtube})

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input or {}),
            errors=errors,
            description_placeholders={"register_url": "https://newsapi.org/register"},
        )


    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Clé NewsAPI refusée : demande une nouvelle clé."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await _validate_key(self.hass, api_key)) is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={"register_url": "https://newsapi.org/register"},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Changer la clé NewsAPI depuis « Reconfigurer »."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await _validate_key(self.hass, api_key)) is None:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=KEY_SCHEMA,
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
                youtube = await _youtube_options(self.hass, user_input, errors)
                if not errors:
                    return self._save_options(api_key, user_input, youtube)

        translate = self.config_entry.options.get(
            CONF_TRANSLATE, (self.hass.config.language or "").startswith("fr")
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=self.config_entry.data.get(CONF_API_KEY, "")): str,
                vol.Optional(CONF_TRANSLATE, default=translate): bool,
                **{
                    vol.Optional(key, default=self.config_entry.options.get(key, self.config_entry.data.get(key, False))): bool
                    for key in (CONF_YOUTUBE_STARBASE_FR, CONF_YOUTUBE_STARBASE_FILTER)
                },
                **{
                    vol.Optional(key, description={"suggested_value": self.config_entry.options.get(key, self.config_entry.data.get(key, default))}): str
                    for key, default in ((CONF_YOUTUBE_FR, DEFAULT_YOUTUBE_FR), (CONF_YOUTUBE_EN, DEFAULT_YOUTUBE_EN), (CONF_YOUTUBE_FR2, DEFAULT_YOUTUBE_FR2), (CONF_YOUTUBE_KEYWORD, "starship"))
                },
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={"register_url": "https://newsapi.org/register"},
        )

    @callback
    def _save_options(self, api_key: str, user_input: dict[str, Any], youtube: dict[str, Any]) -> ConfigFlowResult:
        """Save resolved channel IDs together with existing options, then reload."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_API_KEY: api_key}
        )
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        return self.async_create_entry(data={
            **self.config_entry.options,
            CONF_TRANSLATE: bool(user_input.get(CONF_TRANSLATE)), **youtube,
        })
