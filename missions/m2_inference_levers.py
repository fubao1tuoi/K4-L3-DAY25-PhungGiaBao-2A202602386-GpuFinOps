"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing
from finops import sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def reasoning_budget(rows, cap_fraction: float = 0.10) -> dict:
    """Measure reasoning cost/energy and estimate the effect of a traffic cap.

    The dataset already labels reasoning traffic.  If it is below the cap, the
    counterfactual deliberately reports zero savings rather than inventing a
    model/routing change.  Energy uses the lab's documented 80x multiplier.
    """
    groups = {
        "reasoning": {"requests": 0, "tokens": 0, "cost_usd": 0.0, "energy_wh": 0.0},
        "standard": {"requests": 0, "tokens": 0, "cost_usd": 0.0, "energy_wh": 0.0},
    }
    for r in rows:
        is_reasoning = bool(int(num(r["is_reasoning"])))
        key = "reasoning" if is_reasoning else "standard"
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cost = pricing.request_cost(
            inp, out, pin, pout,
            cached_in=int(num(r["cached_input_tokens"])),
            batch=bool(int(num(r["is_batch"]))),
        )
        groups[key]["requests"] += 1
        groups[key]["tokens"] += inp + out
        groups[key]["cost_usd"] += cost
        groups[key]["energy_wh"] += sustainability.wh_per_query(
            inp + out, is_reasoning=is_reasoning
        )

    total_requests = sum(g["requests"] for g in groups.values())
    total_cost = sum(g["cost_usd"] for g in groups.values())
    total_energy = sum(g["energy_wh"] for g in groups.values())
    reasoning = groups["reasoning"]
    share = reasoning["requests"] / total_requests if total_requests else 0.0
    # The supplied traffic is already compliant. A real policy would route only
    # excess requests after a quality/complexity gate; no such signal is in CSV.
    excess_requests = max(0, reasoning["requests"] - int(total_requests * cap_fraction))
    for g in groups.values():
        g["cost_usd"] = round(g["cost_usd"], 4)
        g["energy_wh"] = round(g["energy_wh"], 2)
    return {
        "groups": groups,
        "cap_fraction": cap_fraction,
        "reasoning_request_pct": round(share * 100, 2),
        "reasoning_cost_pct": round(reasoning["cost_usd"] / total_cost * 100, 2) if total_cost else 0.0,
        "reasoning_energy_pct": round(reasoning["energy_wh"] / total_energy * 100, 2) if total_energy else 0.0,
        "excess_requests": excess_requests,
        "cap_cost_savings_usd": 0.0,
        "cap_energy_savings_wh": 0.0,
        "cap_status": "already_below_cap" if excess_requests == 0 else "routing_signal_required",
    }


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    reasoning = reasoning_budget(rows)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        rg = reasoning["groups"]["reasoning"]
        print("\nReasoning budget (10% request cap):")
        print(f"  traffic={reasoning['reasoning_request_pct']:.2f}%  "
              f"cost={reasoning['reasoning_cost_pct']:.2f}%  "
              f"energy={reasoning['reasoning_energy_pct']:.2f}%")
        print(f"  reasoning=${rg['cost_usd']:.2f}/day, {rg['energy_wh']:.2f} Wh/day")
        print(f"  status={reasoning['cap_status']}  cap savings=$0.00, 0.00 Wh")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_budget": reasoning,
    }


if __name__ == "__main__":
    run()
