# tests/conftest.py
import pytest
import store
from pydantic import BaseModel

# Mocking the data structure you might have in store.py
# Adjust these models to match whatever you actually have inside store.py
class MockDataPoint(BaseModel):
    time: str
    heart_rate: float
    oxygen: float
    elevation: float
    temperature: float

@pytest.fixture
def mock_healthy_vitals():
    """Injects completely stable, healthy vitals into the store."""
    store.SHORT_TERM_POOL = [
        MockDataPoint(time="10:00:00", heart_rate=72.0, oxygen=98.0, elevation=1500.0, temperature=36.5),
        MockDataPoint(time="10:00:02", heart_rate=74.0, oxygen=98.5, elevation=1501.0, temperature=36.6),
        MockDataPoint(time="10:00:04", heart_rate=71.0, oxygen=99.0, elevation=1500.0, temperature=36.5),
    ]
    # Match the key structure expected by your prompt for trends
    store.SHORT_TERM_TRENDS = {
        "heart_rate": MockDataPoint(time="avg", heart_rate=72.3, oxygen=0, elevation=0, temperature=0),
        "oxygen": MockDataPoint(time="avg", heart_rate=0, oxygen=98.5, elevation=0, temperature=0)
    }
    yield
    # Cleanup after test finishes
    store.SHORT_TERM_POOL.clear()
    store.SHORT_TERM_TRENDS.clear()

@pytest.fixture
def mock_hypoxia_crisis():
    """Injects data representing a severe drop in oxygen at high altitude."""
    store.SHORT_TERM_POOL = [
        MockDataPoint(time="12:00:00", heart_rate=95.0, oxygen=92.0, elevation=4000.0, temperature=36.2),
        MockDataPoint(time="12:00:02", heart_rate=110.0, oxygen=88.0, elevation=4005.0, temperature=36.1),
        MockDataPoint(time="12:00:04", heart_rate=125.0, oxygen=82.0, elevation=4010.0, temperature=36.0),
    ]
    store.SHORT_TERM_TRENDS = {
        "oxygen": MockDataPoint(time="trend", heart_rate=0, oxygen=-5.0, elevation=0, temperature=0) # dropping fast
    }
    yield
    store.SHORT_TERM_POOL.clear()
    store.SHORT_TERM_TRENDS.clear()