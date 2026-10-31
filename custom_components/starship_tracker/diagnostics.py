"""Diagnostics Starship Tracker (clé NewsAPI masquée)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import StarshipConfigEntry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StarshipConfigEntry
) -> dict[str, Any]:
    """Renvoie l'état de l'intégration pour le débogage."""
    data = entry.runtime_data
    live = data.live.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "live": {
            "last_update_success": data.live.last_update_success,
            "status": asdict(live) if live else None,
        },
        "news": {
            "last_update_success": data.news.last_update_success,
            "last_exception": repr(data.news.last_exception) if data.news.last_exception else None,
            "articles": data.news.data,
        },
    }
