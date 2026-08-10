"""
Test 5 from the mentor's spec: awkward input. Confirm no crash, sensible output.

Non-model parts only (digest + guards). The malformed-JSON row needs a mocked
ollama client and captain1.py to be importable -- not wired up yet, see the
skipped test below for exactly what's missing.
"""
import pytest
from new_rag.get_data1 import compute_stats
from new_rag.firefighters import ff1


def test_sensor_dead_from_row_zero():
    """A metric that's entirely missing across the whole window."""
    result = compute_stats([None] * 10, expected_n=10)
    assert result["n"] == 0
    assert result["missing_frac"] == 1.0
    assert result["mean"] is None


def test_all_sensors_dead_in_one_reading():
    reading = {"sensor_1": None, "sensor_2": None, "sensor_3": None}
    thresholds = {"sensor_1": [0, 65], "sensor_2": [0, 65], "sensor_3": [0, 65]}
    assert ff1.evaluate_guards(reading, thresholds) == {}


def test_single_row_case():
    result = compute_stats([42])
    assert result["n"] == 1
    assert result["mean"] == 42
    assert result["variance"] == 0.0  # single value -> defined as 0, not a crash


def test_window_with_exactly_one_real_reading():
    result = compute_stats([None, None, 42, None], expected_n=4)
    assert result["n"] == 1
    assert result["mean"] == 42
    assert result["missing_frac"] == 0.75


def test_case_where_nothing_ever_happens():
    """Flat/quiet series -- digest well-defined, no guard fires."""
    values = [22.0] * 20
    result = compute_stats(values)
    assert result["variance"] == 0.0

    thresholds = {"sensor_1": [0, 65]}
    for v in values:
        assert ff1.evaluate_guards({"sensor_1": v}, thresholds) == {}


@pytest.mark.skip(reason=(
    "Malformed-JSON recovery needs a mocked ollama client and captain1.py "
    "importable (needs a 'firefighters' package + a planner.py stub to satisfy "
    "its imports). captain1.is_warning()/receive_warn() already wrap "
    "Analysis.model_validate_json() in try/except, so the recovery behavior "
    "likely exists -- this just isn't wired up as an automated test yet."
))
def test_malformed_model_output_recovery():
    pass