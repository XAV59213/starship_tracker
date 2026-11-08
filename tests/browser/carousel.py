"""Standalone browser regression: python carousel.py [path/to/card.js].

Requires playwright and installed Chromium/WebKit; not collected by pytest.
"""

import os
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

CARD = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[2]
    / "custom_components/starship_tracker/www/starship-tracker-card.js"
)

with sync_playwright() as p:
    for engine in (
        [p.chromium, p.webkit] if os.environ.get("TEST_WEBKIT") else [p.chromium]
    ):
        options = {"headless": True}
        if engine.name == "chromium" and os.environ.get("CHROMIUM_PATH"):
            options["executable_path"] = os.environ["CHROMIUM_PATH"]
            options["args"] = ["--no-sandbox"]
        browser = engine.launch(**options)
        page = browser.new_page(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page.set_content(
            '<meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}ha-card{display:block}</style><starship-tracker-card></starship-tracker-card>'
        )
        page.add_script_tag(path=str(CARD))
        page.evaluate("""() => {
            window.card = document.querySelector('starship-tracker-card');
            card.setConfig({});
            const missions = Array.from({length:21}, (_,i) => ({mission:'Flight '+(21-i), link:'flight-'+i, launch_date:'2024-11-19', mission_status:'final'}));
            card.hass = {language:'fr', states:{'sensor.starship_tracker_starship_missions':{state:'21',attributes:{upcoming:missions.slice(0,2),past:missions.slice(2)}}}};
        }""")
        track = page.locator(".track")
        assert track.evaluate("(t)=>t.clientWidth") == 390
        assert page.locator(".tile").count() == 21
        assert page.locator(".arr.l").is_disabled()
        for i in range(1, 21):
            page.locator(".arr.r").click()
            page.wait_for_function(
                '(i)=>card.shadowRoot.querySelector(".car-count").textContent === `${i+1} / 21`',
                arg=i,
            )
        assert page.locator(".arr.r").is_disabled()
        end = track.evaluate("(t)=>t.scrollLeft")
        page.evaluate("card._render()")
        page.wait_for_timeout(100)
        assert abs(track.evaluate("(t)=>t.scrollLeft") - end) < 2
        for i in range(19, -1, -1):
            page.locator(".arr.l").click()
            page.wait_for_function(
                '(i)=>card.shadowRoot.querySelector(".car-count").textContent === `${i+1} / 21`',
                arg=i,
            )
        assert page.locator(".arr.l").is_disabled()
        # Real mobile touch swipes through Chromium's input protocol.
        if engine.name == "chromium":
            session = page.context.new_cdp_session(page)
            bounds = track.bounding_box()
            y = bounds["y"] + 40
            for _ in range(30):
                if page.locator(".arr.r").is_disabled():
                    break
                session.send(
                    "Input.dispatchTouchEvent",
                    {"type": "touchStart", "touchPoints": [{"x": 340, "y": y}]},
                )
                for x in range(320, 39, -20):
                    session.send(
                        "Input.dispatchTouchEvent",
                        {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]},
                    )
                    page.wait_for_timeout(10)
                session.send(
                    "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}
                )
                page.wait_for_timeout(250)
            assert page.locator(".arr.r").is_disabled()
            assert page.locator(".car-count").inner_text() == "21 / 21"
        print(
            engine.name,
            "PASS: 21 tiles, arrows both ways, end states, scroll preservation; Chromium native swipe",
        )
        # Explicit user limits are respected; old YAML used 10, not the new default.
        page.evaluate("card.setConfig({carousel_count:10})")
        assert page.locator(".tile").count() == 10
        page.evaluate("card.setConfig({})")
        assert page.locator(".tile").count() == 21
        # Wide cards have multiple clamped tile offsets at the right edge.
        page.set_viewport_size({"width": 1200, "height": 844})
        page.evaluate("card.shadowRoot.querySelector('.track').scrollLeft = 100000")
        page.wait_for_timeout(100)
        end = track.evaluate("(t)=>t.scrollLeft")
        page.locator(".arr.l").click()
        assert track.evaluate("(t)=>t.scrollLeft") < end
        browser.close()
