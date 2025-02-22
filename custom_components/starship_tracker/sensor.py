import feedparser
import requests
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, RSS_URL, LIVE_URL

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure les entités sensor."""
    async_add_entities([
        StarshipLiveSensor(hass, config_entry),
        StarshipNewsSensor(hass, config_entry),
    ])

class StarshipLiveSensor(SensorEntity):
    """Entité pour le flux en direct du Starship."""
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self._attr_unique_id = f"{config_entry.entry_id}_starship_live"
        self._attr_name = "Starship Live Stream"
        self._attr_icon = "mdi:rocket-launch"
        self._state = "unknown"
        self._attr_extra_state_attributes = {"url": LIVE_URL}

    @property
    def state(self):
        return self._state

    async def async_update(self) -> None:
        """Mise à jour du sensor (statique pour l'instant)."""
        # Pour un vrai live, on pourrait vérifier via l'API YouTube si un stream est actif.
        self._state = "Check Live Stream"

class StarshipNewsSensor(SensorEntity):
    """Entité pour les 5 dernières actualités du Starship."""
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self._attr_unique_id = f"{config_entry.entry_id}_starship_news"
        self._attr_name = "Starship News"
        self._attr_icon = "mdi:newspaper"
        self._state = "unknown"
        self._attr_extra_state_attributes = {"news": []}

    @property
    def state(self):
        return self._state

    async def async_update(self) -> None:
        """Récupère les 5 dernières actualités."""
        try:
            # Récupération du flux RSS
            feed = await hass.async_add_executor_job(feedparser.parse, RSS_URL)
            news_list = [
                {"title": entry.title, "link": entry.link, "published": entry.published}
                for entry in feed.entries
                if "starship" in entry.title.lower() or "starship" in entry.summary.lower()
            ][:5]  # Limite à 5 résultats
            self._attr_extra_state_attributes["news"] = news_list
            self._state = f"{len(news_list)} news items"
        except Exception as e:
            self._state = "error"
            self._attr_extra_state_attributes["news"] = []
