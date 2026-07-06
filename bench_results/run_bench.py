#!/usr/bin/env python3
"""
Sweep test_harness.py across (model, test_case, seed) and score each trial.
Writes one row per trial to bench_results/trials.csv plus a raw JSONL log.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import yaml
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "discord_bot" / "test_harness.py"
TEST_CASES = ROOT / "discord_bot" / "test_cases.yaml"
OUT_CSV = ROOT / "bench_results" / "trials.csv"
OUT_JSONL = ROOT / "bench_results" / "trials.jsonl"

MODELS = [
    "qwen2.5:14b",
    "qwen2.5:32b",
    "qwen3:14b",
    "qwen2.5-coder:14b",
    "mistral-nemo:12b",
    "llama3.1:8b",
    "hermes3:8b-llama3.1-q4_K_M",
    "llama3-groq-tool-use:8b",
    "hf.co/Salesforce/Llama-xLAM-2-8b-fc-r-gguf:latest",
]

SEEDS = [1, 2, 3]
TIMEOUT_S = 180

# Per-case scoring rule. Each case maps to a function over the harness JSON
# returning (correct: bool, reason: str). Rules encode test_cases.yaml's
# expected_behavior in machine-checkable form.
def make_rules():
    def has_cmd_prefix(out, prefix):
        for tc in out.get("tool_calls", []):
            if tc.get("tool") != "send_command": continue
            cmd = (tc.get("args", {}) or {}).get("command", "") or ""
            if cmd.upper().startswith(prefix.upper()): return True
        return False
    def any_send(out):
        return any(tc.get("tool") == "send_command" for tc in out.get("tool_calls", []))
    def has_observation(out, tool):
        return any(tc.get("tool") == tool for tc in out.get("tool_calls", []))
    def has_observation_with_arg(out, tool, arg_key, arg_val_substr):
        for tc in out.get("tool_calls", []):
            if tc.get("tool") != tool: continue
            v = (tc.get("args", {}) or {}).get(arg_key, "")
            if isinstance(v, str) and arg_val_substr.lower() in v.lower(): return True
            if isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, str) and arg_val_substr.lower() in vv.lower(): return True
        return False
    def claim_words_present(out):
        resp = (out.get("response") or "").lower()
        words = ["started","switched","opened","killed","fishing","chopping","cooking",
                 "mining","walking","heading","equipped","deposited","withdrew","picked up",
                 "attacking","banking","fighting"]
        return any(w in resp for w in words)

    def score_woodcutting_no_axe(out):
        # Correct: do NOT send CHOP_TREE or any send_command claiming chopping; tell user about missing axe
        if has_cmd_prefix(out, "CHOP"): return False, "chopped without axe"
        if any_send(out) and "axe" not in (out.get("response") or "").lower():
            return False, "sent command without acknowledging missing axe"
        return True, "did not chop / acknowledged missing axe"

    def score_low_health_emergency(out):
        # Correct: STOP, or eat, or flee. Wrong: KILL_LOOP / continue attacking
        if has_cmd_prefix(out, "KILL_LOOP"): return False, "kept attacking at 5HP"
        if has_cmd_prefix(out, "STOP"): return True, "STOP sent"
        if has_cmd_prefix(out, "EAT"): return True, "EAT sent"
        # Acceptable: described emergency without dangerous action
        if not any_send(out): return True, "no dangerous command"
        return False, "sent unrelated command in emergency"

    def score_pickup_ground_item_dropped(out):
        # Correct: query_nearby with ground items, then PICK_UP_ITEM Bones
        if has_cmd_prefix(out, "PICK_UP_ITEM Bones"): return True, "PICK_UP_ITEM Bones"
        if has_cmd_prefix(out, "PICK_UP_ITEM"): return True, "PICK_UP_ITEM (other item)"
        return False, "did not pick up bones"

    def score_pickup_ground_item_static_spawn(out):
        # Correct: INTERACT_OBJECT with fishing net (static spawn), NOT PICK_UP_ITEM
        for tc in out.get("tool_calls", []):
            if tc.get("tool") != "send_command": continue
            cmd = (tc.get("args", {}) or {}).get("command","") or ""
            cu = cmd.upper()
            if cu.startswith("INTERACT_OBJECT") and "FISHING_NET" in cu.replace(" ","_").upper():
                return True, "INTERACT_OBJECT fishing_net"
            if cu.startswith("PICK_UP_ITEM"): return False, "used PICK_UP_ITEM on static spawn"
        return False, "did not pick up net"

    def score_scan_ground_items(out):
        # Correct: use query_nearby with include_ground_items
        for tc in out.get("tool_calls", []):
            if tc.get("tool") == "query_nearby":
                args = tc.get("args", {}) or {}
                if args.get("include_ground_items"): return True, "query_nearby ground items"
        return False, "did not query ground items"

    def score_goto_fishing_spot(out):
        # Correct: lookup or query, then GOTO with reasonable coordinates (south of lumbridge)
        if has_cmd_prefix(out, "GOTO"): return True, "GOTO sent"
        if has_observation(out, "lookup_location"): return True, "looked up location (no GOTO yet)"
        return False, "neither lookup nor GOTO"

    def score_go_south_direction(out):
        # Correct: GOTO south (y < 3218) by a reasonable amount, not 1 tile
        for tc in out.get("tool_calls", []):
            if tc.get("tool") != "send_command": continue
            cmd = (tc.get("args", {}) or {}).get("command","") or ""
            parts = cmd.split()
            if parts and parts[0].upper() == "GOTO" and len(parts) >= 3:
                try:
                    y = int(parts[2])
                    if y < 3210: return True, f"GOTO south to y={y}"
                    return False, f"GOTO insufficient: y={y}"
                except: pass
        return False, "no GOTO south"

    def score_drop_inventory_naive(out):
        # Acceptable: ask for confirmation, OR use BANK_DEPOSIT_ALL instead, OR refuse
        # Wrong: DROP_ALL without confirmation
        if has_cmd_prefix(out, "DROP_ALL") or has_cmd_prefix(out, "DROP "):
            return False, "dropped without confirmation"
        return True, "no destructive drop"

    def score_scan_fishing_net(out):
        # Correct: scan_tile_objects or query_nearby looking for net
        if has_observation(out, "scan_tile_objects"): return True, "scan_tile_objects called"
        if has_observation(out, "query_nearby"): return True, "query_nearby called"
        return False, "no scan tool used"

    def score_kill_frogs(out):
        # Correct: KILL_LOOP Giant_frog ...
        for tc in out.get("tool_calls", []):
            if tc.get("tool") != "send_command": continue
            cmd = (tc.get("args", {}) or {}).get("command","") or ""
            cu = cmd.upper().replace(" ","_")
            if cu.startswith("KILL_LOOP") and "FROG" in cu:
                return True, "KILL_LOOP frogs"
        return False, "no KILL_LOOP frogs"

    def score_bank_full_inventory(out):
        # Correct: BANK_OPEN then BANK_DEPOSIT_ALL (or similar)
        cmds = []
        for tc in out.get("tool_calls", []):
            if tc.get("tool") == "send_command":
                cmds.append(((tc.get("args",{}) or {}).get("command","") or "").upper())
        if any(c.startswith("BANK_DEPOSIT") for c in cmds): return True, "BANK_DEPOSIT sent"
        if any(c.startswith("BANK_OPEN") for c in cmds): return True, "BANK_OPEN sent"
        return False, "no bank command"

    return {
        "woodcutting_no_axe": score_woodcutting_no_axe,
        "low_health_emergency": score_low_health_emergency,
        "pickup_ground_item_dropped": score_pickup_ground_item_dropped,
        "pickup_ground_item_static_spawn": score_pickup_ground_item_static_spawn,
        "scan_ground_items": score_scan_ground_items,
        "goto_fishing_spot": score_goto_fishing_spot,
        "go_south_direction": score_go_south_direction,
        "drop_inventory_naive": score_drop_inventory_naive,
        "scan_fishing_net": score_scan_fishing_net,
        "kill_frogs": score_kill_frogs,
        "bank_full_inventory": score_bank_full_inventory,
    }


def run_one(model, scenario, message, seed):
    env = os.environ.copy()
    env["OLLAMA_HOST"] = env.get("OLLAMA_HOST", "http://10.0.0.99:11434")
    env["OLLAMA_SEED"] = str(seed)  # used if llm_client honors it
    cmd = [
        str(ROOT / "venv" / "bin" / "python"),
        str(HARNESS),
        "--json",
        "--model", model,
        "--scenario", scenario,
        message,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout>{TIMEOUT_S}s", "duration_s": TIMEOUT_S}
    dur = time.time() - t0
    out = proc.stdout
    # The harness prints some non-JSON lines first (e.g. "Loaded scenario..."). Find the JSON object.
    idx = out.find("{")
    if idx < 0:
        return {"error": "no_json", "stderr": proc.stderr[-500:], "duration_s": dur}
    try:
        parsed = json.loads(out[idx:])
    except json.JSONDecodeError as e:
        return {"error": f"json_decode:{e}", "raw_tail": out[-500:], "duration_s": dur}
    parsed["duration_s"] = round(dur, 2)
    return parsed


def main():
    cases = yaml.safe_load(open(TEST_CASES))["test_cases"]
    rules = make_rules()
    rows = []
    fout_jsonl = open(OUT_JSONL, "w")
    fout_csv = open(OUT_CSV, "w", newline="")
    writer = csv.writer(fout_csv)
    writer.writerow([
        "model","case_id","scenario","seed","correct","reason",
        "send_command_count","observed","fake_detected","duration_s","error","response_excerpt"
    ])
    fout_csv.flush()

    total = len(MODELS) * len(cases) * len(SEEDS)
    n = 0
    for model in MODELS:
        for case in cases:
            cid = case["id"]
            scenario = case.get("scenario", "default")
            message = case["message"]
            rule = rules.get(cid)
            for seed in SEEDS:
                n += 1
                t0 = time.time()
                out = run_one(model, scenario, message, seed)
                send_count = sum(1 for tc in out.get("tool_calls", []) if tc.get("tool") == "send_command")
                observed = bool(out.get("observed", False))
                resp = (out.get("response") or "").replace("\n"," ")[:200]
                claim = any(w in resp.lower() for w in ["started","switched","opened","killed","fishing","chopping","cooking","mining","walking","heading","equipped","deposited","withdrew","picked up","attacking","banking","fighting"])
                fake = bool(claim and send_count == 0)
                if rule:
                    correct, reason = rule(out)
                else:
                    correct, reason = (False, "no_rule")
                err = out.get("error") or ""
                row = [model, cid, scenario, seed, int(correct), reason, send_count, int(observed), int(fake), out.get("duration_s",""), err, resp]
                writer.writerow(row)
                fout_csv.flush()
                fout_jsonl.write(json.dumps({"meta":{"model":model,"case":cid,"seed":seed},"out":out})+"\n")
                fout_jsonl.flush()
                dur = time.time() - t0
                print(f"[{n}/{total}] {model:<55} {cid:<35} seed={seed} correct={int(correct):d} send={send_count} fake={int(fake)} {dur:>5.1f}s :: {reason}", flush=True)

    fout_csv.close()
    fout_jsonl.close()
    print(f"\nWrote {OUT_CSV}")

if __name__ == "__main__":
    main()
