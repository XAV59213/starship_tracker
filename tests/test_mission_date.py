"""Tests du parseur de date des pages mission SpaceX (sans Home Assistant)."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / "starship_tracker" / "mission_date.py"
)
_SPEC = importlib.util.spec_from_file_location("starship_mission_date", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mission_date = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mission_date
_SPEC.loader.exec_module(mission_date)

parse_launch_prose = mission_date.parse_launch_prose
parse_mission_page = mission_date.parse_mission_page
apply_launch_fields = mission_date.apply_launch_fields
tile_needs_mission_page = mission_date.tile_needs_mission_page
tile_sort_key = mission_date.tile_sort_key

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)

FLIGHT_15 = (
    'Flight 15 of <a href=https://www.spacex.com/vehicles/starship/ target="_">Starship</a> '
    "is preparing to launch as soon as Friday, November 13, pending regulatory approval. "
    "The 75-minute launch window will open at 4:45 p.m. CT."
)
FLIGHT_15_FOLLOWUP = (
    "A live webcast of the flight will begin about 30 minutes before liftoff. "
    "The flight profile lasts more than 22-hour."
)


def _z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_flight_15_prose_is_2026_11_13_2245z() -> None:
    parsed = parse_launch_prose(FLIGHT_15, now=NOW)
    assert parsed is not None
    assert parsed.when is not None
    assert _z(parsed.when) == "2026-11-13T22:45:00Z"
    assert parsed.has_time is True
    assert parsed.launch_date == "2026-11-13"
    assert parsed.launch_time == "22:45:00+00:00"
    assert parsed.launch_window_minutes == 75
    # Même combinaison que launch_datetime : date UTC + heure décalée.
    stamp = f"{parsed.launch_date}T{parsed.launch_time}"
    assert datetime.fromisoformat(stamp).astimezone(timezone.utc) == parsed.when


def test_newlines_between_date_time_and_zone() -> None:
    parsed = parse_launch_prose(
        "Friday,\nNovember 13.\nThe 75-minute launch window will open at\n4:45 p.m.\nCT.",
        now=NOW,
    )
    assert parsed is not None and parsed.when is not None
    assert _z(parsed.when) == "2026-11-13T22:45:00Z"
    assert parsed.launch_window_minutes == 75


def test_flight_15_page_ignores_minutes_that_are_not_a_window() -> None:
    payload = {
        "paragraphs": [
            {"id": 1, "content": FLIGHT_15},
            {"id": 2, "content": FLIGHT_15_FOLLOWUP},
        ]
    }
    parsed = parse_mission_page(payload, now=NOW)
    assert parsed is not None
    assert _z(parsed.when) == "2026-11-13T22:45:00Z"
    assert parsed.launch_window_minutes == 75


def test_optional_year_uses_next_occurrence() -> None:
    # 18:00 UTC le 14 est déjà le 14 novembre à Chicago (CST, UTC−6).
    parsed = parse_launch_prose(
        "Launch on November 13 at 4:45 p.m. CT.",
        now=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
    )
    assert parsed is not None and parsed.when is not None
    assert _z(parsed.when) == "2027-11-13T22:45:00Z"

    today = parse_launch_prose(
        "Launch on November 13 at 4:45 p.m. CT.",
        now=datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc),
    )
    assert today is not None and today.when is not None
    assert _z(today.when) == "2026-11-13T22:45:00Z"


def test_explicit_year_is_kept_even_in_the_past() -> None:
    parsed = parse_launch_prose("November 13, 2024 at 4:45 p.m. CT.", now=NOW)
    assert parsed is not None and parsed.when is not None
    assert _z(parsed.when) == "2024-11-13T22:45:00Z"


def test_ordinal_abbreviation_and_dmy() -> None:
    ordinal = parse_launch_prose("Friday, Nov. 13th, 2026 at 4:45 p.m. CT.", now=NOW)
    assert ordinal is not None and ordinal.when is not None
    assert _z(ordinal.when) == "2026-11-13T22:45:00Z"

    dmy = parse_launch_prose("13 November 2026 at 4:45pm CT.", now=NOW)
    assert dmy is not None and dmy.when is not None
    assert _z(dmy.when) == "2026-11-13T22:45:00Z"


def test_zoneinfo_dst_and_other_zones() -> None:
    summer = parse_launch_prose(
        "July 4 at 4:45 p.m. CT. The 45-minute window opens then.",
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert summer is not None and summer.when is not None
    assert _z(summer.when) == "2026-07-04T21:45:00Z"
    assert summer.launch_window_minutes == 45

    # En novembre America/Chicago est en CST, même si le texte dit CDT.
    winter_cdt = parse_launch_prose("November 13, 2026 at 4:45 p.m. CDT.", now=NOW)
    assert winter_cdt is not None and winter_cdt.when is not None
    assert _z(winter_cdt.when) == "2026-11-13T22:45:00Z"

    eastern = parse_launch_prose("November 13 at 4:45 p.m. ET.", now=NOW)
    assert eastern is not None and eastern.when is not None
    assert _z(eastern.when) == "2026-11-13T21:45:00Z"

    pacific = parse_launch_prose("November 13 at 4:45 p.m. PT.", now=NOW)
    assert pacific is not None and pacific.when is not None
    assert _z(pacific.when) == "2026-11-14T00:45:00Z"
    assert pacific.launch_date == "2026-11-14"
    assert pacific.launch_time == "00:45:00+00:00"

    utc = parse_launch_prose("November 13 at 4:45 p.m. UTC.", now=NOW)
    assert utc is not None and utc.when is not None
    assert _z(utc.when) == "2026-11-13T16:45:00Z"

    gmt = parse_launch_prose("November 13 at 12:00 a.m. GMT.", now=NOW)
    assert gmt is not None and gmt.when is not None
    assert _z(gmt.when) == "2026-11-13T00:00:00Z"

    noon = parse_launch_prose("November 13 at 12:00 p.m. CT.", now=NOW)
    assert noon is not None and noon.when is not None
    assert _z(noon.when) == "2026-11-13T18:00:00Z"


def test_time_without_zone_keeps_the_date_only() -> None:
    parsed = parse_launch_prose("Launch as soon as November 13 at 4:45 p.m.", now=NOW)
    assert parsed is not None
    assert parsed.has_time is False
    assert parsed.launch_time is None
    assert parsed.launch_date == "2026-11-13"
    assert parsed.when is not None
    assert _z(parsed.when) == "2026-11-13T00:00:00Z"


def test_window_only_and_no_match() -> None:
    window = parse_launch_prose("The 90-minute launch window is not yet dated.", now=NOW)
    assert window is not None
    assert window.when is None
    assert window.launch_window_minutes == 90

    assert parse_launch_prose("No schedule has been announced.", now=NOW) is None
    assert parse_mission_page({"paragraphs": []}, now=NOW) is None
    assert parse_mission_page(None, now=NOW) is None


def test_february_29_rolls_to_the_next_valid_year() -> None:
    parsed = parse_launch_prose("February 29 at 1:00 a.m. UTC.", now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert parsed is not None and parsed.when is not None
    assert _z(parsed.when) == "2028-02-29T01:00:00Z"


def test_feed_values_keep_priority() -> None:
    prose = parse_launch_prose(FLIGHT_15, now=NOW)
    tile = {
        "title": "Starship Flight 15",
        "link": "starship-flight-15",
        "launchDate": "2026-12-01",
        "launchTime": "18:00:00",
        "endDate": None,
    }
    mission = {"launch_date": "2026-12-01", "launch_time": "18:00:00"}
    updated = apply_launch_fields(mission, tile, prose)
    assert updated["launch_date"] == "2026-12-01"
    assert updated["launch_time"] == "18:00:00"
    assert updated["date_source"] == "feed"
    assert updated["launch_window_minutes"] is None
    assert tile_needs_mission_page(tile) is False


def test_null_feed_dates_use_the_mission_page() -> None:
    prose = parse_launch_prose(FLIGHT_15, now=NOW)
    tile = {
        "title": "Starship Flight 15",
        "link": "starship-flight-15",
        "launchDate": None,
        "launchTime": None,
        "endDate": None,
    }
    mission = {"launch_date": None, "launch_time": None}
    updated = apply_launch_fields(mission, tile, prose)
    assert updated["date_source"] == "mission_page"
    assert updated["launch_date"] == "2026-11-13"
    assert updated["launch_time"] == "22:45:00+00:00"
    assert updated["launch_window_minutes"] == 75
    assert tile_needs_mission_page(tile) is True


def test_end_date_alone_blocks_the_mission_page() -> None:
    tile = {"launchDate": None, "launchTime": None, "endDate": "2026-11-20", "link": "starship-flight-15"}
    mission = {"launch_date": None, "launch_time": None}
    updated = apply_launch_fields(mission, tile, parse_launch_prose(FLIGHT_15, now=NOW))
    assert updated["date_source"] == "feed"
    assert updated["launch_date"] is None
    assert updated["launch_window_minutes"] is None
    assert tile_needs_mission_page(tile) is False


def test_sort_uses_the_parsed_date_when_the_feed_is_empty() -> None:
    dated = {"launchDate": "2026-12-01", "launchTime": "18:00:00", "link": "later"}
    flight_15 = {"launchDate": None, "launchTime": None, "endDate": None, "link": "starship-flight-15"}
    parsed = parse_launch_prose(FLIGHT_15, now=NOW)
    assert tile_sort_key(flight_15, parsed) < tile_sort_key(dated, None)
    assert tile_sort_key(flight_15, None) == ("9999", "")


extract_mission_details = mission_date.extract_mission_details


def test_extract_mission_details():
    payload = {
        "imageDesktop": {"url": "/cms-assets/a.png", "formats": {"large": {"url": "https://content.spacex.com/cms-assets/large_a.png"}}},
        "imageMobile": {"url": "/cms-assets/m.png"},
        "paragraphs": [{"content": FLIGHT_15}, {"content": 'Watch <a href="https://x.com/SpaceX">on X</a> &amp; more.'}],
        "webcasts": [{"url": "https://www.youtube.com/watch?v=1"}],
    }
    d = extract_mission_details(payload)
    assert d["mission_image"] == "https://content.spacex.com/cms-assets/large_a.png"
    assert d["mission_image_mobile"] == "https://content.spacex.com/cms-assets/m.png"
    assert "<" not in d["mission_description"] and "Watch on X & more." in d["mission_description"]
    assert d["mission_links"] == ["https://www.spacex.com/vehicles/starship/", "https://x.com/SpaceX"]
    assert d["webcast_links"] == ["https://www.youtube.com/watch?v=1"]


def test_extract_mission_details_limits():
    d = extract_mission_details({"paragraphs": [{"content": "a" * 5000}]})
    assert len(d["mission_description"]) == mission_date.MISSION_DESCRIPTION_MAX
    assert extract_mission_details(None) == {}
