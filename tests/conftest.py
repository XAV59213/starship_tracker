"""Fixtures communes (pytest-homeassistant-custom-component)."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Active les intégrations personnalisées dans chaque test HA."""
    yield
