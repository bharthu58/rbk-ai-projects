# Week 1 - Day 4

## 🎯 Goal
- Build replay engine: process 1000–5000 `'A'` messages
- Print top-of-book every 100 messages with counter prefix
- Validate prices move across snapshots

---

## ✅ What I Did
- Modified `main.cpp` to remove the 10-message cap and process 2000 `'A'` messages
- Added `count % 100 == 0` trigger to print top-of-book every 100 messages with `[N]` prefix
- Validated output: spread tightens from $1.89 → $0.91 → $0.60 across 2000 messages

---

## ❌ What Failed
- Initial `count % 100` check was inverted (truthy for all non-multiples) — caused flooded output every message instead of every 100

---

## ⚠️ Blockers
- None

---

## 🧠 Key Learnings
- `count % 100` is non-zero (truthy) for everything except multiples of 100 — always use `== 0` explicitly
- With add-only messages, spread can only **tighten**: new bids above current best bid or new asks below current best ask improve the top of book
- Spread **widening** requires the current best level to be removed — needs cancel (`'X'`/`'D'`) or execute (`'E'`) messages, coming in Week 2
- New orders posted worse than the current best (higher ask, lower bid) go deeper in the book and don't affect top-of-book at all

---

## ⏱ Time Spent
- ~30 minutes

---

## 📌 Tomorrow's First Step
- Saturday: Week 1 Review — fill `Week_01_Review.md`, write missing `Week_01_Day_02.md`, answer SRS prompts

---

## 🔥 If I only finish ONE thing today:
→ Replay engine printing top-of-book every 100 messages with moving prices
