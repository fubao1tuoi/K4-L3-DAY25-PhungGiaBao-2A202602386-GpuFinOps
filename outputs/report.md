# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Lowest-carbon region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Extension 4 — Reasoning Budget

| Traffic | Requests | Tokens | Cost/day | Energy/day |
|---|---:|---:|---:|---:|
| Standard | 2,199 | 6,291,871 | $7.09 | 1,887.56 Wh |
| Reasoning | 201 | 1,241,156 | $1.40 | 29,787.74 Wh |

Reasoning represents **8.38%** of requests, **16.46%** of optimized inference cost, and **94.04%** of estimated energy. The dataset is already below the proposed 10% request cap, so the measured cap savings are **$0.00 and 0.00 Wh**. No artificial rerouting savings are claimed.

**Policy:** enable reasoning only for high-complexity tasks or when a calibrated confidence score is below threshold; monitor quality before lowering the cap.

## Extension 5 — Carbon-aware Scheduling

Interruptible workloads consume an estimated **1,789.00 kWh** over the `days` recorded in `workloads.csv`.

| Region | USD/kWh | gCO2/kWh | Electricity cost | Carbon (kgCO2e) |
|---|---:|---:|---:|---:|
| us-east-1 | $0.120 | 380 | $214.68 | 679.82 |
| us-west-2 | $0.070 | 120 | $125.23 | 214.68 |
| europe-north1 | $0.090 | 30 | $161.01 | 53.67 |
| europe-central2 | $0.180 | 660 | $322.02 | 1,180.74 |
| us-east-wa | $0.055 | 90 | $98.39 | 161.01 |

Moving eligible jobs from `us-east-1` to `europe-north1` reduces estimated emissions from **679.82** to **53.67 kgCO2e**, saving **626.15 kgCO2e (92.1%)**. The cheapest electricity region is `us-east-wa`; it differs from the cleanest region, so the final choice must also account for latency and data residency.

## Analysis and prioritized actions

`gpu-h100-4` and `gpu-a10g-1` show high GPU activity but MFU below 30%. GPU-Util measures time with active work, not useful FLOP throughput; memory stalls, I/O waits, and inefficient kernels can therefore create a costly utilization lie.

1. Apply Spot to checkpointable jobs and Reserved pricing only to steady workloads; this is the largest measured savings lever.
2. Enforce the 10% reasoning budget with a quality-aware routing gate and alert on both cost and energy share.
3. Shut down idle GPUs, right-size low-MFU deployments, and schedule interruptible training in a lower-carbon region when latency and governance permit.
