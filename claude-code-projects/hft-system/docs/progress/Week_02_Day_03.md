# Week 2 Day 3 — Imbalance Metrics

## Log

* **Goal:** Compute total bid/ask volume per symbol and print imbalance with sign
* **Completed:** `computeTotalBidVolume`, `computeTotalAskVolume`, `computeImbalance` implemented on `OrderBook`; `Market::printImbalance` formats and prints per-symbol output; called every 100 messages in `main.cpp`; added `bookUpdated` flag (set on `addOrder`/`executeOrder`, reset after print) so imbalance only prints when book changed; added `lastImbalance_` sentinel so imbalance only prints when value actually shifts
* **Expected Output Met?** Yes
* **Blockers:** Bugs fixed:
  1. `computeImbalance` returned `uint64_t` — underflows silently when ask > bid; changed to `int64_t` with explicit casts
  2. `u_int64_t` (non-standard) in `order_book.h` — replaced with `uint64_t`
  3. `market.cpp` called `it->second.printImbalance()` on `OrderBook` which had no such method — moved formatted output into `Market::printImbalance`
  4. Stale `#include "main.h"` in `main.cpp` (file never existed) — removed
  5. `printImbalance` was `const` but needed to call `resetBookUpdated()` — dropped `const` on both declaration and definition
* **Key Learning:** Unsigned underflow is silent — always cast to signed before subtracting volume metrics. `const` on a method propagates to all members it touches; if you need to mutate state (reset a flag) the method can't be const. Gate prints on both book-changed AND value-changed to avoid log noise.
* **Sample Output:**
```
[100] ARGX | BidVol: 2000 AskVol: 2400 Imbalance: -400
[300] ARGX | BidVol: 2400 AskVol: 2400 Imbalance: +0
[1600] ARGX | BidVol: 2730 AskVol: 3341 Imbalance: -611
Processed 2000 messages.
```
* **Time Spent:** ~1 session
* **Tomorrow First Step:** Day 4 — emit (tick, imbalance, mid-price) to CSV from C++, plot imbalance vs price in Python
