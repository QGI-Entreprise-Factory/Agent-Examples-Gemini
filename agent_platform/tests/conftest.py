# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Shared test fixtures for the platform suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_platform.backend import registry
from agent_platform.backend.app import app
from agent_platform.registry import build_registry


@pytest.fixture(scope="session", autouse=True)
def _ensure_manifest():
    """Make sure the manifest is built before any test runs."""
    build_registry.main()
    registry.load_manifest.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
