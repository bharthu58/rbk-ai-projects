# Week 2 Day 4 — Visualization

## Plan

* Emit `(tick, imbalance, mid_price)` rows to `imbalance.csv` from C++ on each imbalance change
* Load CSV in Python, plot imbalance trend + mid-price overlay on dual y-axes

## Expected Output

Graph showing:
- Imbalance trend (bar or line)
- Price movement overlay (line, right axis)

## Reject if:
- Static or flat plot
- Misaligned axes
- CSV is empty or all zeros

## Log

* **Goal:** Emit per-tick imbalance + mid-price to CSV from C++; plot dual-axis chart in Python
* **Completed:**
  - `Market::printImbalance` now accepts `tick` param and writes `tick,mid,imbalance\n` on every ARGX/EQNR book update
  - CSV emitted at `imbalance.csv` with header `msg_count,mid_price,imbalance`
  - `plot_imbalance.py` produces dual y-axis chart (imbalance left, mid price right), saved as `imbalance_plot.png`
  - Switched symbol ARGX → ZJZZT → EQNR after diagnosing low/artificial sample counts
* **Expected Output Met?** Yes — jagged imbalance line with price overlay, dual axes aligned
* **Blockers / Bugs Fixed:**
  1. `market.cpp` missing `#include <fstream>` — `ofstream` was only forward-declared, `<<` operator failed to resolve
  2. Garbled CSV literal `"mid_price,,"` in `printImbalance` — leftover from earlier draft; removed
  3. `main.cpp` wrote `count << ","` unconditionally before calling `printImbalance`; when imbalance unchanged, orphaned count bled into next row — fixed by passing `tick` into `printImbalance` and writing count only when data is emitted
  4. Removed `% 100` sampling gate — now emits on every book update for EQNR
  5. ZJZZT is NASDAQ's test symbol — only bid-side orders in this window, imbalance monotonically increasing; switched to EQNR (real stock, 108 add orders in 5000 ticks)
* **Plot Observation:**
  - **Price behavior:** Mid starts at ~$9.97 (halved — book incomplete, only bids, so mid = bestBid/2). Jumps to ~$19.965 at tick 193 when the first ask arrives. Flat for the rest of the session with only minor tick-level moves (~$19.965–$19.97). Essentially anchored.
  - **Imbalance behavior:** Starts mildly bid-heavy (+3000–6000) for the first ~200 ticks, then flips negative and drifts in a staircase pattern to -105,000 by tick 5000. Jagged step-changes with occasional partial reversals — consistent with large ask orders being placed in bursts.
  - **Any visible relationship:** Imbalance flips negative almost exactly when mid stabilizes (~tick 193). After that, price does not follow the deepening ask pressure — mid stays flat while imbalance diverges. No clear lead-lag in this 5000-tick window. Suggests either (a) the ask orders are far from best ask and don't move mid, or (b) the window is pre-open and price discovery hasn't started yet.
* **Key Signal (EQNR):** Imbalance turns ask-heavy immediately after book completes (~tick 200) and drifts steadily to -105,000 shares by tick 5000 while mid price stays flat at ~$19.97. Classic pre-open ask stacking — market makers loading the sell side with a stable price anchor, consistent with a stock trading near fair value with institutional selling pressure building.
* **Key Learning:** Always write the full CSV row atomically inside the emit function — never split across caller and callee or skipped rows corrupt adjacent ones. Test symbols (ZJZZT prefix) have synthetic one-sided flow; always verify both bid and ask sides exist before trusting imbalance shape.
* **Sample Output:**
```
msg_count,mid_price,imbalance
189,9.975,3000
192,9.975,6000
193,19.965,3000
195,19.965,0
768,19.965,100
775,19.965,0
1324,19.97,1000
1398,19.965,-5000
1409,19.965,-8600
...
4900,19.965,-104900
Processed 5000 messages. (109 EQNR rows)
```
* **Time Spent:** ~1 session
* **Tomorrow First Step:** Week 3 Day 1 — Queue Simulation: model queue position for a limit order, simulate fill time based on order flow ahead
