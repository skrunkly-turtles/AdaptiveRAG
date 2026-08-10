"""
Test 6 from the mentor's spec: consistency. Feed identical input twice,
digest and guards must be byte-identical.

Model-call consistency (run the same input 5 times, count agreement) needs
a live or mocked model and isn't included here -- see section 6 of the spec,
which explicitly scopes that part to a small manual run, not the automated
pytest suite.
"""
from get_data1 import compute_stats
from firefighters import ff1, ff2, ff3


def test_compute_stats_deterministic():
    values = [10, 20, None, 40, 55.5]
    r1 = compute_stats(values, expected_n=6)
    r2 = compute_stats(values, expected_n=6)
    assert r1 == r2


def test_evaluate_guards_deterministic():
    reading = {"hr": 300, "o2": 50}
    thresholds = {"hr": [40, 230], "o2": [93, 100]}
    r1 = ff1.evaluate_guards(reading, thresholds)
    r2 = ff1.evaluate_guards(reading, thresholds)
    assert r1 == r2


def test_evaluate_guards_identical_across_ff_modules():
    """ff1 and ff3 each have their own copy of evaluate_guards -- confirm
    they still agree on identical input. If a fix lands in one copy and not
    the other, this is what catches the drift."""
    reading = {"hr": 300}
    thresholds = {"hr": [40, 230]}
    assert ff1.evaluate_guards(reading, thresholds) == ff3.evaluate_guards(reading, thresholds)
    assert ff1.evaluate_guards(reading, thresholds) == ff2.evaluate_guards(reading, thresholds)