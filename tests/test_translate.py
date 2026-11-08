"""Tests de la traduction FR."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.starship_tracker import translate as tr
from custom_components.starship_tracker.translate import (
    GTX_URL,
    MYMEMORY_URL,
    Translator,
    async_translate_mission,
    translate_status,
    translate_timeline_entry,
    translate_title,
)


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        ("Starship's Seventh Flight Test", "7e vol d'essai Starship"),
        ("Starship's First Flight Test", "1er vol d'essai Starship"),
        ("Starship's Thirteenth Flight Test", "13e vol d'essai Starship"),
        ("Starship Flight 15", "Vol Starship 15"),
        ("Starship Flight Test", "Vol d'essai Starship"),
        ("Starship High Altitude Test - SN10", "Test haute altitude Starship - SN10"),
        ("Starship Test - SN5", "Test Starship - SN5"),
        ("USSF-627 Mission", "USSF-627 Mission"),
        (None, None),
    ],
)
def test_titles(src, dst):
    assert translate_title(src) == dst


def test_status_and_dictionary():
    assert translate_status("final") == "Terminé"
    assert translate_status("upcoming") == "À venir"
    assert translate_status("live") == "En direct"
    assert translate_status("weird") == "weird"
    assert translate_status(None) is None
    assert translate_timeline_entry("LIFTOFF") == "Décollage"
    assert translate_timeline_entry("Max Q (moment of peak aerodynamic stress on the rocket)").startswith("Max Q (moment")
    assert translate_timeline_entry("Something new") is None


def test_chunks():
    text = ("A sentence. " * 80).strip() + "\n\nSecond para."
    parts = tr._chunks(text)
    assert all(len(p) <= tr.MAX_CHUNK for p in parts)
    assert "\n\n" in parts


async def test_translator_gtx_then_cache(hass: HomeAssistant, aioclient_mock, hass_storage) -> None:
    aioclient_mock.get(GTX_URL, json=[[["Bonjour ", "Hello "], ["monde", "world"]]])
    t = Translator(hass)
    assert await t.async_translate("Hello world") == "Bonjour monde"
    calls = aioclient_mock.call_count
    assert await t.async_translate("Hello world") == "Bonjour monde"
    assert aioclient_mock.call_count == calls
    assert await t.async_translate("") is None


async def test_translator_fallback_and_failure(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(GTX_URL, status=429)
    aioclient_mock.get(MYMEMORY_URL, json={"responseStatus": 200, "responseData": {"translatedText": "Salut"}})
    t = Translator(hass)
    assert await t.async_translate("Hi") == "Salut"
    aioclient_mock.clear_requests()
    aioclient_mock.get(GTX_URL, status=429)
    aioclient_mock.get(MYMEMORY_URL, json={"quotaFinished": True, "responseStatus": 429})
    assert await t.async_translate("Other") is None
    t._budget = 0
    assert await t._remote("x") is None


async def test_translate_mission(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(GTX_URL, json=[[["Texte FR", "x"]]])
    out = await async_translate_mission(Translator(hass), {
        "mission": "Starship Flight 15", "mission_status": "upcoming",
        "mission_description": "English text.",
        "mission_countdown": [["00:50:00", "Propellant load"]],
        "mission_timeline": [["00:00:00", "Liftoff"], ["00:09:00", "Some new event"]],
    })
    assert out["mission_fr"] == "Vol Starship 15"
    assert out["mission_status_fr"] == "À venir"
    assert out["mission_description_fr"] == "Texte FR"
    assert out["mission_countdown_fr"] == [["00:50:00", "Remplissage des ergols"]]
    assert out["mission_timeline_fr"] == [["00:00:00", "Décollage"], ["00:09:00", "Texte FR"]]
