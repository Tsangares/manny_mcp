#!/usr/bin/env python3
"""Reduce trials.csv into per-model and per-scenario tables, plus a plot."""
import csv, sys, json, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "trials.csv"

def load():
    with open(CSV) as f:
        return list(csv.DictReader(f))

def by(rows, key):
    g = defaultdict(list)
    for r in rows: g[r[key]].append(r)
    return g

def rate(rows, field):
    n = len(rows); s = sum(int(r[field]) for r in rows if r[field].isdigit() or r[field] in ("0","1"))
    return s, n, (s/n if n else 0)

def main():
    rows = load()
    print(f"Total trials: {len(rows)}")

    # Per-model overall
    print("\n=== Per-model overall (across all 11 cases x seeds) ===")
    print(f"{'model':<55}{'correct':>10}{'%':>7}{'fake':>8}{'%':>7}{'mean_dur':>10}")
    per_model_correct = {}
    per_model_fake = {}
    per_model_dur = {}
    for m, rs in sorted(by(rows, "model").items()):
        c, n, pc = rate(rs, "correct")
        f, _, pf = rate(rs, "fake_detected")
        durs = [float(r["duration_s"]) for r in rs if r["duration_s"]]
        md = statistics.mean(durs) if durs else 0
        per_model_correct[m] = (c, n, pc)
        per_model_fake[m] = (f, n, pf)
        per_model_dur[m] = md
        print(f"{m:<55}{c:>5}/{n:<4}{100*pc:>6.1f}%{f:>5}/{n:<2}{100*pf:>6.1f}%{md:>9.1f}s")

    # Per-case across models
    print("\n=== Per-case correctness across all models ===")
    print(f"{'case_id':<35}{'correct':>10}{'%':>7}")
    for cid, rs in sorted(by(rows, "case_id").items()):
        c, n, p = rate(rs, "correct")
        print(f"{cid:<35}{c:>5}/{n:<4}{100*p:>6.1f}%")

    # Model x case grid (correct / total)
    print("\n=== Model x case correctness grid ===")
    cases = sorted({r["case_id"] for r in rows})
    models = sorted({r["model"] for r in rows})
    # Header (truncate names)
    print(f"{'model':<32}" + "".join(f"{c[:10]:>11}" for c in cases))
    for m in models:
        cells = ""
        for c in cases:
            sub = [r for r in rows if r["model"]==m and r["case_id"]==c]
            sc = sum(int(r["correct"]) for r in sub)
            cells += f"{sc}/{len(sub):<8}".rjust(11)
        print(f"{m[:31]:<32}{cells}")

    # Save reduced JSON for the post
    out = {
        "n_trials": len(rows),
        "per_model": {m: {"correct": c, "n": n, "rate": pc, "fake_rate": per_model_fake[m][2], "mean_duration_s": per_model_dur[m]}
                      for m, (c,n,pc) in per_model_correct.items()},
        "per_case": {cid: {"correct": rate(rs,"correct")[0], "n": rate(rs,"correct")[1], "rate": rate(rs,"correct")[2]}
                     for cid, rs in by(rows, "case_id").items()},
    }
    (ROOT / "summary.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {ROOT/'summary.json'}")

    # Optional plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ms = sorted(per_model_correct.keys(), key=lambda m: per_model_correct[m][2])
        rates_correct = [100*per_model_correct[m][2] for m in ms]
        rates_fake = [100*per_model_fake[m][2] for m in ms]
        fig, ax = plt.subplots(figsize=(10, 5))
        y = range(len(ms))
        ax.barh(y, rates_correct, color="#2b6cb0", label="correct")
        ax.barh(y, [-r for r in rates_fake], color="#c53030", label="faked (claim w/o send_command)")
        ax.set_yticks(y); ax.set_yticklabels([m[:30] for m in ms])
        ax.axvline(0, color="black", lw=0.5)
        ax.set_xlabel("% of trials")
        ax.set_title(f"Model performance under agentic-mode harness  (n={len(rows)} trials, {len(cases)} cases x seeds)")
        ax.legend(loc="lower right")
        ax.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()
        plt.savefig(ROOT / "model_correct_vs_fake.png", dpi=130)
        print(f"Wrote {ROOT/'model_correct_vs_fake.png'}")
    except ImportError:
        print("matplotlib not available; skipping plot")

if __name__ == "__main__":
    main()
