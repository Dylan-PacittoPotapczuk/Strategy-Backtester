"""Shared fixtures for engine tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.data.adapter import FixtureDataAdapter


@pytest.fixture
def start() -> date:
    return date(2024, 1, 2)
