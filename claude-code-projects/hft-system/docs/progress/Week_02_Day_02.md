# Week 2 Day 2 — Trades + Book Sync

## Log

* **Goal:** Update the order book on execution — reduce shares or remove order if fully filled
* **Completed:** `order_map_` (`orders_`) added to `Market`; `executeOrder(const Execution&)` implemented in `market.cpp`; `executeOrder(const Order&)` implemented in `order_book.cpp`; before/after state printed on each execution
* **Expected Output Met?** Yes
* **Blockers:** Three bugs fixed in user-written code:
  1. `market.cpp` line 9: missing `)` closing the `if` condition
  2. Missing `#include <iostream>` for `std::cerr`
  3. `uint32_t shares < 0` is always false (unsigned) — replaced with pre-subtraction guard `execution.shares > order.shares`
  4. `order_book.cpp`: `for(auto book_order:...)` iterated by copy — mutations were lost; replaced with `std::find_if` + iterator erase
* **Key Learning:** `uint32_t` underflow wraps to a huge positive number silently — always guard before subtracting unsigned values. Erase-remove on a vector of structs requires `operator==` or use `std::find_if` + `erase`.
* **Sample Output:**
```
EXECUTE |  ID: 39411 Shares: 3
Before: BID 5.9000 (700 shares)
After:  BID 5.9000 (697 shares)
EXECUTE |  ID: 46917 Shares: 3
Before: BID 1872.0200 (20 shares)
After:  BID 1872.0200 (17 shares)
EXECUTE |  ID: 44261 Shares: 20
Before: ASK 50.5200 (600 shares)
After:  ASK 50.5200 (580 shares)
EXECUTE |  ID: 30090 Shares: 1000
Before: BID 19.9600 (1000 shares)
After:  BID 19.9600 (0 shares — removed)
EXECUTE |  ID: 52577 Shares: 50
Before: ASK 50.5300 (600 shares)
After:  ASK 50.5300 (550 shares)
```
* **Time Spent:** ~1 session
* **Tomorrow First Step:** Day 3 — compute total bid/ask volume per symbol, print imbalance
