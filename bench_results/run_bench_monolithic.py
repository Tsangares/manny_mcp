#!/usr/bin/env python3
"""
Re-run the bench under monolithic CONTEXT.md (no fragment injection)
for the smart-context A/B comparison post (Post B).

Sets MANNY_BENCH_MONOLITHIC=1 in the env so agentic_loop.py skips
the activity_classifier fragment injection. CONTEXT.md must already
be replaced with the 186-line pre-fragment version (git 9ad9d77).

Output goes to bench_results/trials_monolithic.csv so it doesn't
clobber the original trials.csv (which is the fragmented baseline).
"""
import sys
import os
from pathlib import Path

# Force monolithic mode for every spawned harness call
os.environ["MANNY_BENCH_MONOLITHIC"] = "1"

# Re-use everything from run_bench.py with redirected output paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench_results"))

import run_bench
run_bench.OUT_CSV = ROOT / "bench_results" / "trials_monolithic.csv"
run_bench.OUT_JSONL = ROOT / "bench_results" / "trials_monolithic.jsonl"
run_bench.main()
