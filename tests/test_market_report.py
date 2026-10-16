import pytest
from fba_trends.market_report import Economics


def test_economics():
    result = Economics(30,8,4.5,4,3,1,0.5).evaluate()
    assert result["unit_profit"] == 9
    assert result["net_margin_pct"] == 30
    assert result["evidence_status"] == "scenario_only"


def test_negative_cost():
    with pytest.raises(ValueError):
        Economics(10,-1,0,0,0,0,0).evaluate()
