"""
Tests for lib.stats module.
Verifies statistical accuracy for Wilson CI, normal CDF, chi-square test, and Cohen's h.
"""

from __future__ import annotations

import math
import pytest

from lib.stats import (
    chi_square_test,
    chi_square_to_p_value,
    cohens_h,
    get_z_score,
    normal_cdf,
    wilson_confidence_interval,
)


def test_normal_cdf_exact_values() -> None:
    assert normal_cdf(0.0) == 0.5
    assert math.isclose(normal_cdf(1.95996398454), 0.975, rel_tol=1e-4)
    assert math.isclose(normal_cdf(-1.95996398454), 0.025, rel_tol=1e-4)
    assert normal_cdf(-10.0) < 1e-15
    assert normal_cdf(10.0) > 1 - 1e-15


def test_get_z_score_validation() -> None:
    assert get_z_score(0.90) == 1.645
    assert get_z_score(0.95) == 1.96
    assert get_z_score(0.99) == 2.576
    assert get_z_score(0.999) == 3.291

    with pytest.raises(ValueError, match="Unsupported confidence level"):
        get_z_score(0.85)


def test_wilson_confidence_interval_bounds() -> None:
    zero_case = wilson_confidence_interval(0, 0)
    assert zero_case["proportion"] == 0
    assert zero_case["lower"] == 0
    assert zero_case["upper"] == 0

    ci_50 = wilson_confidence_interval(50, 100, confidence=0.95)
    assert ci_50["proportion"] == 0.5
    assert 0.40 < ci_50["lower"] < 0.42
    assert 0.58 < ci_50["upper"] < 0.60
    assert ci_50["lower"] <= ci_50["proportion"] <= ci_50["upper"]

    # Boundary cases: 0/100 and 100/100
    ci_0 = wilson_confidence_interval(0, 100, confidence=0.95)
    assert ci_0["lower"] == 0.0
    assert ci_0["upper"] > 0.0

    ci_100 = wilson_confidence_interval(100, 100, confidence=0.95)
    assert ci_100["upper"] == 1.0
    assert ci_100["lower"] < 1.0


def test_cohens_h_interpretation() -> None:
    # Identical proportions
    res_zero = cohens_h(0.5, 0.5)
    assert res_zero["h"] == 0.0
    assert res_zero["interpretation"] == "negligible"

    # Small effect
    res_small = cohens_h(0.5, 0.6)
    assert res_small["interpretation"] == "small"

    # Medium effect
    res_medium = cohens_h(0.3, 0.6)
    assert res_medium["interpretation"] in ("medium", "large")

    # Large effect
    res_large = cohens_h(0.1, 0.9)
    assert res_large["h"] >= 0.8
    assert res_large["interpretation"] == "large"


def test_chi_square_test_comparisons() -> None:
    # Empty inputs
    assert chi_square_test([0, 0], [0, 0]) is None

    # Identical distributions
    res_same = chi_square_test([50, 50], [50, 50])
    assert res_same is not None
    assert res_same["chiSquare"] == 0.0
    assert res_same["pValue"] == 1.0
    assert not res_same["significant"]

    # Highly divergent distributions
    res_diff = chi_square_test([90, 10], [10, 90])
    assert res_diff is not None
    assert res_diff["chiSquare"] > 50.0
    assert res_diff["pValue"] < 0.001
    assert res_diff["significant"]

    # Small sample warning
    res_small = chi_square_test([2, 1], [1, 2])
    assert res_small is not None
    assert res_small["warning"] is not None


def test_chi_square_to_p_value_degrees_of_freedom() -> None:
    # df = 1: 3.841 maps to p ~ 0.05
    p_df1 = chi_square_to_p_value(3.841, df=1)
    assert math.isclose(p_df1, 0.05, rel_tol=0.01)

    # df = 2: 5.991 maps to p ~ 0.05
    p_df2 = chi_square_to_p_value(5.991, df=2)
    assert math.isclose(p_df2, 0.05, rel_tol=0.01)

    # df = 3
    p_df3 = chi_square_to_p_value(7.815, df=3)
    assert math.isclose(p_df3, 0.05, rel_tol=0.05)
