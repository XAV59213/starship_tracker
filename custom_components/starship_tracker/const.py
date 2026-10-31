"""Constantes de l'intégration Starship Tracker."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "starship_tracker"

# Flux en direct (chaîne YouTube SpaceX)
LIVE_URL: Final = "https://www.youtube.com/@SpaceX/live"

# NewsAPI : la clé est saisie par l'utilisateur via le config flow
CONF_API_KEY: Final = "api_key"
NEWS_API_URL: Final = "https://newsapi.org/v2/everything"
NEWS_QUERY: Final = "starship spacex"
NEWS_LIMIT: Final = 5

SCAN_INTERVAL_NEWS: Final = timedelta(minutes=30)
