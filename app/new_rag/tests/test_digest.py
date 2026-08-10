"""
Test 1 from the mentor's spec: digest arithmetic, pass/fail per check.
Every one must match to the decimal.

NOTE on coverage: the spec's table includes a "slope"/"slope_r2" row (straight
line rising 10C/min -> slope=10.0, slope_r2=1.0). compute_stats() does not
compute slope -- nothing in the current codebase does. That row is skipped
here (see test_slope_not_yet_implemented) rather than faked.
"""
import pytest
from get_data1 import compute_stats


def test_constant_series():
    result = compute_stats([50, 50, 50, 50, 50])
    assert result["variance"] == 0.0
    # spec table calls this "sd" -- compute_stats' "variance" key is actually
    # a population/sample stdev (statistics.stdev), not variance. Naming
    # mismatch worth fixing in get_data1.py at some point, noted separately.
    assert result["mean"] == 50


def test_missing_fraction_six_window_two_missing():
    result = compute_stats([1, 2, None, 4, None, 6], expected_n=6)
    assert result["missing_frac"] == 0.333


def test_all_missing_no_crash():
    result = compute_stats([None, None, None])
    assert result["n"] == 0
    assert result["mean"] is None
    assert result["min"] is None
    assert result["max"] is None


def test_basic_stats_known_values():
    result = compute_stats([10, 20, 30, 40, 50])
    assert result["mean"] == 30
    assert result["median"] == 30
    assert result["min"] == 10
    assert result["max"] == 50


def test_empty_list_no_crash():
    result = compute_stats([])
    assert result["n"] == 0


@pytest.mark.skip(reason=(
    "compute_stats() does not compute slope/slope_r2 -- no rate-of-change "
    "logic exists yet anywhere in the codebase shared so far. Needs to be "
    "built before this row of the spec's table can be tested for real."
))
def test_slope_not_yet_implemented():
    pass