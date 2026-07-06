#!/usr/bin/env python3
"""
Figure for Post A (recursive cost explosion).

Data anchors from journals/manny_driver_recursive_cost_explosion_2026-02-07.md:
- Pre-fix: messages grew to 82K+ chars by iteration 20+
- Post-fix: messages stay ~500 chars
- Pre-fix request total: ~237K input tokens per call
- Post-fix request total: well under provider limits
- Combined session cost: $26 -> ~$0.02-0.05 (~500x reduction)

The directive growth is linear in iterations under the bug
(each call concatenates prior directive into new wrapper). I'm modelling
it as L(N) = base + (N-1)*W with W chosen so that L(20) hits the
journal's 82K-char number. Post-fix is flat at 500 chars.

This is labeled as a projection from journal-reported endpoints, not a
measurement, because I do not have per-iteration logged sizes from the
$26 session.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path.home() / "Downloads" / "manny_recursive_cost_growth.png"

plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})

RED  = "#c53030"
BLUE = "#2b6cb0"

# Iterations 1..25
iters = list(range(1, 26))

# Pre-fix linear growth: L(1)=20, L(20)=82000  =>  W = (82000-20)/19 ≈ 4314
base = 20
W = (82000 - base) / 19
pre = [base + (n-1) * W for n in iters]

# Post-fix flat
post = [500 for _ in iters]

fig, ax = plt.subplots(figsize=(9.5, 5.0))
ax.plot(iters, pre, color=RED, lw=2.2, marker="o", ms=4, label="before fix: directive concatenates into itself")
ax.plot(iters, post, color=BLUE, lw=2.2, marker="s", ms=4, label="after fix: directive set once, _original_goal preserved")

ax.set_yscale("log")
ax.set_xlabel("monitoring intervention iteration")
ax.set_ylabel("user-message size (characters, log scale)")
ax.set_title("Self-referential directive nesting: per-iteration message growth\n(projection from two journal-reported endpoints)")

# Annotate iteration 20 = 82K chars on pre-fix
ax.axhline(82000, color=RED, lw=0.8, ls="--", alpha=0.5)
ax.annotate("82,000 chars at iter 20\n(journal-reported)",
            xy=(20, 82000), xytext=(11.5, 12000),
            fontsize=9, color=RED,
            arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))

# Annotate post-fix flat line
ax.annotate("~500 chars, every iteration",
            xy=(15, 500), xytext=(15, 1400),
            fontsize=9, color=BLUE,
            arrowprops=dict(arrowstyle="->", color=BLUE, lw=0.8))

# Annotate the cost: 237K tokens per request, $26 over 2hr
ax.text(1.2, 200000,
        "per-request total: ~237K input tokens (incl. conv history + 33 tool schemas)\n"
        "session cost: $26 over 2 hours on Gemini 2.5 Flash Lite",
        fontsize=9, color=RED,
        bbox=dict(facecolor="#fff5f5", edgecolor=RED, lw=0.6, pad=4, alpha=0.95))

ax.text(20, 250,
        "post-fix session cost: ~$0.02-0.05 (≈500x reduction)",
        fontsize=9, color=BLUE, ha="right",
        bbox=dict(facecolor="#ebf8ff", edgecolor=BLUE, lw=0.6, pad=4, alpha=0.95))

ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False)
ax.set_xticks([1, 5, 10, 15, 20, 25])
ax.set_xlim(0.5, 25.5)
ax.set_ylim(100, 1_000_000)
plt.tight_layout()
plt.savefig(OUT, dpi=150)
plt.close()
print(f"Wrote {OUT}")
