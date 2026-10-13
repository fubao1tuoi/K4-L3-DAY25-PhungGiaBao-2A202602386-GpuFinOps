"""Extension 5 — carbon-aware scheduling for interruptible GPU jobs.

Run: python missions/m3_carbon_aware.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from finops import sustainability
from missions._common import load_csv, num, catalog_by_type

BASELINE_REGION = "us-east-1"


def run(verbose: bool = True) -> dict:
    jobs = [r for r in load_csv("workloads.csv") if bool(int(num(r["interruptible"])))]
    catalog = catalog_by_type()
    regions = []
    total_wh = 0.0
    job_rows = []

    for job in jobs:
        gpu_hours = num(job["hours_per_day"]) * num(job["days"]) * num(job["num_gpus"])
        energy_wh = gpu_hours * num(catalog[job["gpu_type"]]["watts"])
        total_wh += energy_wh
        job_rows.append({
            "job_id": job["job_id"], "gpu_type": job["gpu_type"],
            "gpu_hours": round(gpu_hours, 1), "energy_kwh": round(energy_wh / 1000.0, 2),
        })

    for region in sustainability.REGION_CARBON:
        regions.append({
            "region": region,
            "usd_per_kwh": sustainability.REGION_PRICE_KWH[region],
            "gco2_per_kwh": sustainability.REGION_CARBON[region],
            "electricity_cost_usd": round(sustainability.energy_cost_usd(total_wh, region), 2),
            "carbon_kg": round(sustainability.carbon_g(total_wh, region) / 1000.0, 2),
        })

    cleanest = min(regions, key=lambda r: r["gco2_per_kwh"])
    cheapest = min(regions, key=lambda r: r["usd_per_kwh"])
    baseline = next(r for r in regions if r["region"] == BASELINE_REGION)
    carbon_saved_kg = baseline["carbon_kg"] - cleanest["carbon_kg"]
    carbon_saved_pct = carbon_saved_kg / baseline["carbon_kg"] * 100 if baseline["carbon_kg"] else 0.0
    result = {
        "jobs": job_rows, "total_energy_kwh": round(total_wh / 1000.0, 2), "regions": regions,
        "baseline_region": BASELINE_REGION, "cleanest_region": cleanest["region"],
        "cheapest_region": cheapest["region"], "baseline_carbon_kg": baseline["carbon_kg"],
        "optimized_carbon_kg": cleanest["carbon_kg"],
        "carbon_saved_kg": round(carbon_saved_kg, 2), "carbon_saved_pct": round(carbon_saved_pct, 1),
    }

    if verbose:
        print("== Extension 5: Carbon-aware Scheduling ==")
        print(f"interruptible jobs={len(jobs)}  energy={result['total_energy_kwh']:,.2f} kWh")
        print(f"{'region':18}{'$/kWh':>9}{'gCO2/kWh':>12}{'power cost':>14}{'carbon kg':>13}")
        for row in regions:
            print(f"{row['region']:18}{row['usd_per_kwh']:>9.3f}{row['gco2_per_kwh']:>12}"
                  f"${row['electricity_cost_usd']:>12,.2f}{row['carbon_kg']:>13,.2f}")
        print(f"cleanest={cleanest['region']}; cheapest={cheapest['region']}")
        print(f"carbon: {baseline['carbon_kg']:,.2f} -> {cleanest['carbon_kg']:,.2f} kgCO2e "
              f"({result['carbon_saved_pct']:.1f}% reduction)")
        print("trade-off: region choice must also consider user latency and data residency")
    return result


if __name__ == "__main__":
    run()
