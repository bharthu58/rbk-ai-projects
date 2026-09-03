# Week 2 Day 5 — Buffer Day (Refactor + Assertions + 50k Replay)

## Plan

Buffer day — no new feature. Goals:
1. Clean and refactor logging
2. Add assertions
3. Replay 50k messages
4. Observe behavior carefully

## Log

* **Goal:** Harden the codebase before moving to Week 3 — silence noisy debug output, add correctness guards, expand replay window, and observe what breaks
* **Completed:**
  - Gated all `executeOrder` Before/After prints and unknown-message-type print behind `#ifdef DEBUG`
  - Removed dead commented-out debug block in `itch_parser.cpp`
  - Added assertions: `execution.shares > 0` (market), `order.price > 0` and `order.side == 'B'||'S'` (order_book)
  - Fixed real bug: `it->shares <= 0` on `uint32_t` was always false — changed to `== 0`
  - Added `FileReader` destructor with `fclose()`
  - Extracted `totalVolume(side)` static helper — eliminated duplicate bid/ask volume loops
  - `printTopOfBook()` now takes symbol param; output is `SYMBOL | BID: x | ASK: x | SPREAD: x`
  - CSV extended: added `best_bid`, `best_ask`, `spread` columns
  - Fixed `getMid()`: returns available side when book is one-sided (was halving price when ask=0)
  - Skip CSV rows when both sides are 0
  - Added `[CROSSED BOOK]` detection: logs to stderr with symbol, tick, msg type, bid, ask, spread
  - Bumped replay cap to 50k messages
* **Expected Output Met?** Yes — 50k messages processed, no crashes, no assertion fires, 74ms wall time
* **Bugs Fixed:**
  1. `getMid()` returning `bestBid/2` when ask side empty — now returns `bestBid` directly
  2. `uint32_t <= 0` dead comparison in `executeOrder` — changed to `== 0`
  3. `market.cpp` was computing mid inline as `(bid+ask)/2` instead of calling `getMid()` — fixed to use `getMid()`
* **Crossed Book Observation:**
  - 692 crossed-book events detected across 50k messages
  - All triggered by `msg=A` (Add Order) — never by executions
  - Identical inversion every time: `bid=19.96 ask=19.95 spread=-0.01`
  - First appears at tick 6643 and persists to end — a stale resting order that was never cancelled
  - **Root cause:** We are not processing `'D'` (Delete) or `'U'` (Replace) messages; a cancel that should have resolved the cross is being silently dropped
  - Not fixing now — will resolve when Delete/Replace parsing is implemented
* **Key Learning:** One-sided mid is a silent data quality issue — the halved price looked plausible ($9.97 vs $19.95) and only became obvious at scale. Always check both sides exist before computing any derived price metric.
* **Sample Output:**
```
Processed 50000 messages.

[CROSSED BOOK] EQNR tick=6643 msg=A bid=19.96 ask=19.95 spread=-0.01
[CROSSED BOOK] EQNR tick=6644 msg=A bid=19.96 ask=19.95 spread=-0.01
[CROSSED BOOK] EQNR tick=6656 msg=A bid=19.96 ask=19.95 spread=-0.01
[CROSSED BOOK] EQNR tick=6659 msg=A bid=19.96 ask=19.95 spread=-0.01
[CROSSED BOOK] EQNR tick=6670 msg=A bid=19.96 ask=19.95 spread=-0.01

msg_count,mid_price,imbalance,best_bid,best_ask,spread
189,19.95,3000,19.95,0,0
192,19.95,6000,19.95,0,0
193,19.965,3000,19.95,19.98,0.03
195,19.965,0,19.95,19.98,0.03
768,19.965,100,19.95,19.98,0.03
...
49966,19.955,-205700,19.96,19.95,-0.01
49967,19.955,-205200,19.96,19.95,-0.01
```
* **Time Spent:** ~1 session
* **Tomorrow First Step:** Week 2 Day 6 (Weekly Review) — answer: what works, what's broken, biggest mistake, correctness confidence %, unverified assumptions
