"""
Test 2 from the mentor's spec: guard timing -- where off-by-one errors live.

Tests evaluate_guards() exactly where it actually lives -- inline in each
ff module -- rather than a separately-extracted copy. Parametrized across
ff1 and ff3 so both copies are checked (they should be identical; if a fix
lands in one and not the other, this catches the drift).

Importing ff1/ff3 directly means their real imports (ollama, memory_manager,
comms) have to succeed too. This project's ollama.py / memory_manager.py /
comms.py are lightweight test-only stand-ins for exactly that reason -- see
each file's docstring. evaluate_guards itself never touches any of them.

NOTE on coverage: same gaps as before -- no rate-of-rise guard, no permanent
sensor-death guard exist in the code yet. Skipped, not faked.
"""
import pytest
from firefighters import ff1, ff2, ff3

IMPLEMENTATIONS = [
    pytest.param(ff1.evaluate_guards, id="ff1"),
    pytest.param(ff2.evaluate_guards, id="ff2"),
    pytest.param(ff3.evaluate_guards, id="ff3"),
]


@pytest.mark.parametrize("evaluate_guards", IMPLEMENTATIONS)
def test_fires_on_exact_threshold_row(evaluate_guards):
    thresholds = {"hr": [40, 230]}
    at_bound = evaluate_guards({"hr": 230}, thresholds)
    assert at_bound == {}, "230 is AT the bound, not over it -- confirm this is intended"

    just_over = evaluate_guards({"hr": 231}, thresholds)
    assert just_over != {}
    assert just_over["warnings"]["hr"] == 231


@pytest.mark.parametrize("evaluate_guards", IMPLEMENTATIONS)
def test_fires_on_lower_bound_crossing(evaluate_guards):
    thresholds = {"o2": [93, 100]}
    assert evaluate_guards({"o2": 93}, thresholds) == {}
    fired = evaluate_guards({"o2": 92}, thresholds)
    assert fired["warnings"]["o2"] == 92


@pytest.mark.parametrize("evaluate_guards", IMPLEMENTATIONS)
def test_in_range_does_not_fire(evaluate_guards):
    thresholds = {"hr": [40, 230], "o2": [93, 100]}
    assert evaluate_guards({"hr": 80, "o2": 98}, thresholds) == {}


@pytest.mark.parametrize("evaluate_guards", IMPLEMENTATIONS)
def test_missing_value_does_not_crash_or_fire(evaluate_guards):
    thresholds = {"hr": [40, 230]}
    assert evaluate_guards({"hr": None}, thresholds) == {}


@pytest.mark.parametrize("evaluate_guards", IMPLEMENTATIONS)
def test_multiple_simultaneous_violations(evaluate_guards):
    thresholds = {"hr": [40, 230], "o2": [93, 100]}
    fired = evaluate_guards({"hr": 300, "o2": 50}, thresholds)
    assert set(fired["warnings"].keys()) == {"hr", "o2"}


def test_each_ff_has_independent_det_warnings():
    """Sanity check that each module's own DET_WARNINGS dict is intact and
    independent -- guards against accidental cross-import sharing."""
    assert "hr" in ff1.DET_WARNINGS
    assert "hr" in ff2.DET_WARNINGS
    assert "hr" in ff3.DET_WARNINGS
    assert ff1.DET_WARNINGS is not ff3.DET_WARNINGS
    assert ff2.DET_WARNINGS is not ff1.DET_WARNINGS


@pytest.mark.skip(reason=(
    "No rate-of-rise guard exists yet (spec wants: rising at 12C/min fires, "
    "8C/min does not). evaluate_guards only checks instantaneous bounds, not "
    "rate of change across readings. Needs a rate calculation built first."
))
def test_rate_of_rise_guard_not_yet_implemented():
    pass


@pytest.mark.skip(reason=(
    "No permanent sensor-death guard/masking exists yet. pool_maker.py logs "
    "every reading as-is with no 150C-and-above-stays-dead rule -- the whole "
    "masking mechanism from spec section 4.3 isn't implemented anywhere in "
    "the real pipeline yet, only in the standalone fire-data generator."
))
def test_sensor_death_guard_not_yet_implemented():
    pass