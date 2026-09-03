# Week 1 - Day 3

## 🎯 Goal
- Parse Add Order (`'A'`) messages with full field decoding
- Build a per-symbol order book
- Print top of book with correct price formatting

---

## ✅ What I Did
- Implemented `itch_utils` (`readUint16/32/64`, `toPrice`) for big-endian decoding and ITCH price formatting
- Refactored `ITCHParser::parseAddOrder` to fully decode all fields: order ID, side, shares, stock symbol, price
- Built `Order` struct and `OrderBook` class (bids/asks as `std::map`, `printTopOfBook`)
- Built `Market` class — `unordered_map<string, OrderBook>` — to separate books per symbol, fixing incorrect cross-symbol spread
- Updated `main.cpp` to filter only `'A'` messages and print top of book for `ARGX`
- Added `toPrice()` helper; `printTopOfBook` now prints `$160.5800` style with spread in dollars
- Configured VS Code IntelliSense via `.vscode/c_cpp_properties.json` pointing to `build/compile_commands.json`
- Set up Obsidian vault integration with Claude Code memory

---

## ❌ What Failed
- Initial `OrderBook` was shared across all symbols — spread was garbage (mixing ARGX bids with AZN asks)
- VS Code showing stale buffers when Claude edited files on disk — required manual Revert File

---

## ⚠️ Blockers
- None

---

## 🧠 Key Learnings
- ITCH prices are raw `uint32` with 4 implied decimal places (divide by 10000)
- First ~50 messages in the feed are session setup (`S`, `R`); `A` messages only appear after market open
- Variable declarations inside `case` blocks need braces `{}` in C++ to avoid "jump crosses initialization" error
- VS Code + Claude workflow: never edit in IDE while Claude is writing; use Revert File after each Claude edit

---

## ⏱ Time Spent
- ~2 hours

---

## 📌 Tomorrow's First Step
Turn the system into a stable replay engine with evolving market state:
- Processing 1000+ messages ✅
- Periodic top-of-book output ✅
- Clean decimal prices ✅
- No crashes / garbage values

---

## 🔥 If I only finish ONE thing today:
→ Per-symbol order book with correct top-of-book output
