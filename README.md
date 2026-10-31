# starship_tracker

[![Downloads](https://img.shields.io/github/downloads/XAV59213/starship_tracker/total.svg?label=Downloads)](https://github.com/XAV59213/starship_tracker/releases)

Intégration Home Assistant (HACS) qui expose :

- **SpaceX live sur X** (`binary_sensor`, optionnel) : `on` quand SpaceX diffuse un live sur X, `off` sinon. Attributs : `url` (lien `x.com/i/broadcasts/…`), `title`, `post_url`, `started_at`, `last_check`. Vérifié toutes les 10 minutes.
- **Starship Live stream** : lien vers le compte X de SpaceX, attribut `url`.
- **Starship News** : nombre d'articles récents, avec les 5 dernières actualités Starship (`title`, `link`, `published`) dans l'attribut `news`. Rafraîchi toutes les 30 minutes via [NewsAPI](https://newsapi.org).

## Installation (HACS)

1. HACS → Intégrations → menu ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/XAV59213/starship_tracker` (catégorie *Intégration*).
2. Installer **Starship Tracker**, puis redémarrer Home Assistant.

## Configuration

1. Créer une clé gratuite sur <https://newsapi.org/register>.
2. Paramètres → Appareils et services → *Ajouter une intégration* → **Starship Tracker**.
3. Coller la clé NewsAPI. Optionnel : coller un *bearer token* de l'API X (<https://developer.x.com>) pour activer la détection du live. Il peut aussi être ajouté plus tard via *Configurer* (options).

La clé NewsAPI Elle est validée puis stockée dans la config entry Home Assistant (jamais dans le code).

## ⚠️ Sécurité

Les versions ≤ 1.0.3 contenaient une clé NewsAPI en clair dans `const.py`. Cette clé est publique dans l'historique Git : **elle doit être révoquée/régénérée** sur le compte NewsAPI. Depuis la 1.1.0, aucune clé n'est livrée avec l'intégration.

## Détection du live (X)

Choix d'un `binary_sensor` (classe idiomatique HA pour un état on/off) plutôt qu'un sensor texte.

SpaceX diffuse ses lives sur X et publie à chaque fois un post contenant un lien `x.com/i/broadcasts/…`. Toutes les 10 minutes, l'intégration interroge l'API X v2 (`tweets/search/recent`, requête `from:SpaceX url:"x.com/i/broadcasts"`). Si le dernier post de ce type a moins de 2 heures, le capteur passe à `on`.

## Limites

- Heuristique : l'API X n'expose pas l'état réel d'une diffusion. Un live de plus de 2 h repasse à `off`, et un post annonçant un live à venir peut le passer à `on` trop tôt.
- L'API X nécessite un bearer token (accès payant / à l'usage selon l'offre X). 144 requêtes par jour environ.
- Sans token, le binary_sensor n'est pas créé ; news et lien restent fonctionnels.
