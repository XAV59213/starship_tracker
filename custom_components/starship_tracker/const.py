"""Constantes de l'intégration Starship Tracker."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "starship_tracker"

# Flux en direct (compte X SpaceX)
LIVE_URL: Final = "https://x.com/SpaceX"

# NewsAPI : la clé est saisie par l'utilisateur via le config flow
CONF_API_KEY: Final = "api_key"
NEWS_API_URL: Final = "https://newsapi.org/v2/everything"
NEWS_QUERY: Final = "starship spacex"
NEWS_LIMIT: Final = 5

SCAN_INTERVAL_NEWS: Final = timedelta(minutes=30)

# Détection du live SpaceX sur X (API X v2, bearer token optionnel)
CONF_X_BEARER_TOKEN: Final = "x_bearer_token"
X_ACCOUNT: Final = "SpaceX"
X_PROFILE_URL: Final = "https://x.com/SpaceX"
X_SEARCH_URL: Final = "https://api.x.com/2/tweets/search/recent"
X_SEARCH_QUERY: Final = 'from:SpaceX url:"x.com/i/broadcasts" -is:retweet -is:reply'
# Un post de diffusion plus récent que cette fenêtre = live en cours
LIVE_WINDOW: Final = timedelta(hours=2)
SCAN_INTERVAL_LIVE: Final = timedelta(minutes=10)
