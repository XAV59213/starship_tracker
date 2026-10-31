"""Constantes de l'intégration Starship Tracker."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "starship_tracker"

# Flux en direct (page véhicule Starship sur spacex.com)
LIVE_URL: Final = "https://www.spacex.com/vehicles/starship"

# NewsAPI : la clé est saisie par l'utilisateur via le config flow
CONF_API_KEY: Final = "api_key"
NEWS_API_URL: Final = "https://newsapi.org/v2/everything"
NEWS_QUERY: Final = "starship spacex"
NEWS_LIMIT: Final = 5

SCAN_INTERVAL_NEWS: Final = timedelta(minutes=30)

# Détection du live Starship via l'API publique du site spacex.com
SPACEX_TILES_URL: Final = "https://content.spacex.com/api/spacex-website/launches-page-tiles/upcoming"
SPACEX_LAUNCH_URL: Final = "https://www.spacex.com/launches/{link}"
TRACKED_VEHICLE: Final = "Starship"
SCAN_INTERVAL_LIVE: Final = timedelta(minutes=5)
EVENT_LIVE_STARTED: Final = "starship_tracker_live_started"
EVENT_LIVE_ENDED: Final = "starship_tracker_live_ended"
EVENT_LAUNCH_SOON: Final = "starship_tracker_launch_soon"
LAUNCH_SOON_WINDOW: Final = timedelta(hours=1)
# Flux complet de la page https://www.spacex.com/launches (passés + à venir, ~3 Mo)
SPACEX_ALL_TILES_URL: Final = "https://content.spacex.com/api/spacex-website/launches-page-tiles"
SCAN_INTERVAL_ALL_LAUNCHES: Final = timedelta(hours=6)
# Compteurs globaux SpaceX affichés sur https://www.spacex.com/launches
SPACEX_STATS_URL: Final = "https://content.spacex.com/api/spacex-website/launches-page-stats"
SCAN_INTERVAL_STATS: Final = timedelta(hours=1)
