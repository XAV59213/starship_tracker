"""Numéros booster / vaisseau depuis Launch Library 2."""

from custom_components.starship_tracker.live_coordinator import flight_number, parse_ll2_vehicles


def test_parse_ll2_vehicles() -> None:
    data = {"results": [
        {"name": "Starship | Starlink Group 31-2 (Starship Flight 15)", "rocket": {
            "launcher_stage": [{"launcher": {"serial_number": "Booster 22"}}],
            "spacecraft_stage": [{"spacecraft": {"name": "Ship 42", "serial_number": "S42"}}],
        }},
        {"name": "Starship | SpaceX HLS LEO Demo", "rocket": {"launcher_stage": [], "spacecraft_stage": None}},
        {"name": "Starship Flight 16", "rocket": {"launcher_stage": [], "spacecraft_stage": None}},
    ]}
    assert parse_ll2_vehicles(data) == {15: {"booster": "B22", "ship": "S42"}}
    assert parse_ll2_vehicles({"detail": "throttled"}) == {}
    assert parse_ll2_vehicles(None) == {}


def test_flight_number() -> None:
    assert flight_number("Starship Flight 15") == 15
    assert flight_number("Starship's Twelfth Flight Test") is None
