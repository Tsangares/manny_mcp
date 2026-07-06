# Bench results: fragmented vs. monolithic CONTEXT.md (Post B)

A/B test of two system-prompt strategies for `discord_bot/agentic_loop.py`,
scored by `run_bench.py` against `discord_bot/test_harness.py` across 9 local
Ollama models and 11 tool-calling test cases (3 seeds each).

- **Fragmented** (`run_bench.py`, output `trials.csv` / `summary.json`): the
  committed `CONTEXT.md` (short core prompt) plus a per-message context
  fragment injected by `classify_activity()` / `get_context_fragment()`.
- **Monolithic** (`run_bench_monolithic.py`, output `trials_monolithic.csv` /
  `summary_monolithic.json`): one large prompt with everything inlined, no
  fragment injection. Enabled via `MANNY_BENCH_MONOLITHIC=1`, which
  `agentic_loop.py` checks to skip fragment injection.

## Verdict: fragmented wins

Only 3 models were re-run under the monolithic prompt before the experiment
was called (qwen3:14b stopped at 15/33 trials). For all 3, fragmented beat
monolithic by ~15-32 points:

| model | fragmented | monolithic |
|---|---|---|
| qwen2.5:14b | 23/33 (69.7%) | 18/33 (54.5%) |
| qwen2.5:32b | 24/33 (72.7%) | 17/33 (51.5%) |
| qwen3:14b | 26/33 (78.8%) | 7/15 (46.7%, partial) |

`CONTEXT.md` stays on the fragmented version. The `MANNY_BENCH_MONOLITHIC=1`
env gate is kept in `agentic_loop.py` for future A/B benching, even though
this round didn't favor it.

## Rerunning

```
python3 run_bench.py               # fragmented (default CONTEXT.md)
python3 run_bench_monolithic.py    # monolithic (sets MANNY_BENCH_MONOLITHIC=1)
python3 analyze.py                 # -> summary.json + model_correct_vs_fake.png
python3 gen_monolithic_summary.py  # -> summary_monolithic.json
```

Raw per-trial CSV/JSONL logs and the plot are gitignored (bulky); only the
scripts and the two summary JSON files are committed.
