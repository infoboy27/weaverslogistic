import numpy as np
import pandas as pd

from fba_trends.trends import anomalous_weeks


def _universe(holiday_lift: float, glitch: bool) -> dict[str, pd.Series]:
    """20 gift-like keywords: every December lifts them; optionally a market-wide glitch in spring 2026."""
    idx = pd.date_range("2022-01-02", "2026-10-11", freq="W-SUN")
    rng = np.random.default_rng(0)
    out = {}
    for i in range(20):
        v = 40 + rng.normal(0, 2, len(idx))
        v = np.where(idx.month == 12, v * holiday_lift, v)
        if glitch:
            v = np.where((idx >= "2026-03-22") & (idx <= "2026-06-21"), v * 4, v)
        out[f"k{i}"] = pd.Series(v, index=idx)
    return out


def test_yearly_holiday_lift_is_not_a_glitch():
    data = _universe(holiday_lift=1.5, glitch=False)
    assert len(anomalous_weeks(data.get, list(data))) == 0


def test_market_wide_jump_is_a_glitch():
    data = _universe(holiday_lift=1.5, glitch=True)
    weeks = anomalous_weeks(data.get, list(data))
    assert pd.Timestamp("2026-04-12") in weeks and pd.Timestamp("2025-12-14") not in weeks
