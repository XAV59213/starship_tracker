"""Real YouTube channel tabs (recorded 2026-11-08) to catch YouTube layout changes."""
from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest

from custom_components.starship_tracker.youtube_parser import parse_channel_tab

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 8, 15, 0, tzinfo=UTC)


def _page(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes()).decode()


@pytest.mark.parametrize(
    ("name", "streams", "count", "statuses"),
    [
        ("ufotinik_streams", True, 5, {"ended"}),
        ("ufotinik_videos", False, 9, {None}),
        ("starbase_streams", True, 5, {"ended"}),
        ("starbase_videos", False, 20, {None}),
        ("nsf_streams", True, 5, {"ended", "live"}),
        ("nsf_videos", False, 17, {None}),
    ],
)
def test_recorded_channel_tabs(name: str, streams: bool, count: int, statuses: set[str | None]) -> None:
    videos = parse_channel_tab(_page(name), "starship", NOW, streams=streams)
    assert len(videos) == count
    assert {video.get("live_status") for video in videos} == statuses
    for video in videos:
        assert "starship" in video["title"].casefold()
        assert len(video["video_id"]) == 11
        assert video["url"].startswith("https://www.youtube.com/watch?v=")
        datetime.fromisoformat(video["published"])
