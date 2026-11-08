"""Traduction FR du contenu SpaceX (titres, statuts, chronologie, description).

1. Règles déterministes : statuts, titres (« Starship's Seventh Flight Test » →
   « 7e vol d'essai Starship »), dictionnaire des termes de chronologie.
2. Le reste passe par une traduction gratuite sans clé :
   translate.googleapis.com (client=gtx), puis api.mymemory.translated.net.
   Ces services ne sont pas garantis (limites, blocages d'IP) : en cas
   d'échec le texte original est conservé et retenté plus tard.
3. Chaque texte traduit est mis en cache de façon persistante (Store).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
GTX_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MAX_CHUNK = 450
MAX_REMOTE_PER_RUN = 40

STATUS_FR = {"final": "Terminé", "upcoming": "À venir", "live": "En direct", "active": "En cours", "past": "Terminé"}

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20,
}


def _ord_fr(n: int) -> str:
    return "1er" if n == 1 else f"{n}e"


def translate_title(title: str | None) -> str | None:
    """Traduction déterministe des titres de missions Starship."""
    if not title:
        return title
    t = title.strip()
    m = re.fullmatch(r"Starship'?s?\s+(\w+)\s+Flight\s+Test", t, re.IGNORECASE)
    if m and m.group(1).lower() in _ORDINALS:
        return f"{_ord_fr(_ORDINALS[m.group(1).lower()])} vol d'essai Starship"
    m = re.fullmatch(r"Starship\s+Flight\s+(\d+)", t, re.IGNORECASE)
    if m:
        return f"Vol Starship {m.group(1)}"
    m = re.fullmatch(r"Starship\s+Flight\s+Test", t, re.IGNORECASE)
    if m:
        return "Vol d'essai Starship"
    m = re.fullmatch(r"Starship\s+High\s+Altitude\s+Test\s*-\s*(\S+)", t, re.IGNORECASE)
    if m:
        return f"Test haute altitude Starship - {m.group(1)}"
    m = re.fullmatch(r"Starship\s+Test\s*-\s*(\S+)", t, re.IGNORECASE)
    if m:
        return f"Test Starship - {m.group(1)}"
    return title


def translate_status(status: str | None) -> str | None:
    if not status:
        return status
    return STATUS_FR.get(status.lower(), status)


# Termes fréquents des chronologies SpaceX (minuscule → FR). Ordre : du plus long au plus court.
TIMELINE_FR: dict[str, str] = {
    "spacex flight director conducts poll and verifies go for propellant load": "Le directeur de vol SpaceX fait le tour des équipes et confirme le GO pour le remplissage des ergols",
    "max q (moment of peak aerodynamic stress on the rocket)": "Max Q (moment de contrainte aérodynamique maximale sur la fusée)",
    "super heavy meco (most engines cut off)": "MECO du Super Heavy (arrêt de la plupart des moteurs)",
    "hot-staging (starship raptor ignition and stage separation)": "Hot-staging (allumage des Raptor de Starship et séparation des étages)",
    "super heavy boostback burn startup": "Début de l'allumage de retour (boostback) du Super Heavy",
    "super heavy boostback burn shutdown": "Fin de l'allumage de retour (boostback) du Super Heavy",
    "super heavy is expected to be over the gulf of america": "Super Heavy devrait être au-dessus du golfe du Mexique",
    "super heavy landing burn startup": "Début de l'allumage d'atterrissage du Super Heavy",
    "super heavy landing burn shutdown": "Fin de l'allumage d'atterrissage du Super Heavy",
    "super heavy landing burn startup and catch": "Allumage d'atterrissage et capture du Super Heavy",
    "super heavy catch": "Capture du Super Heavy",
    "booster lox (liquid oxygen) load underway": "Remplissage du LOX (oxygène liquide) du booster en cours",
    "booster fuel (liquid methane) load underway": "Remplissage du carburant (méthane liquide) du booster en cours",
    "starship fuel (liquid methane) load underway": "Remplissage du carburant (méthane liquide) de Starship en cours",
    "starship lox (liquid oxygen) load underway": "Remplissage du LOX (oxygène liquide) de Starship en cours",
    "raptor begins engine chill on booster": "Début de la mise en froid des moteurs Raptor du booster",
    "raptor begins engine chill on starship": "Début de la mise en froid des moteurs Raptor de Starship",
    "starship engine chill": "Mise en froid des moteurs de Starship",
    "booster engine chill": "Mise en froid des moteurs du booster",
    "spacex flight director verifies go for launch": "Le directeur de vol SpaceX confirme le GO pour le lancement",
    "excess propellant offload": "Délestage des ergols en excès",
    "flight computers command booster and ship propellant pressurization": "Les ordinateurs de vol commandent la pressurisation des ergols du booster et du vaisseau",
    "booster and ship propellant pressurization": "Pressurisation des ergols du booster et du vaisseau",
    "propellant load complete": "Remplissage des ergols terminé",
    "propellant load": "Remplissage des ergols",
    "starship secos (second engine cutoff)": "SECO de Starship (arrêt des moteurs du second étage)",
    "starship seco (second engine cutoff)": "SECO de Starship (arrêt des moteurs du second étage)",
    "starship seco": "SECO de Starship",
    "starship meco": "MECO de Starship",
    "starship entry": "Rentrée atmosphérique de Starship",
    "starship atmospheric entry": "Rentrée atmosphérique de Starship",
    "starship flip, landing burn, and landing": "Basculement, allumage d'atterrissage et atterrissage de Starship",
    "starship flip, landing burn, and catch": "Basculement, allumage d'atterrissage et capture de Starship",
    "starship landing flip": "Basculement d'atterrissage de Starship",
    "starship landing burn": "Allumage d'atterrissage de Starship",
    "starship splashdown": "Amerrissage de Starship",
    "starship catch": "Capture de Starship",
    "raptor in-space relight": "Rallumage d'un Raptor dans l'espace",
    "in-space raptor relight": "Rallumage d'un Raptor dans l'espace",
    "starlink simulator deployment begins": "Début du déploiement des simulateurs Starlink",
    "starlink simulator deployment complete": "Fin du déploiement des simulateurs Starlink",
    "payload deploy": "Déploiement de la charge utile",
    "hot-staging": "Hot-staging (séparation à chaud)",
    "stage separation": "Séparation des étages",
    "liftoff": "Décollage",
    "lift off": "Décollage",
    "max q": "Max Q (pression dynamique maximale)",
    "landing": "Atterrissage",
    "splashdown": "Amerrissage",
    "catch": "Capture",
}


def translate_timeline_entry(text: str) -> str | None:
    """Traduction par dictionnaire, ou None si le terme est inconnu."""
    key = re.sub(r"\s+", " ", (text or "").strip().lower()).rstrip(".")
    return TIMELINE_FR.get(key)


def _chunks(text: str) -> list[str]:
    """Découpe en morceaux ≤ MAX_CHUNK (paragraphes puis phrases)."""
    out: list[str] = []
    for para in text.split("\n\n"):
        cur = ""
        for sent in re.split(r"(?<=[.!?])\s+", para):
            if len(cur) + len(sent) + 1 > MAX_CHUNK and cur:
                out.append(cur)
                cur = ""
            cur = f"{cur} {sent}".strip()
        out.append(cur)
        out.append("\n\n")
    return out[:-1]


class Translator:
    """Traduction EN→FR avec cache persistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.translations")
        self._cache: dict[str, str] | None = None
        self._dirty = False
        self._budget = MAX_REMOTE_PER_RUN

    async def async_load(self) -> None:
        if self._cache is None:
            self._cache = (await self._store.async_load()) or {}

    async def async_translate(self, text: str | None) -> str | None:
        """Traduit un texte libre ; renvoie None si aucune traduction n'est disponible."""
        if not text or not text.strip():
            return None
        await self.async_load()
        assert self._cache is not None
        if text in self._cache:
            return self._cache[text]
        parts: list[str] = []
        for chunk in _chunks(text):
            if chunk == "\n\n" or not chunk.strip():
                parts.append(chunk)
                continue
            done = self._cache.get(chunk) or await self._remote(chunk)
            if done is None:
                return None
            self._cache[chunk] = done
            parts.append(done)
        result = "".join(_join(parts))
        self._cache[text] = result
        self._dirty = True
        return result

    def start_run(self) -> None:
        self._budget = MAX_REMOTE_PER_RUN

    async def async_save(self) -> None:
        if self._dirty and self._cache is not None:
            self._store.async_delay_save(lambda: self._cache or {}, 10)
            self._dirty = False

    async def _remote(self, text: str) -> str | None:
        if self._budget <= 0:
            return None
        self._budget -= 1
        session = async_get_clientsession(self._hass)
        for fn in (self._gtx, self._mymemory):
            try:
                async with asyncio.timeout(15):
                    result = await fn(session, text)
            except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as err:
                _LOGGER.debug("Traduction %s indisponible : %s", fn.__name__, err)
                continue
            if result:
                return result
        return None

    @staticmethod
    async def _gtx(session: aiohttp.ClientSession, text: str) -> str | None:
        params = {"client": "gtx", "sl": "en", "tl": "fr", "dt": "t", "q": text}
        async with session.get(GTX_URL, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
        return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip() or None

    @staticmethod
    async def _mymemory(session: aiohttp.ClientSession, text: str) -> str | None:
        params = {"q": text, "langpair": "en|fr"}
        async with session.get(MYMEMORY_URL, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
        if data.get("quotaFinished") or int(data.get("responseStatus") or 0) != 200:
            return None
        out = (data.get("responseData") or {}).get("translatedText")
        if not isinstance(out, str) or "MYMEMORY WARNING" in out.upper():
            return None
        return out.strip() or None


def _join(parts: list[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        if p != "\n\n" and out and out[-1] != "\n\n":
            out.append(" ")
        out.append(p)
    return out


async def async_translate_mission(tr: Translator, mission: dict[str, Any]) -> dict[str, Any]:
    """Champs FR (``*_fr``) pour la prochaine mission."""

    async def _entries(entries: list[list[str]] | None) -> list[list[str]]:
        out: list[list[str]] = []
        for time, desc in entries or []:
            fr = translate_timeline_entry(desc) or await tr.async_translate(desc) or desc
            out.append([time, fr])
        return out

    tr.start_run()
    result = {
        "mission_fr": translate_title(mission.get("mission")),
        "mission_status_fr": translate_status(mission.get("mission_status")),
        "mission_description_fr": await tr.async_translate(mission.get("mission_description")),
        "mission_countdown_fr": await _entries(mission.get("mission_countdown")),
        "mission_timeline_fr": await _entries(mission.get("mission_timeline")),
    }
    await tr.async_save()
    return result
