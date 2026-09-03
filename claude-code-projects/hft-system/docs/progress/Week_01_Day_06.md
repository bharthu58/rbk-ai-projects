# Week 1 - Day 6 (Saturday Review)

## 🎯 Goal
- Complete Week 1 review: assess correctness, identify gaps, document findings

---

## ✅ What I Did
- Answered all 5 review questions against the tracker criteria
- Identified correctness bugs in the current implementation
- Documented system gaps and unverified assumptions

---

## ❌ What Failed
- Spread widening claim was incorrect — with add-only messages, spread can only tighten or stay the same; widening requires cancel/execute messages
- No crossed/locked book detection in place
- `'E'`, `'D'`, `'X'`, `'U'` messages are dropped before the parser — book is purely additive

## ⚠️ Blockers
- None

---

## 🧠 Key Learnings
- A monotonically growing book (adds only) means top-of-book stabilises quickly — price discovery is not realistic without removals
- Crossed book (bid >= ask) is a sign of a parsing bug — should be asserted after every update
- Without an order-id reference map, execute and cancel messages cannot be applied — this must be added before Week 2 Day 1

---

## ⏱ Time Spent
- ~45 minutes

---

## 📌 Tomorrow's First Step
- Week 2 Day 1: add `unordered_map<uint64_t, Order>` reference map, remove `'A'`-only filter in `main.cpp`, parse `'E'` message fields

---

## 🔥 If I only finish ONE thing today:
→ Honest correctness review with all 5 questions answered and gaps documented
