"""Fixtures communes (pytest-homeassistant-custom-component)."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Active les intégrations personnalisées dans chaque test HA."""
    yield


@pytest.fixture(autouse=True)
def no_youtube_tabs():
    """Les onglets publics YouTube ne sont jamais lus pendant les tests."""
    from unittest.mock import AsyncMock, patch

    with patch(
        "custom_components.starship_tracker.youtube_coordinator.async_fetch_channel_videos",
        AsyncMock(return_value=[]),
    ):
        yield
