import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("imbalance.csv")

fig, ax1 = plt.subplots(figsize=(12, 5))

ax1.set_xlabel("Message Count (tick)")
ax1.set_ylabel("Imbalance (shares)", color="steelblue")
ax1.plot(df["msg_count"], df["imbalance"], color="steelblue", linewidth=1, label="Imbalance")
ax1.tick_params(axis="y", labelcolor="steelblue")
ax1.axhline(0, color="steelblue", linewidth=0.5, linestyle="--", alpha=0.5)

ax2 = ax1.twinx()
ax2.set_ylabel("Mid Price ($)", color="tomato")
ax2.plot(df["msg_count"], df["mid_price"], color="tomato", linewidth=1.5, label="Mid Price")
ax2.tick_params(axis="y", labelcolor="tomato")

fig.suptitle("EQNR — Order Book Imbalance vs Mid Price", fontweight="bold")
fig.tight_layout()
plt.savefig("imbalance_plot.png", dpi=150)
print("Saved imbalance_plot.png")
