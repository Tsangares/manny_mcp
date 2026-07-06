#!/usr/bin/env python3
"""
Generate the three figures for the blog post, saved to ~/Downloads.

1. manny_model_correct_vs_fake.png - per-model bench results (referenced in post)
2. manny_per_case_difficulty.png - per-case correctness, surfaces drop_inventory failure
3. manny_production_logs_send_command.png - daily send_command rate from logs
"""
import csv, json, os, glob, collections
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "Downloads"
TRIALS = ROOT / "bench_results" / "trials.csv"
LOGS = ROOT / "logs" / "conversations"

# ---- Common style ----
plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "-",
})

BLUE = "#2b6cb0"
RED  = "#c53030"
GRAY = "#4a5568"

# ---- Load trials ----
rows = list(csv.DictReader(open(TRIALS)))
n_trials = len(rows)

# ---- Figure 1: per-model correct vs faked ----
per_model_correct = collections.defaultdict(lambda: [0, 0])  # [correct, total]
per_model_fake = collections.defaultdict(lambda: [0, 0])
for r in rows:
    m = r["model"]
    per_model_correct[m][1] += 1
    per_model_fake[m][1] += 1
    if r["correct"] == "1": per_model_correct[m][0] += 1
    if r["fake_detected"] == "1": per_model_fake[m][0] += 1

# Friendly model labels
def shorten(name):
    name = name.replace("hf.co/Salesforce/Llama-xLAM-2-8b-fc-r-gguf:latest", "xLAM:8b")
    name = name.replace("hermes3:8b-llama3.1-q4_K_M", "hermes3:8b")
    name = name.replace("llama3-groq-tool-use:8b", "llama3-groq-tool:8b")
    return name

models = sorted(per_model_correct.keys(), key=lambda m: per_model_correct[m][0]/per_model_correct[m][1])
correct_pcts = [100 * per_model_correct[m][0] / per_model_correct[m][1] for m in models]
fake_pcts = [100 * per_model_fake[m][0] / per_model_fake[m][1] for m in models]

fig, ax = plt.subplots(figsize=(9.5, 5))
y = list(range(len(models)))
ax.barh(y, correct_pcts, color=BLUE, label="correct on per-case rule")
ax.barh(y, [-p for p in fake_pcts], color=RED, label="claimed action without send_command (proxy for faking)")
ax.set_yticks(y)
ax.set_yticklabels([shorten(m) for m in models])
ax.axvline(0, color="black", lw=0.6)
ax.set_xlim(-30, 100)
ax.set_xlabel("% of 33 trials (11 cases x 3 seeds)")
ax.set_title("Per-model performance under the agentic-mode harness")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, framealpha=0.95, frameon=False)
ax.set_xticks([-20, 0, 20, 40, 60, 80, 100])
ax.set_xticklabels(["20%", "0", "20%", "40%", "60%", "80%", "100%"])
for i, p in enumerate(correct_pcts):
    ax.text(p + 1.5, i, f"{p:.0f}%", va="center", fontsize=9, color=BLUE)
plt.tight_layout()
out1 = OUT / "manny_model_correct_vs_fake.png"
plt.savefig(out1, dpi=150)
plt.close()
print(f"Wrote {out1}")

# ---- Figure 2: per-case difficulty ----
per_case = collections.defaultdict(lambda: [0, 0])
for r in rows:
    per_case[r["case_id"]][1] += 1
    if r["correct"] == "1": per_case[r["case_id"]][0] += 1
cases = sorted(per_case.keys(), key=lambda c: per_case[c][0]/per_case[c][1])
case_pcts = [100 * per_case[c][0] / per_case[c][1] for c in cases]

fig, ax = plt.subplots(figsize=(9.5, 5.2))
y = list(range(len(cases)))
colors = [RED if p < 30 else (BLUE if p > 70 else GRAY) for p in case_pcts]
ax.barh(y, case_pcts, color=colors)
ax.set_yticks(y)
ax.set_yticklabels(cases)
ax.set_xlim(0, 105)
ax.set_xlabel("% of 27 trials correct (9 models x 3 seeds, per case)")
ax.set_title("Per-case difficulty across all 9 models")
ax.axvline(50, color="black", lw=0.4, alpha=0.4, ls="--")
for i, p in enumerate(case_pcts):
    ax.text(p + 1, i, f"{p:.0f}%", va="center", fontsize=9, color="black")
# annotate the failures
for i, c in enumerate(cases):
    if c == "drop_inventory_naive":
        ax.annotate("only 4/27 ask for confirmation",
                    xy=(case_pcts[i], i), xytext=(case_pcts[i]+22, i-0.2),
                    fontsize=9, color=RED,
                    arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))
plt.tight_layout()
out2 = OUT / "manny_per_case_difficulty.png"
plt.savefig(out2, dpi=150)
plt.close()
print(f"Wrote {out2}")

# ---- Figure 3: production-log send_command rate by day ----
bundles = collections.defaultdict(lambda: {"req":None,"tools":[],"resp":None,"date":None})
for f in sorted(glob.glob(str(LOGS / "conversations_*.jsonl"))):
    date = Path(f).stem.replace("conversations_", "")
    for line in open(f):
        try: e = json.loads(line)
        except: continue
        rid = e.get("request_id")
        if not rid: continue
        b = bundles[rid]; b["date"] = date
        t = e.get("type")
        if t == "request": b["req"] = e
        elif t == "response": b["resp"] = e
        elif t == "tool_call": b["tools"].append(e)

grid = collections.defaultdict(lambda: collections.defaultdict(lambda: [0,0]))  # date -> task -> [send,total]
for rid, b in bundles.items():
    if not b["req"] or not b["resp"]: continue
    tt = b["req"].get("task_type", "?")
    has_send = any("send_command" in tc.get("tool","") for tc in b["tools"])
    grid[b["date"]][tt][1] += 1
    if has_send: grid[b["date"]][tt][0] += 1

dates = sorted(grid.keys())
focus_types = ["loop_command", "simple_command", "multi_step"]
fig, ax = plt.subplots(figsize=(9.5, 4.8))
markers = {"loop_command": "o", "simple_command": "s", "multi_step": "^"}
colors = {"loop_command": "#c53030", "simple_command": "#2b6cb0", "multi_step": "#2f855a"}
for tt in focus_types:
    xs, ys, ns = [], [], []
    for d in dates:
        s, n = grid[d][tt]
        if n == 0: continue
        xs.append(d); ys.append(100*s/n); ns.append(n)
    ax.plot(xs, ys, marker=markers[tt], color=colors[tt], lw=1.6, label=f"{tt} (n shown above marker)")
    for x, y, n in zip(xs, ys, ns):
        ax.text(x, y+3, f"n={n}", ha="center", fontsize=8, color=colors[tt])

ax.axvspan(-0.5, 2.5, color="#c53030", alpha=0.07)
ax.axvspan(3.5, 5.5, color="#2b6cb0", alpha=0.07)
ax.text(1, 105, "legacy mode", color="#c53030", ha="center", fontsize=10)
ax.text(4.5, 105, "agentic mode", color="#2b6cb0", ha="center", fontsize=10)

ax.set_ylim(-5, 115)
ax.set_ylabel("% calling send_command")
ax.set_xlabel("date (production Discord bot logs)")
ax.set_title("send_command call rate by task type, before and after the structural fix")
ax.legend(loc="lower right", framealpha=0.95)
ax.tick_params(axis="x", rotation=30)
plt.tight_layout(pad=1.2)
out3 = OUT / "manny_production_logs_send_command.png"
plt.savefig(out3, dpi=150)
plt.close()
print(f"Wrote {out3}")
