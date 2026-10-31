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
