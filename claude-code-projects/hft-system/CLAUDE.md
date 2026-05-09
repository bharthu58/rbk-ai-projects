# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
cd build && cmake .. && make   # Configure and build
./build/hft_system             # Run (expects data/12302019.NASDAQ_ITCH50 relative to cwd)
```

The binary must be run from the repo root so the hardcoded `data/` path resolves correctly.

## Architecture

This is a NASDAQ ITCH 5.0 binary market data parser in C++17. The protocol spec is in `doc/NQTVITCHSpecification.pdf`.

**Data flow:**

```
ITCH binary file → FileReader → ITCHParser → Market → OrderBook (per symbol)
```

- `src/utils/file_reader.{h,cpp}` — Reads length-prefixed binary messages from an ITCH feed file. Each message is preceded by a 2-byte big-endian length field; `FileReader` strips it and returns the raw message body.
- `src/utils/itch_utils.{h,cpp}` — Big-endian decode helpers (`readUint16`, `readUint32`, `readUint64`) under the `itch` namespace. Take `const char*` pointing directly to the field offset. Used by the parser via `using namespace itch`.
- `src/parser/itch_parser.{h,cpp}` — Dispatches on the first byte (message type). Handles `'A'` (Add Order) with full field decoding; `'E'` (Order Executed) is a stub; all others fall through to a default case.
- `src/orderbook/order_book.{h,cpp}` — `OrderBook` per symbol; `std::map` bids/asks; `addOrder`, `printTopOfBook`.
- `src/orderbook/market.{h,cpp}` — `Market` class; `unordered_map<string, OrderBook>`; routes orders by symbol.
- `src/main.cpp` — Filters to first 10 `'A'` messages; calls `market.printTopOfBook("ARGX")`.

**Key protocol details (ITCH 5.0):**
- Messages are framed with a 2-byte big-endian length prefix (stripped by `FileReader` before passing to the parser).
- Message type is always the first byte of the body.
- Fields within messages are big-endian and fixed-width (no delimiters).
- The test data file is `data/12302019.NASDAQ_ITCH50` (NASDAQ feed from 2019-12-30).