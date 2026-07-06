#!/usr/bin/env python3
"""Reduce trials_monolithic.csv into the same shape as summary.json (analyze.py),
so the fragmented-vs-monolithic A/B comparison has matching per-model numbers
on both sides. See ../discord_bot/CONTEXT.md and README.md in this dir for the verdict.
"""
import csv, json, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "trials_monolithic.csv"


def load():
    with open(CSV) as f:
        return list(csv.DictReader(f))


def by(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g


def rate(rows, field):
    n = len(rows)
    s = sum(int(r[field]) for r in rows if r[field] in ("0", "1"))
    return s, n, (s / n if n else 0)


def main():
    rows = load()
    per_model_correct, per_model_fake, per_model_dur = {}, {}, {}
    for m, rs in sorted(by(rows, "model").items()):
        c, n, pc = rate(rs, "correct")
        f, _, pf = rate(rs, "fake_detected")
        durs = [float(r["duration_s"]) for r in rs if r["duration_s"]]
        md = statistics.mean(durs) if durs else 0
        per_model_correct[m] = (c, n, pc)
        per_model_fake[m] = (f, n, pf)
        per_model_dur[m] = md

    out = {
        "note": "Partial run (3 of 9 models; qwen3:14b stopped early at 15/33 trials). "
                "Kept for the record alongside summary.json (fragmented baseline).",
        "n_trials": len(rows),
        "per_model": {
            m: {
                "correct": c,
                "n": n,
                "rate": pc,
                "fake_rate": per_model_fake[m][2],
                "mean_duration_s": per_model_dur[m],
            }
            for m, (c, n, pc) in per_model_correct.items()
        },
    }
    (ROOT / "summary_monolithic.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {ROOT/'summary_monolithic.json'}")


if __name__ == "__main__":
    main()
