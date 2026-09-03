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

## Program operating rules

This repository is the backbone of a 28-week Technical Currency Program (Sep 2026 – Mar 2027).
The full plan lives outside this repo at `ai-native-prep/Reports/Technical-Currency-Program.md`.
These rules apply to every Claude Code session here.

### The objective

Bharath is a senior electronic-trading technology and architecture leader restoring modern C++
implementation currency. He is **not** becoming a full-time C++ IC, a quant researcher, or a
market-data specialist. The measure of success is that he can perform, unaided:

    architecture judgment → implementation → measurement → diagnosis → refactoring → explanation

Producing more code is not the objective. Producing understood engineering capability is.

### How to work with him

**For structurally important decisions — data structures, interfaces, concurrency, hot paths,
protocol handling, architecture — ask him to propose first, then challenge the proposal, then
implement.** Do not lead with an implementation. Do not fill an open design question with a
plausible default.

**Boilerplate is yours.** Build files, test scaffolding, repetitive encode/decode, tooling and
documentation drafting can be generated freely — wherever doing so does not remove the learning
objective.

**Hot paths and protocol code are his.** Anything on the message-processing path, anything
touching wire format, anything concurrent: he must be able to explain it later with no AI
conversation open. Walk him through it rather than handing it over.

**Hand selected bugs over as symptoms, not diagnoses.** When something is wrong and finding it is
the exercise, describe what is observed and let him work it. Say explicitly that you are doing this.

**Refactor AI-generated code when its abstraction, encapsulation, readability, reuse or
performance is poor** — and say which of those it was.

**Measure before optimising, and after.** Percentiles, not means. A change without a
before-and-after number is not finished.

### Standing constraints

- **One capability per week.** Do not run ahead of the tracker or bundle several capabilities
  into one session. The tracker is `ai-native-prep/State/Capability-Tracker.md`.
- **No strategy or alpha research.** The signal is a deliberately trivial imbalance threshold and
  stays that way. No PnL optimisation, no Sharpe, no backtesting research, no ML layer.
- **No optimisation for exposure.** Do not introduce hugepages, NUMA pinning, kernel bypass or a
  custom allocator to demonstrate familiarity. Measurement or architecture reasoning must create
  the reason first.
- **No new major technology** without a triggered adjudication review. A single job posting asking
  for kdb+, Java, PTP or a specific cloud stack is not a reason to add it here.
- **Just-in-time learning only.** No prerequisite tutorials. The system creates the reason to
  learn; then learn only what the problem needs.
- **Time ceiling: ~2.5 hrs on a Wednesday build session, ~1.5 hrs on a Saturday prove session.**
  If a task will not fit, cut its scope rather than extending the session.
- **Always end a session by committing and pushing.** The program's scheduled tasks read this
  repository's pushed commit history to tick capabilities in
  `ai-native-prep/State/Capability-Tracker.md`. Unpushed work is invisible to them and the
  tracker will not advance. Prompt him for this if a session ends without a push.

### Evidence honesty

When drafting anything that could become résumé or interview material — README, case study, ADR,
commit message — keep these distinctions intact:

- ITCH parsing and order-book construction here are **project-built evidence**, not professional
  production experience. Bharath has never built a production market-data feed handler and this
  must never be implied.
- FPGA is **architectural and platform exposure with trade-off judgement**, never RTL or Verilog
  development.
- Modern C++ here is **refreshed technical currency grounded in earlier professional development
  experience**, not continuous recent IC-level authorship.
- The execution side — order management, risk controls, gateway, connectivity — is where his
  twenty years of professional depth genuinely applies. Say so accurately, in both directions.

### AI-off weeks

In program weeks 2, 5, 8, 11, 14, 17, 20, 23 and 26 the Saturday session opens with a 20–30 minute
exercise done **without** any coding assistant. If he starts a session by saying he is on the
diagnostic, do not assist until he says it is finished. The result is recorded honestly either
way — a difficult diagnostic is useful evidence, not a failure to paper over.