# starship_tracker

[![Downloads](https://img.shields.io/github/downloads/XAV59213/starship_tracker/total.svg?label=Downloads)](https://github.com/XAV59213/starship_tracker/releases)

Intégration Home Assistant (HACS) qui expose :

- **Starship Live stream** : lien vers le flux en direct SpaceX (YouTube), attribut `url`.
- **Starship News** : nombre d'articles récents, avec les 5 dernières actualités Starship (`title`, `link`, `published`) dans l'attribut `news`. Rafraîchi toutes les 30 minutes via [NewsAPI](https://newsapi.org).

## Installation (HACS)

1. HACS → Intégrations → menu ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/XAV59213/starship_tracker` (catégorie *Intégration*).
2. Installer **Starship Tracker**, puis redémarrer Home Assistant.

## Configuration

1. Créer une clé gratuite sur <https://newsapi.org/register>.
2. Paramètres → Appareils et services → *Ajouter une intégration* → **Starship Tracker**.
3. Coller la clé NewsAPI. Elle est validée puis stockée dans la config entry Home Assistant (jamais dans le code).

## ⚠️ Sécurité

Les versions ≤ 1.0.3 contenaient une clé NewsAPI en clair dans `const.py`. Cette clé est publique dans l'historique Git : **elle doit être révoquée/régénérée** sur le compte NewsAPI. Depuis la 1.1.0, aucune clé n'est livrée avec l'intégration.

## Limites

Le sensor live ne détecte pas encore si une diffusion est en cours : il fournit seulement le lien.
