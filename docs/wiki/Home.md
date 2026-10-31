# Starship Tracker — Wiki

**FR** — Intégration Home Assistant (HACS) pour suivre Starship : live spacex.com, prochaine mission, compte à rebours, actualités. Version **1.10.0**, HA ≥ 2024.11.0.
**EN** — Home Assistant (HACS) integration to follow Starship: spacex.com live, next mission, launch countdown, news. Version **1.10.0**, HA ≥ 2024.11.0.

| Entité / Entity (EN) | FR | Type |
|---|---|---|
| Starship live | Starship en direct | binary_sensor |
| Next Starship mission | Prochaine mission Starship | sensor |
| Starship launch countdown | Compte à rebours lancement Starship | sensor (timestamp) |
| Starship vehicle page | Page du vaisseau Starship | sensor |
| Starship news | Actualités Starship | sensor |
| Starship mission status | Statut mission Starship | sensor |
| Last Starship flight | Dernier vol Starship | sensor |
| Starship missions | Missions Starship | sensor (past / upcoming, video_url) |
| Refresh | Rafraîchir | button |

- Installation & configuration : voir / see [README](https://github.com/XAV59213/starship_tracker#readme)
- Carte personnalisée / Custom card : `type: custom:starship-tracker-card` (livrée avec l'intégration / bundled)
- Carte Lovelace / Lovelace card : [`docs/lovelace-card.yaml`](https://github.com/XAV59213/starship_tracker/blob/main/docs/lovelace-card.yaml)
- Événements / Events : `starship_tracker_live_started`, `starship_tracker_live_ended`, `starship_tracker_launch_soon` (T-1h)
- Releases : <https://github.com/XAV59213/starship_tracker/releases>
