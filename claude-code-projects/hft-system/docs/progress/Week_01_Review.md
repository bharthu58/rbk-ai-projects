# Week 1 Review

## ✅ What Works
- Binary ITCH file reader: correctly strips 2-byte big-endian length prefix and returns message body
- `'A'` (Add Order) parsing: all fields decoded correctly (order_id, side, shares, price, stock)
- Per-symbol order book: `Market` routes orders to the correct `OrderBook` by symbol
- Top-of-book printing: best bid (`rbegin()`), best ask (`begin()`), spread — printed every 100 messages with counter prefix
- Replay engine: processes 2000 `'A'` messages without crash

## ❌ What Doesn't
- No cancel, amend, or execute handling — `'E'`, `'D'`, `'X'`, `'U'` are all dropped or stubbed
- Book is purely additive: orders are never removed or reduced, so price discovery is not realistic
- No order-id lookup map — cannot map executions or cancels back to existing orders
- `main.cpp` filters to `'A'` only before the parser, so non-add messages never reach `parseMessage`

## ⚠️ Biggest Mistake
- `count % 100` without `== 0`: truthy for all non-multiples, causing flooded output on every message instead of every 100
- Did not think through per-symbol book routing upfront — treated it as a global book initially

## 🧠 Key Insight
- With add-only messages, spread can only **tighten** (new orders improving best bid/ask) or stay the same — spread widening requires a level to be removed, which needs cancel/execute messages
- A crossed book (bid >= ask) would signal a parsing bug (wrong offset, wrong endianness, wrong side byte) — currently unguarded

## 🔧 System Gaps
- No order reference map (`order_id → Order`) — required for Week 2 execute/cancel handling
- No crossed/locked book detection
- No validation that parsed prices and shares are realistic (unverified assumption)
- Confidence in correctness: **75%** — risk areas are output formatting and unverified field offsets

## 📈 Performance
- Time taken: ~4 days of 2–3 hr sessions
- Bottlenecks: none at current scale; `std::map` and `std::vector` per price level will become bottlenecks at full feed volume

## 🎯 Adjustments for Week 2
- Add `unordered_map<uint64_t, Order>` order reference map before touching execute parsing
- Process all message types in `main.cpp` (remove `'A'`-only filter)
- Implement `'E'` (Execute) parsing: extract order_id + executed shares, reduce/remove from book
- Add crossed book assertion after every update
