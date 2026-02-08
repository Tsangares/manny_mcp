"""Cost reporting for manny-driver LLM requests.

Usage:
    python -m manny_driver.report_cost           # today's sessions
    python -m manny_driver.report_cost --all      # all sessions
    python -m manny_driver.report_cost --session abc123  # specific session
    python -m manny_driver.report_cost --tail     # live watch mode
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("/tmp/manny_driver_requests.jsonl")

# ANSI colors
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def load_records(path: Path = LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def group_by_session(records: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for r in records:
        groups[r.get("session_id", "unknown")].append(r)
    return dict(groups)


def print_session(session_id: str, records: list[dict]):
    if not records:
        return
    first_ts = records[0].get("ts", "?")
    last_ts = records[-1].get("ts", "?")
    model = records[0].get("model", "?")

    # Calculate duration
    try:
        t0 = datetime.fromisoformat(first_ts)
        t1 = datetime.fromisoformat(last_ts)
        dur = t1 - t0
        hours, remainder = divmod(int(dur.total_seconds()), 3600)
        minutes = remainder // 60
        dur_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
    except (ValueError, TypeError):
        dur_str = "?"

    total_in = sum(r.get("in", 0) for r in records)
    total_out = sum(r.get("out", 0) for r in records)
    total_cost = sum(r.get("cost_usd", 0) for r in records)
    avg_in = total_in // len(records) if records else 0
    avg_out = total_out // len(records) if records else 0

    exec_count = sum(1 for r in records if r.get("phase") == "execution")
    mon_count = sum(1 for r in records if r.get("phase") == "monitoring")

    # Display timestamp in local time
    try:
        ts_display = datetime.fromisoformat(first_ts).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        ts_display = first_ts

    print(f"\n{BOLD}Session {ts_display}{RESET} ({dur_str})  {CYAN}{model}{RESET}  {DIM}[{session_id}]{RESET}")
    print(f"  Requests:  {len(records)} (avg {avg_in:,} in / {avg_out:,} out tokens)")
    print(f"  Tokens:    {total_in:,} in / {total_out:,} out")
    print(f"  Cost:      {GREEN}${total_cost:.4f}{RESET}")
    print(f"  Phases:    execution={exec_count} monitoring={mon_count}")


def run_tail():
    """Watch mode: seek-based polling of the JSONL file for new entries."""
    print(f"{BOLD}Watching{RESET} {LOG_PATH} (Ctrl+C to stop)\n")
    file_pos = 0
    running_cost = 0.0

    # Skip past existing content
    if LOG_PATH.exists():
        existing = load_records()
        running_cost = sum(r.get("cost_usd", 0) for r in existing)
        file_pos = LOG_PATH.stat().st_size
        print(f"{DIM}Skipping {len(existing)} existing records (${running_cost:.4f} so far){RESET}\n")

    try:
        while True:
            if LOG_PATH.exists():
                size = LOG_PATH.stat().st_size
                if size > file_pos:
                    with open(LOG_PATH) as f:
                        f.seek(file_pos)
                        new_data = f.read()
                        file_pos = f.tell()
                    for line in new_data.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        running_cost += r.get("cost_usd", 0)
                        ts = r.get("ts", "?")
                        try:
                            ts = datetime.fromisoformat(ts).astimezone().strftime("%H:%M:%S")
                        except (ValueError, TypeError):
                            pass
                        print(
                            f"  {DIM}{ts}{RESET} "
                            f"{CYAN}{r.get('model','?')}{RESET} "
                            f"{r.get('in',0):,}in/{r.get('out',0):,}out "
                            f"{YELLOW}${r.get('cost_usd',0):.6f}{RESET} "
                            f"{r.get('phase','?')} "
                            f"{DIM}total: {GREEN}${running_cost:.4f}{RESET}"
                        )
                elif size < file_pos:
                    # File was truncated/rotated - reset
                    file_pos = 0
                    continue
            time.sleep(5)
    except KeyboardInterrupt:
        print(f"\n{BOLD}Total cost: ${running_cost:.4f}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="manny-driver cost report")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--today", action="store_true", help="Show today's sessions (default)")
    group.add_argument("--all", action="store_true", help="Show all sessions")
    group.add_argument("--session", type=str, help="Show specific session by ID")
    group.add_argument("--tail", action="store_true", help="Live watch mode")
    args = parser.parse_args()

    if args.tail:
        run_tail()
        return

    records = load_records()
    if not records:
        print("No request logs found. Run manny-driver first.")
        return

    # Filter
    if args.session:
        records = [r for r in records if r.get("session_id") == args.session]
        if not records:
            print(f"No records for session {args.session}")
            return
    elif not args.all:
        # Today only
        today = datetime.now(timezone.utc).date().isoformat()
        records = [r for r in records if r.get("ts", "").startswith(today)]
        if not records:
            print("No sessions today.")
            return

    sessions = group_by_session(records)
    for sid, recs in sessions.items():
        print_session(sid, recs)

    # Total
    total_cost = sum(r.get("cost_usd", 0) for r in records)
    label = "Today" if not args.all and not args.session else "Total"
    print(f"\n{BOLD}{label} total: ${total_cost:.4f}{RESET} across {len(sessions)} session(s)")


if __name__ == "__main__":
    main()
