# Week 2 Day 1 — Execute Message Parsing

## Log

* **Goal:** Parse `'E'` (Order Executed) messages, extract order_id + executed shares
* **Completed:** `parseOrderExecuted()` implemented in `itch_parser.cpp`; `'E'` case wired into `parseMessage`; `main.cpp` filter updated to pass all message types
* **Expected Output Met?** Yes
* **Blockers:** Two bugs fixed — `case 'E':` missing braces (jump-to-label error); bogus `price` field read beyond message boundary (ITCH `'E'` has no price)
* **Key Learning:** ITCH `'E'` message is 31 bytes total — no price field. Reading past the end gives garbage silently. `'C'` (Order Executed With Price) is the variant that includes price.
* **Time Spent:** ~1 session
* **Sample Output:**
```
[1400] Top of Book:
EXECUTE |  ID: 39411 Shares: 3
[1500] Top of Book:
EXECUTE |  ID: 46917 Shares: 3
[1600] Top of Book:
EXECUTE |  ID: 44261 Shares: 20
[1700] Top of Book:
EXECUTE |  ID: 30090 Shares: 1000
EXECUTE |  ID: 52577 Shares: 50
```
* **Tomorrow First Step:** Day 2 — wire `order_map_` into `Market`, reduce shares on execution, remove order if shares hit 0, print before/after book state
