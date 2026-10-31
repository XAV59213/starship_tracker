# starship_tracker

[![Downloads](https://img.shields.io/github/downloads/XAV59213/starship_tracker/total.svg?label=Downloads)](https://github.com/XAV59213/starship_tracker/releases)

Intégration Home Assistant (HACS) qui expose :

- **Starship en direct** (*Starship live*, `binary_sensor`) : `on` quand une mission Starship est en direct sur spacex.com, `off` sinon. Attributs : `url` (page de la mission, où se trouve le live), `vehicle_url`, `mission`, `mission_status`, `launch_date`, `launch_site`, `last_check`. Vérifié toutes les 5 minutes, sans clé.
- **Prochaine mission Starship** (*Next Starship mission*, `sensor`) : état = nom de la prochaine mission Starship annoncée (vide/`unknown` s'il n'y en a pas). Attributs : `mission`, `launch_date`, `launch_time`, `launch_site`, `mission_status`, `vehicle`, `mission_type`, `url`, `last_check`. Même flux et même rafraîchissement (5 min) que le binary_sensor live.
- **Compte à rebours lancement Starship** (*Starship launch countdown*, `sensor`, `device_class: timestamp`) : état = date/heure UTC du prochain lancement Starship (HA affiche « dans 3 jours »…). Attributs : `mission`, `launch_site`, `url`, `seconds_remaining`, `countdown` (ex. `3d 04h 12m`), `launched`, `last_check`. `unknown` si aucun lancement annoncé.
- **Statut mission Starship** (*Starship mission status*, `sensor`) : `live` pendant un direct, sinon le statut SpaceX de la prochaine mission (`missionStatus`, ex. *Upcoming*, *Scrubbed*). Attributs : `mission`, `is_live`, `launch_date`, `url`, `last_check`.
- **Dernier vol Starship** (*Last Starship flight*, `sensor`) : nom du dernier vol Starship terminé d'après <https://www.spacex.com/launches> (ex. *Starship Flight 14*). Attributs : `launch_date`, `launch_time`, `launch_time_utc`, `launch_site`, `return_site`, `mission_status`, `url`.
- **Missions Starship** (*Starship missions*, `sensor`) : nombre de vols Starship listés sur <https://www.spacex.com/launches>. Attributs : `past` (10 derniers vols), `upcoming`, `past_count`, `upcoming_count` — chaque mission : `mission`, `launch_date`, `launch_site`, `mission_status`, `url`, `video_url` (webcast live / replay cliquable), `is_live`.
- **Page du vaisseau Starship** (*Starship vehicle page*) : lien vers <https://www.spacex.com/vehicles/starship>, attribut `url`.
- **Actualités Starship** (*Starship news*) : nombre d'articles récents, avec les 5 dernières actualités Starship (`title`, `link`, `published`) dans l'attribut `news`. Rafraîchi toutes les 30 minutes via [NewsAPI](https://newsapi.org).

- **Rafraîchir** (*Refresh*, `button`, catégorie diagnostic) : force la mise à jour immédiate du live SpaceX et des actualités (utilisable en automatisation via `button.press`).

Version actuelle : **1.10.0**. Nécessite Home Assistant **2024.11.0** ou plus récent. Interface traduite en anglais et en français.

## Installation (HACS)

1. HACS → Intégrations → menu ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/XAV59213/starship_tracker` (catégorie *Intégration*).
2. Installer **Starship Tracker**, puis redémarrer Home Assistant.

## Configuration

1. Créer une clé gratuite sur <https://newsapi.org/register>.
2. Paramètres → Appareils et services → *Ajouter une intégration* → **Starship Tracker**.
3. Coller la clé NewsAPI. Pour la changer plus tard : *Paramètres → Appareils et services → Starship Tracker → Configurer* (la clé est testée puis l’intégration rechargée). Elle est validée puis stockée dans la config entry Home Assistant (jamais dans le code).

## ⚠️ Sécurité

Les versions ≤ 1.0.3 contenaient une clé NewsAPI en clair dans `const.py`. Cette clé est publique dans l'historique Git : **elle doit être révoquée/régénérée** sur le compte NewsAPI. Depuis la 1.1.0, aucune clé n'est livrée avec l'intégration.

## Détection du live

Choix d'un `binary_sensor` (état on/off idiomatique dans HA).

La source est le site officiel SpaceX (<https://www.spacex.com/vehicles/starship> et ses pages de lancement). L'intégration lit le flux JSON public qui alimente la page des lancements du site (`content.spacex.com/api/spacex-website/launches-page-tiles/upcoming`), garde les missions dont `vehicle` vaut `Starship`, et passe à `on` si l'une d'elles a `isLive: true`. Sans live, les attributs décrivent la prochaine mission Starship annoncée, s'il y en a une.

### Sources (1.9.0)

1. Flux principal, toutes les 5 min : `launches-page-tiles/upcoming` (live + prochaine mission).
2. Flux complet de la page <https://www.spacex.com/launches> (`content.spacex.com/api/spacex-website/launches-page-tiles`, ~3 Mo, tous les vols passés et à venir), lu toutes les 6 h et mis en cache : dernier vol Starship, missions Starship à venir/en cours absentes du flux principal.
3. Repli : si le flux principal échoue, le flux complet est relu immédiatement ; si les deux échouent, les entités passent indisponibles.

## Notifications (événements)

Quand le live Starship commence, l'intégration déclenche l'événement Home Assistant `starship_tracker_live_started`, et `starship_tracker_live_ended` quand il se termine. Données : `mission`, `url`, `launch_date`, `launch_site`, `mission_status`. `starship_tracker_launch_soon` est émis une seule fois par mission/date quand le lancement est à moins d'1 h (T-1h, précision 5 min). Données : `mission`, `url`, `launch_time`, `minutes_remaining`, `launch_site`, `mission_status`. Aucun événement live n'est émis au démarrage de Home Assistant, seulement lors d'un changement d'état.

Exemple d'automatisation (remplacer `notify.mobile_app_mon_telephone` par votre service de notification) :

```yaml
automation:
  - alias: "Starship en direct"
    triggers:
      - trigger: event
        event_type: starship_tracker_live_started
    actions:
      - action: notify.mobile_app_mon_telephone
        data:
          title: "🚀 Starship en direct"
          message: "{{ trigger.event.data.mission }} est en live sur spacex.com"
          data:
            url: "{{ trigger.event.data.url }}"
            clickAction: "{{ trigger.event.data.url }}"
```

Variante sans événement : déclencher sur l'état du binary_sensor (`trigger: state`, `to: "on"`).

## Diagnostics & robustesse

- *Paramètres → Appareils et services → Starship Tracker → ⋮ → Télécharger les diagnostics* : état du live et des actualités, clé NewsAPI masquée (`**REDACTED**`).
- Si NewsAPI échoue au démarrage (clé invalide, quota, réseau), l'intégration démarre quand même : le live et la prochaine mission fonctionnent, seul le sensor actualités est indisponible jusqu'au prochain rafraîchissement.

## Limites

- Le flux JSON est interne au site spacex.com, pas une API documentée : il peut changer sans préavis.
- Le statut dépend de la mise à jour du flag `isLive` par SpaceX, et du délai de 5 minutes entre deux vérifications.

## Brand / Icônes

Les icônes et logos de l'intégration sont dans `custom_components/starship_tracker/brand/`
(`icon.png`, `icon@2x.png`, `dark_icon*.png`, `logo*.png`, `dark_logo*.png`, PNG transparents).
Home Assistant (2026.3+) les utilise directement pour les intégrations personnalisées.

Integration icons and logos live in `custom_components/starship_tracker/brand/` (transparent PNGs),
used directly by Home Assistant for custom integrations.

## Carte Starship Tracker (custom card)

**1.10.0** : la carte affiche les prochaines missions et les derniers vols Starship avec un lien **▶ Vidéo** cliquable (options `show_missions: true`, `missions_count: 3`).

Depuis la 1.8.0, une carte Lovelace personnalisée est **livrée avec l'intégration** : aucune installation HACS séparée, aucune ressource à ajouter. Elle est chargée automatiquement dès que l'intégration est configurée (vider le cache du navigateur / de l'app après la mise à jour si elle n'apparaît pas).

1. Mettre à jour Starship Tracker en 1.8.0 via HACS, redémarrer Home Assistant.
2. Tableau de bord → Modifier → Ajouter une carte → chercher **Starship Tracker** (ou carte manuelle) :

```yaml
type: custom:starship-tracker-card
```

Affiche la prochaine mission façon fiche (titre « Mission (SpaceX) », fournisseur, véhicule, rampe, emplacement, date cible, compte à rebours en direct, tags), le statut live et les 5 dernières actualités. Textes en français ou anglais selon la langue de HA. Les entités sont détectées automatiquement ; options facultatives :

```yaml
type: custom:starship-tracker-card
show_news: true      # afficher les actualités
news_count: 5        # nombre d'actualités
# entités à forcer si besoin : live, next, countdown, status, news
# next: sensor.starship_tracker_prochaine_mission_starship
```

*EN* — Since 1.8.0 a custom card ships **with the integration** (no separate HACS install, no resource to add). Add a card of type `custom:starship-tracker-card`; entities are auto-detected.

## Carte Lovelace / Lovelace card (cartes natives)

Exemple prêt à coller (Tableau de bord → Modifier → Ajouter une carte → Manuel), aussi dans [`docs/lovelace-card.yaml`](docs/lovelace-card.yaml).
Met en avant la **prochaine mission Starship** façon fiche mission (titre « Mission (SpaceX) », Provider / Vehicle / Launch Pad / Location / Target Date / Countdown / Tags), puis le statut live et les 5 dernières actualités. Cartes natives uniquement.

Ready-to-paste example (Dashboard → Edit → Add card → Manual), also in `docs/lovelace-card.yaml`. Native cards only.

> Les `entity_id` ci-dessous correspondent à une installation en anglais. En français ils peuvent être par ex. `sensor.starship_tracker_prochaine_mission_starship` — vérifiez dans Paramètres → Entités.

```yaml
# Starship Tracker — carte Lovelace / Lovelace card
# Style « fiche mission » (titre « Mission (Provider) » + lignes), cartes natives uniquement.
# Adaptez les entity_id si votre HA est en français (voir README).
type: vertical-stack
cards:
  # 1) Prochaine mission Starship (mise en avant)
  - type: markdown
    content: >
      {% set m = 'sensor.starship_tracker_next_starship_mission' %}
      {% set c = 'sensor.starship_tracker_starship_launch_countdown' %}
      {% if states(m) not in ['unknown', 'unavailable', ''] %}
      ## {{ states(m) }} (SpaceX)

      **Provider:** SpaceX<br>
      **Vehicle:** {{ state_attr(m, 'vehicle') or 'Starship' }}<br>
      **Launch Pad:** {{ state_attr(m, 'launch_site') or 'Starbase' }}<br>
      **Location:** Starbase, Texas, United States<br>
      **Target Date:** {{ state_attr(m, 'launch_date') or 'TBD' }} {{ state_attr(m, 'launch_time') or '' }}<br>
      **Countdown:** {{ state_attr(c, 'countdown') or '—' }}{% if state_attr(c, 'launched') %} (lancé / launched){% endif %}<br>
      **Tags:** {{ state_attr(m, 'mission_type') or 'Test flight' }} | {{ state_attr(m, 'mission_status') or 'Upcoming' }} |

      [Détails / Details]({{ state_attr(m, 'url') }})
      {% else %}
      ## TBD (SpaceX)

      **Provider:** SpaceX<br>
      **Vehicle:** Starship<br>
      **Launch Pad:** Starbase<br>
      **Location:** Starbase, Texas, United States<br>
      **Target Date:** TBD<br>
      **Tags:** Aucune mission annoncée / No mission announced |
      {% endif %}

  # 2) Statut live
  - type: markdown
    content: >
      {% if is_state('binary_sensor.starship_tracker_starship_live', 'on') %}
      🔴 **EN DIRECT / LIVE** — [Regarder / Watch]({{ state_attr('sensor.starship_tracker_next_starship_mission', 'url') or 'https://www.spacex.com/vehicles/starship' }})
      {% else %}
      ⚪ Pas de live en cours / No live stream — [spacex.com/vehicles/starship](https://www.spacex.com/vehicles/starship)
      {% endif %}

  # 3) Actualités
  - type: markdown
    title: Actualités / News
    content: |
      {% set news = state_attr('sensor.starship_tracker_starship_news', 'news') or [] %}
      {% for a in news[:5] %}
      - [{{ a.title }}]({{ a.link }})
      {% else %}
      Aucune actualité / No news
      {% endfor %}
```

## English

Home Assistant (HACS) integration — **version 1.10.0**, requires Home Assistant **2024.11.0+**, UI in English and French.

- **Starship live** (`binary_sensor`): `on` while a Starship mission is live on spacex.com (checked every 5 min, no key).
- **Next Starship mission** (`sensor`): name of the next announced Starship mission; attributes `launch_date`, `launch_time`, `launch_site`, `mission_status`, `vehicle`, `mission_type`, `url`.
- **Starship launch countdown** (`sensor`, `device_class: timestamp`): next launch time; attributes `seconds_remaining`, `countdown`, `launched`.
- **Starship vehicle page** (`sensor`): link to <https://www.spacex.com/vehicles/starship>.
- **Refresh** (`button`): forces an immediate update of SpaceX live data and news.
- Diagnostics download (NewsAPI key redacted); if NewsAPI fails at startup, live sensors keep working.
- **Starship news** (`sensor`): latest 5 Starship articles via [NewsAPI](https://newsapi.org) (refreshed every 30 min).
- **Last Starship flight** (`sensor`): last completed Starship flight from <https://www.spacex.com/launches> (full feed, cached 6 h); the upcoming feed stays primary, the full feed is the fallback.
- **Starship missions** (`sensor`): number of Starship flights on <https://www.spacex.com/launches>; attributes `past` (latest 10), `upcoming`, `past_count`, `upcoming_count` — each with `mission`, `launch_date`, `launch_site`, `mission_status`, `url`, `video_url` (clickable live / replay webcast), `is_live`.
- **Starship mission status** (`sensor`): `live` during a stream, otherwise SpaceX `missionStatus` of the next mission.
- Events `starship_tracker_live_started` / `starship_tracker_live_ended`, and `starship_tracker_launch_soon` (once, within 1 h of launch).
- Install: HACS → custom repository `https://github.com/XAV59213/starship_tracker` (Integration), then add **Starship Tracker** and paste a NewsAPI key (changeable via *Configure*).
- Custom card bundled with the integration: `type: custom:starship-tracker-card` — shows upcoming missions and latest flights with a clickable **▶ Video** link (`show_missions`, `missions_count`).
- Example native Lovelace card: `docs/lovelace-card.yaml` (see section above). Brand icons: `custom_components/starship_tracker/brand/`.
