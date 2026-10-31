# starship_tracker

[![Downloads](https://img.shields.io/github/downloads/XAV59213/starship_tracker/total.svg?label=Downloads)](https://github.com/XAV59213/starship_tracker/releases)

Intégration Home Assistant (HACS) qui expose :

- **Starship en direct** (*Starship live*, `binary_sensor`) : `on` quand une mission Starship est en direct sur spacex.com, `off` sinon. Attributs : `url` (page de la mission, où se trouve le live), `vehicle_url`, `mission`, `mission_status`, `launch_date`, `launch_site`, `last_check`. Vérifié toutes les 5 minutes, sans clé.
- **Prochaine mission Starship** (*Next Starship mission*, `sensor`) : état = nom de la prochaine mission Starship annoncée (vide/`unknown` s'il n'y en a pas). Attributs : `mission`, `launch_date`, `launch_time`, `launch_site`, `mission_status`, `vehicle`, `mission_type`, `url`, `last_check`. Même flux et même rafraîchissement (5 min) que le binary_sensor live.
- **Page du vaisseau Starship** (*Starship vehicle page*) : lien vers <https://www.spacex.com/vehicles/starship>, attribut `url`.
- **Actualités Starship** (*Starship news*) : nombre d'articles récents, avec les 5 dernières actualités Starship (`title`, `link`, `published`) dans l'attribut `news`. Rafraîchi toutes les 30 minutes via [NewsAPI](https://newsapi.org).

Version actuelle : **1.4.0**. Nécessite Home Assistant **2024.11.0** ou plus récent. Interface traduite en anglais et en français.

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

## Notifications (événements)

Quand le live Starship commence, l'intégration déclenche l'événement Home Assistant `starship_tracker_live_started`, et `starship_tracker_live_ended` quand il se termine. Données : `mission`, `url`, `launch_date`, `launch_site`, `mission_status`. Aucun événement n'est émis au démarrage de Home Assistant, seulement lors d'un changement d'état.

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

## Limites

- Le flux JSON est interne au site spacex.com, pas une API documentée : il peut changer sans préavis.
- Le statut dépend de la mise à jour du flag `isLive` par SpaceX, et du délai de 5 minutes entre deux vérifications.

## Brand / Icônes

Les icônes et logos de l'intégration sont dans `custom_components/starship_tracker/brand/`
(`icon.png`, `icon@2x.png`, `dark_icon*.png`, `logo*.png`, `dark_logo*.png`, PNG transparents).
Home Assistant (2026.3+) les utilise directement pour les intégrations personnalisées.

Integration icons and logos live in `custom_components/starship_tracker/brand/` (transparent PNGs),
used directly by Home Assistant for custom integrations.
