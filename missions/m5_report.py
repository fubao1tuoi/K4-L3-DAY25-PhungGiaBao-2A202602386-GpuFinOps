"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m3_carbon_aware

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    carbon = m3_carbon_aware.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust)
    reasoning = r2["reasoning_budget"]
    rg = reasoning["groups"]["reasoning"]
    std = reasoning["groups"]["standard"]
    region_lines = [
        f"| {r['region']} | ${r['usd_per_kwh']:.3f} | {r['gco2_per_kwh']} | "
        f"${r['electricity_cost_usd']:,.2f} | {r['carbon_kg']:,.2f} |"
        for r in carbon["regions"]
    ]
    extension_md = [
        "", "## Extension 4 — Reasoning Budget", "",
        "| Traffic | Requests | Tokens | Cost/day | Energy/day |",
        "|---|---:|---:|---:|---:|",
        f"| Standard | {std['requests']:,} | {std['tokens']:,} | ${std['cost_usd']:,.2f} | {std['energy_wh']:,.2f} Wh |",
        f"| Reasoning | {rg['requests']:,} | {rg['tokens']:,} | ${rg['cost_usd']:,.2f} | {rg['energy_wh']:,.2f} Wh |",
        "",
        f"Reasoning represents **{reasoning['reasoning_request_pct']:.2f}%** of requests, "
        f"**{reasoning['reasoning_cost_pct']:.2f}%** of optimized inference cost, and "
        f"**{reasoning['reasoning_energy_pct']:.2f}%** of estimated energy. The dataset is "
        "already below the proposed 10% request cap, so the measured cap savings are "
        "**$0.00 and 0.00 Wh**. No artificial rerouting savings are claimed.",
        "",
        "**Policy:** enable reasoning only for high-complexity tasks or when a calibrated "
        "confidence score is below threshold; monitor quality before lowering the cap.",
        "", "## Extension 5 — Carbon-aware Scheduling", "",
        f"Interruptible workloads consume an estimated **{carbon['total_energy_kwh']:,.2f} kWh** "
        "over the `days` recorded in `workloads.csv`.", "",
        "| Region | USD/kWh | gCO2/kWh | Electricity cost | Carbon (kgCO2e) |",
        "|---|---:|---:|---:|---:|", *region_lines, "",
        f"Moving eligible jobs from `{carbon['baseline_region']}` to `{carbon['cleanest_region']}` "
        f"reduces estimated emissions from **{carbon['baseline_carbon_kg']:,.2f}** to "
        f"**{carbon['optimized_carbon_kg']:,.2f} kgCO2e**, saving "
        f"**{carbon['carbon_saved_kg']:,.2f} kgCO2e ({carbon['carbon_saved_pct']:.1f}%)**. "
        f"The cheapest electricity region is `{carbon['cheapest_region']}`; it differs from the "
        "cleanest region, so the final choice must also account for latency and data residency.",
        "", "## Analysis and prioritized actions", "",
        "`gpu-h100-4` and `gpu-a10g-1` show high GPU activity but MFU below 30%. "
        "GPU-Util measures time with active work, not useful FLOP throughput; memory stalls, "
        "I/O waits, and inefficient kernels can therefore create a costly utilization lie.",
        "",
        "1. Apply Spot to checkpointable jobs and Reserved pricing only to steady workloads; "
        "this is the largest measured savings lever.",
        "2. Enforce the 10% reasoning budget with a quality-aware routing gate and alert on both "
        "cost and energy share.",
        "3. Shut down idle GPUs, right-size low-MFU deployments, and schedule interruptible "
        "training in a lower-carbon region when latency and governance permit.",
    ]
    md += "\n" + "\n".join(extension_md)
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", newline="\n", encoding="utf-8") as f:
        f.write(md + "\n")
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"))

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1),
            "reasoning_budget": reasoning, "carbon_aware": carbon}


if __name__ == "__main__":
    run()
