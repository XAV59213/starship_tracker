"""Récapitulatif « Autorisations avant décollage » : parsers (fixtures réduites, sans réseau)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from custom_components.starship_tracker.authorizations import (
    CAMERON_URL,
    FAA_STARSHIP_URL,
    FAA_TFR_LIST_URL,
    NGA_WARNINGS_URL,
    build_items,
    overall,
    parse_cameron_closures,
    parse_faa_page_updated,
    parse_nga_warnings,
    parse_tfr_list,
    parse_tfr_webtext,
    tfr_url,
)

FIX = Path(__file__).parent / "fixtures" / "authorizations"


def _json(name: str) -> Any:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_parse_tfr_list_keeps_starbase_space_operations() -> None:
    notams = parse_tfr_list(_json("tfr_list.json"))
    assert [n["notam_id"] for n in notams] == ["6/7129", "6/7130"]  # Cape Canaveral et doublon exclus
    assert notams[0]["date"] == "2026-11-13"
    assert notams[0]["url"] == "https://tfr.faa.gov/tfr3/?page=detail_6_7129"
    assert notams[0]["revision"] == "202611111650"
    assert parse_tfr_list({"error": 1}) == []
    assert parse_tfr_list(None) == []
    assert tfr_url("6/7132") == "https://tfr.faa.gov/tfr3/?page=detail_6_7132"


def test_parse_tfr_webtext() -> None:
    assert parse_tfr_webtext(_json("tfr_text_6_7129.json")) == {
        "start": "2026-11-13T22:30:00+00:00",
        "end": "2026-11-14T00:40:00+00:00",
    }
    assert parse_tfr_webtext([]) == {}
    assert parse_tfr_webtext({"text": "nothing"}) == {}


def test_parse_nga_warnings() -> None:
    warnings = parse_nga_warnings(_json("nga_warnings.json"))
    assert [w["id"] for w in warnings] == ["NAVAREA IV 1187/26"]  # Floride / épave exclues
    assert "ROCKET LAUNCHING" in warnings[0]["text"]
    assert parse_nga_warnings("<html>503</html>") == []


def test_parse_cameron_closures() -> None:
    page = (FIX / "cameron.html").read_text(encoding="utf-8")
    rows = parse_cameron_closures(page, date(2025, 10, 13))
    assert [r["date"] for r in rows] == ["2025-10-13", "2025-10-14", "2025-10-15"]
    assert rows[0]["scheduled"] is True and rows[1]["scheduled"] is False
    assert rows[0]["time"] == "12:00 p.m. to 10:00 p.m."
    assert parse_cameron_closures(page, date(2026, 11, 11)) == []  # dates passées ignorées
    assert parse_cameron_closures("", date(2026, 11, 11)) == []


def test_parse_faa_page_updated() -> None:
    page = "<p>Stay informed</p><div>Last updated: <time>Tuesday, November 10, 2026</time></div>"
    assert parse_faa_page_updated(page) == "2026-11-10"
    assert parse_faa_page_updated("<p>nothing</p>") is None


def test_build_items_all_sources() -> None:
    notams = parse_tfr_list(_json("tfr_list.json"))
    notams[0].update(parse_tfr_webtext(_json("tfr_text_6_7129.json")))
    closures = parse_cameron_closures((FIX / "cameron.html").read_text(encoding="utf-8"), date(2025, 10, 13))
    items = build_items(
        notams=notams, notams_updated="t1",
        closures=closures, closures_updated="t2",
        navigation=parse_nga_warnings(_json("nga_warnings.json")), navigation_updated="t3",
        faa_page_updated="2026-11-10",
    )
    by_key = {i["key"]: i for i in items}
    assert list(by_key) == ["faa_license", "notam", "navigation", "road_closure"]
    assert by_key["faa_license"]["status"] == "unknown"
    assert by_key["faa_license"]["url"] == FAA_STARSHIP_URL
    assert "2026-11-10" in by_key["faa_license"]["detail"]
    assert by_key["notam"]["status"] == "ok"
    assert by_key["notam"]["detail"] == "NOTAM 6/7129 (+1) · 2026-11-13T22:30:00+00:00"
    assert by_key["notam"]["notams"][0]["end"] == "2026-11-14T00:40:00+00:00"
    assert by_key["navigation"]["status"] == "ok"
    assert by_key["road_closure"]["status"] == "ok"
    assert by_key["road_closure"]["url"] == CAMERON_URL
    assert all({"key", "label", "status", "detail", "url", "updated"} <= set(i) for i in items)
    assert overall(items) == "partial"  # licence non vérifiable automatiquement


def test_build_items_sources_down_or_empty() -> None:
    items = build_items(notams=None, notams_updated=None, closures=None, closures_updated=None,
                        navigation=None, navigation_updated=None)
    assert [i["key"] for i in items] == ["faa_license", "notam", "road_closure"]  # NGA omis
    assert {i["status"] for i in items} == {"unknown"}
    assert overall(items) == "pending"
    items = build_items(notams=[], notams_updated="t", closures=[{"date": "2026-11-13", "time": "", "scheduled": False}],
                        closures_updated="t", navigation=[], navigation_updated="t")
    assert [i["status"] for i in items] == ["unknown", "pending", "pending", "pending"]
    assert overall([{"status": "ok"}]) == "ready"


def test_urls_are_public_sources() -> None:
    assert FAA_TFR_LIST_URL.startswith("https://tfr.faa.gov/")
    assert NGA_WARNINGS_URL.startswith("https://msi.nga.mil/") and "output=json" in NGA_WARNINGS_URL


async def test_coordinator_end_to_end(hass, aioclient_mock) -> None:
    """Coordinator : sources mockées, puis limitation des requêtes au rafraîchissement suivant."""
    from custom_components.starship_tracker.authorizations import FAA_TFR_TEXT_URL
    from custom_components.starship_tracker.authorizations_coordinator import LaunchAuthorizationsCoordinator

    aioclient_mock.get(FAA_TFR_LIST_URL, json=_json("tfr_list.json"))
    aioclient_mock.get(FAA_TFR_TEXT_URL.format(notam_id="6/7129"), json=_json("tfr_text_6_7129.json"))
    aioclient_mock.get(FAA_TFR_TEXT_URL.format(notam_id="6/7130"), status=500)
    aioclient_mock.get(NGA_WARNINGS_URL, json=_json("nga_warnings.json"))
    aioclient_mock.get(CAMERON_URL, text=(FIX / "cameron.html").read_text(encoding="utf-8"))
    aioclient_mock.get(FAA_STARSHIP_URL, text="<div>Last updated: Tuesday, November 10, 2026</div>")
    coordinator = LaunchAuthorizationsCoordinator(hass)
    await coordinator.async_refresh()
    data = coordinator.data
    assert coordinator.last_update_success
    by_key = {i["key"]: i for i in data["items"]}
    assert by_key["notam"]["status"] == "ok"
    assert by_key["notam"]["notams"][0]["start"] == "2026-11-13T22:30:00+00:00"
    assert "start" not in by_key["notam"]["notams"][1]  # texte en erreur : NOTAM gardé quand même
    assert by_key["navigation"]["status"] == "ok"
    assert by_key["road_closure"]["status"] == "pending"  # tableau du comté : dates passées
    assert by_key["faa_license"]["page_updated"] == "2026-11-10"
    assert data["total"] == 4 and data["ok_count"] == 2 and data["overall"] == "partial"
    calls = aioclient_mock.call_count
    await coordinator.async_refresh()
    assert aioclient_mock.call_count == calls  # intervalles minimaux par source respectés


async def test_coordinator_all_sources_down(hass, aioclient_mock) -> None:
    from custom_components.starship_tracker.authorizations_coordinator import LaunchAuthorizationsCoordinator

    for url in (FAA_TFR_LIST_URL, NGA_WARNINGS_URL, CAMERON_URL, FAA_STARSHIP_URL):
        aioclient_mock.get(url, status=503)
    coordinator = LaunchAuthorizationsCoordinator(hass)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert [i["status"] for i in coordinator.data["items"]] == ["unknown", "unknown", "unknown"]
    assert coordinator.data["overall"] == "pending"
