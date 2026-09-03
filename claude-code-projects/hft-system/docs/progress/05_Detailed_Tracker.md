# 📘 HFT Trading Systems Bootcamp — Execution Tracker (With Expected Outputs)

---

## 🎯 Objective

Build a low-latency trading system from NASDAQ ITCH data.

---

## 🧭 Rules

* Mon–Thu: Build (2–3 hrs)
* Sat: Review deeply
* Sun: Rest
* No skipping logs
* No moving forward without meeting expected output

---

## 🧠 Claude’s Role

For each day:

1. Ask what I completed
2. Compare against **Expected Output**
3. Reject incomplete work
4. Force corrections before moving on
5. Keep feedback strict and concise

---

# 📅 WEEK 1 — Order Book Foundations

---

## Day 1 — File Reader

### Tasks

* Read ITCH binary file
* Extract message length + type
* Print first N messages

### ✅ Expected Output

```
Message Type: A
Message Type: E
Message Type: X
...
Processed 50 messages
```

### ❌ Reject if:

* No variation in message types
* Crashes or incomplete reads

---

## Day 2 — Add Order Parsing

### Tasks

* Parse ‘A’ message fields:

  * order_id
  * side
  * shares
  * price
  * stock

### ✅ Expected Output

```
ADD ORDER | ID: 10165 Side: B Shares: 3900 Price: 135000 Stock: CS
ADD ORDER | ID: 327 Side: B Shares: 1200 Price: 587800 Stock: RDS.A
```

### ❌ Reject if:

* Stock contains padding spaces
* Price/shares unrealistic
* Missing fields

---

## Day 3 — Order Book (Per Symbol)

### Tasks

* Maintain:

  * symbol → order book
  * bids (max)
  * asks (min)

### ✅ Expected Output

```
RDS.A | BID: 58.78 | ASK: 59.05 | SPREAD: 0.27
CS    | BID: 13.50 | ASK: 13.60 | SPREAD: 0.10
```

### ❌ Reject if:

* Global (cross-symbol) book
* Negative spread
* Missing one side without handling

---

## Day 4 — Replay Engine

### Tasks

* Process 1000–5000 messages
* Print every 100 messages
* Convert price → decimal

### ✅ Expected Output

```
[100] ARGX | BID: 160.58 | ASK: 162.47 | SPREAD: 1.89
[200] ARGX | BID: 160.60 | ASK: 162.40 | SPREAD: 1.80
[300] ARGX | BID: 160.55 | ASK: 162.50 | SPREAD: 1.95
```

### ❌ Reject if:

* Static prices (no movement)
* Crashes under load
* Flooded logs (no batching)

---

## Day 6 — Weekly Review

### ✅ Expected Output

Clear answers to:

* What works?
* What is broken?
* Biggest mistake?
* Confidence in correctness (0–100%)
* What assumptions are unverified?

---

# 📅 WEEK 2 — Trades + Imbalance

---

## Day 1 — Execute Message Parsing

### Tasks

* Parse ‘E’ message
* Extract:

  * order_id
  * executed shares

### ✅ Expected Output

```
EXECUTE | ID: 10165 Shares: 100
EXECUTE | ID: 327 Shares: 200
```

### ❌ Reject if:

* Cannot map to existing orders
* Wrong field extraction

---

## Day 2 — Trades + Book Sync

### Tasks

* Update order book on execution
* Reduce shares or remove order

### ✅ Expected Output

```
Before: BID 58.78 (100 shares)
After:  BID 58.78 (0 shares removed)
```

### ❌ Reject if:

* Book unchanged after execution
* Negative shares

---

## Day 3 — Imbalance Metrics

### Tasks

* Compute:

  * total bid volume
  * total ask volume

### ✅ Expected Output

```
RDS.A | BidVol: 50000 AskVol: 42000 Imbalance: +8000
```

### ❌ Reject if:

* Always zero
* Same values every tick

---

## Day 4 — Visualization

### Tasks

* Plot imbalance vs price (Python allowed)

### ✅ Expected Output

* Graph showing:

  * Imbalance trend
  * Price movement overlay

### ❌ Reject if:

* Static or flat plot
* Misaligned axes

---

# 📅 WEEK 3 — Queue Simulation

### Expected Output

```
Order Placed @ 58.78
Queue Position: 5
Filled after: 120 ms
```

---

# 📅 WEEK 4 — Strategy (Market Making)

### Expected Output

```
Trades: 120
PnL: +$250
Max Drawdown: -$80
```

---

# 📅 WEEK 5 — Backtesting Engine

### Expected Output

```
Replay → Strategy → Orders → Fills working end-to-end
No lookahead bias
```

---

# 📅 WEEK 6 — Risk Layer

### Expected Output

```
Position Limit Hit → Trading Halted
```

---

# 📅 WEEK 7 — Alpha Signals

### Expected Output

```
Strategy v2 Sharpe > Strategy v1
```

---

# 📅 WEEK 8 — Execution

### Expected Output

```
Naive PnL: +300
Realistic PnL: +120
```

---

# 📅 WEEK 9 — Latency

### Expected Output

```
Before: 120µs
After:  35µs
```

---

# 📅 WEEK 10 — Impact Modeling

### Expected Output

```
Large orders → measurable slippage
```

---

# 📅 WEEK 11 — ML Layer

### Expected Output

```
Model Accuracy > baseline heuristic
```

---

# 📅 WEEK 12 — Final System

### Expected Output

```
Full system running:
- Data → Strategy → Execution → Risk
PnL + Metrics generated
```

---

# 📊 Daily Log (Mandatory)

## Day X Log

* Goal:
* Completed:
* Expected Output Met? (Yes/No)
* If No → Why?
* Blockers:
* Key Learning:
* Time Spent:
* Tomorrow First Step:

---

# 🚨 Hard Rules

* No Expected Output → Day NOT complete
* No skipping bugs
* No moving ahead with incorrect data
* Always validate with real output

---

# 🎯 End State

You can confidently say:

“I built a trading system from raw exchange data with:

* Order book reconstruction
* Trade handling
* Strategy + backtesting
* Risk + execution modeling”

---
