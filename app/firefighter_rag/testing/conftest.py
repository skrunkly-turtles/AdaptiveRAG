# testing/conftest.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # adds firefighter_rag/ to path

import pytest
import ollama
import demo
import demo_v2
import store
from datetime import datetime


def pytest_configure(config):
    """Sets asyncio mode so all async tests share a properly managed event loop."""
    config.inicfg["asyncio_mode"] = "auto"
    config.inicfg["asyncio_default_fixture_loop_scope"] = "function"


@pytest.fixture(autouse=True)
def reset_state():
    """
    Runs before every test: clears all store state AND rebinds demo.client
    to the current test's event loop. This fixes the 'Event loop is closed'
    error, which happens because the global client holds a reference to the
    previous test's now-dead loop.
    """
    # Reset store
    store.SHORT_TERM_POOL.clear()
    store.SHORT_TERM_TRENDS.clear()
    store.LONG_TERM_TRENDS.clear()
    store.CATEGORICAL_CONGLOMERATE = {'hr': [], 'o2': [], 'temp': [], 'elevation': []}

    # Rebind Ollama client to the fresh loop for this test
    try:
        host = getattr(demo.client, '_host', None)
        # demo.client = ollama.AsyncClient(host=host)
        demo_v2.client = ollama.AsyncClient(host=host)
    except Exception:
        # demo.client = ollama.AsyncClient()
        demo_v2.client = ollama.AsyncClient()

    yield

    # Teardown: clean up after test too
    store.SHORT_TERM_POOL.clear()
    store.SHORT_TERM_TRENDS.clear()
    store.LONG_TERM_TRENDS.clear()
    store.CATEGORICAL_CONGLOMERATE = {'hr': [], 'o2': [], 'temp': [], 'elevation': []}


# ── Eval fixtures ─────────────────────────────────────────────────────────────
# These use store.Sensor (the actual Pydantic model) instead of plain dicts.
# response_report() calls .model_dump() on each item in SHORT_TERM_POOL,
# so plain dicts would crash with AttributeError. store.Sensor fixes that.

_HEALTHY_TIME = datetime(2026, 6, 22, 12, 0, 0)
_HYPOXIA_TIME = datetime(2026, 6, 22, 12, 5, 0)

@pytest.fixture
def mock_healthy_vitals():
    """Injects safe, normal vitals into the store."""
    packet = store.Sensor(
        time=_HEALTHY_TIME,
        hr=72,
        o2=98.0,
        elevation=100.0,
        temp=37.0,
    )
    store.SHORT_TERM_POOL.append(packet)
    store.longtrends(packet)
    store.shorttrends()
    yield


@pytest.fixture
def mock_hypoxia_crisis():
    """Injects a dangerous low-oxygen reading into the store."""
    packet = store.Sensor(
        time=_HYPOXIA_TIME,
        hr=110,
        o2=82.0,
        elevation=100.0,
        temp=37.0,
    )
    store.SHORT_TERM_POOL.append(packet)
    store.longtrends(packet)
    store.shorttrends()
    yield