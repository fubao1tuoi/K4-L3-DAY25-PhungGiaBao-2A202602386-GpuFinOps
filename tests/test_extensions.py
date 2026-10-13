import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from missions import m2_inference_levers, m3_carbon_aware


def test_reasoning_budget_is_measured_and_cap_is_honest():
    result = m2_inference_levers.run(verbose=False)["reasoning_budget"]
    assert 0 < result["reasoning_request_pct"] < 10
    assert result["reasoning_energy_pct"] > result["reasoning_request_pct"]
    assert result["cap_status"] == "already_below_cap"
    assert result["cap_cost_savings_usd"] == 0


def test_carbon_aware_scheduling_compares_all_regions():
    result = m3_carbon_aware.run(verbose=False)
    assert len(result["regions"]) == 5
    assert result["cleanest_region"] == "europe-north1"
    assert result["cheapest_region"] == "us-east-wa"
    assert result["carbon_saved_kg"] > 0
    assert result["optimized_carbon_kg"] < result["baseline_carbon_kg"]
