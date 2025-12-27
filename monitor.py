#!/home/wil/manny-mcp/venv/bin/python
"""
Performance Monitoring Tool for Manny MCP Optimizations

Tracks and reports on optimization effectiveness:
- Build times (incremental vs clean)
- Cache hit rates
- Search engine performance
- State file write frequency
- Command response latencies

Usage:
    ./monitor.py --metric builds    # Show build performance
    ./monitor.py --metric cache     # Show cache statistics
    ./monitor.py --metric search    # Show search engine stats
    ./monitor.py --metric state     # Monitor state file writes
    ./monitor.py --metric all       # Show all metrics
    ./monitor.py --watch            # Live monitoring mode
"""

import argparse
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import subprocess
import os

# Import optimization modules
try:
    from cache_layer import get_tool_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

try:
    from search_engine import get_search_index
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

# Configuration
STATE_FILE = "/tmp/manny_state.json"
RESPONSE_FILE = "/tmp/manny_response.json"
PLUGIN_DIR = "/home/wil/Desktop/manny"
METRICS_LOG = "/tmp/manny_metrics.json"

# Performance baselines (from OPTIMIZATIONS.md)
BASELINES = {
    "build_time_incremental": {"expected": 30, "alert_threshold": 60},
    "build_time_clean": {"expected": 35, "alert_threshold": 70},
    "command_response": {"expected": 10, "alert_threshold": 100},
    "search_lookup": {"expected": 1, "alert_threshold": 10},
    "cache_hit_rate": {"expected": 50, "alert_threshold": 30},
    "state_writes_per_min": {"expected": 8, "alert_threshold": 20},
    "index_build_time": {"expected": 1, "alert_threshold": 5}
}


class MetricsCollector:
    """Collect and analyze performance metrics."""

    def __init__(self):
        self.metrics_log = Path(METRICS_LOG)
        self._ensure_metrics_log()

    def _ensure_metrics_log(self):
        """Create metrics log if it doesn't exist."""
        if not self.metrics_log.exists():
            self.metrics_log.write_text(json.dumps({
                "builds": [],
                "state_writes": [],
                "commands": []
            }, indent=2))

    def _load_metrics(self) -> Dict:
        """Load metrics from log file."""
        try:
            return json.loads(self.metrics_log.read_text())
        except:
            return {"builds": [], "state_writes": [], "commands": []}

    def _save_metrics(self, metrics: Dict):
        """Save metrics to log file."""
        self.metrics_log.write_text(json.dumps(metrics, indent=2))

    def record_build(self, duration_sec: float, clean: bool = False):
        """Record a build event."""
        metrics = self._load_metrics()
        metrics["builds"].append({
            "timestamp": time.time(),
            "duration_sec": round(duration_sec, 2),
            "clean": clean
        })
        # Keep last 100 builds
        metrics["builds"] = metrics["builds"][-100:]
        self._save_metrics(metrics)

    def record_command(self, command: str, latency_ms: float):
        """Record a command execution."""
        metrics = self._load_metrics()
        metrics["commands"].append({
            "timestamp": time.time(),
            "command": command,
            "latency_ms": round(latency_ms, 2)
        })
        # Keep last 1000 commands
        metrics["commands"] = metrics["commands"][-1000:]
        self._save_metrics(metrics)

    def get_build_stats(self) -> Dict:
        """Get build performance statistics."""
        metrics = self._load_metrics()
        builds = metrics.get("builds", [])

        if not builds:
            return {"error": "No build data available"}

        incremental = [b for b in builds if not b["clean"]]
        clean = [b for b in builds if b["clean"]]

        stats = {
            "total_builds": len(builds),
            "incremental_builds": len(incremental),
            "clean_builds": len(clean)
        }

        if incremental:
            avg = sum(b["duration_sec"] for b in incremental) / len(incremental)
            stats["incremental_avg_sec"] = round(avg, 2)
            stats["incremental_min_sec"] = round(min(b["duration_sec"] for b in incremental), 2)
            stats["incremental_max_sec"] = round(max(b["duration_sec"] for b in incremental), 2)

            baseline = BASELINES["build_time_incremental"]
            stats["incremental_status"] = "OK" if avg < baseline["alert_threshold"] else "SLOW"

        if clean:
            avg = sum(b["duration_sec"] for b in clean) / len(clean)
            stats["clean_avg_sec"] = round(avg, 2)
            stats["clean_min_sec"] = round(min(b["duration_sec"] for b in clean), 2)
            stats["clean_max_sec"] = round(max(b["duration_sec"] for b in clean), 2)

            baseline = BASELINES["build_time_clean"]
            stats["clean_status"] = "OK" if avg < baseline["alert_threshold"] else "SLOW"

        return stats

    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics."""
        if not CACHE_AVAILABLE:
            return {"error": "Cache layer not available"}

        try:
            cache = get_tool_cache()
            stats = cache.get_stats()

            baseline = BASELINES["cache_hit_rate"]
            stats["status"] = "OK" if stats["hit_rate"] >= baseline["alert_threshold"] else "LOW"

            return stats
        except Exception as e:
            return {"error": str(e)}

    def get_search_stats(self) -> Dict:
        """Get search engine statistics."""
        if not SEARCH_AVAILABLE:
            return {"error": "Search engine not available"}

        try:
            index = get_search_index(PLUGIN_DIR)
            stats = index.get_stats()

            baseline = BASELINES["index_build_time"]
            stats["status"] = "OK" if stats["build_time_sec"] < baseline["alert_threshold"] else "SLOW"

            return stats
        except Exception as e:
            return {"error": str(e)}

    def get_state_write_frequency(self, window_minutes: int = 5) -> Dict:
        """Estimate state file write frequency."""
        state_file = Path(STATE_FILE)

        if not state_file.exists():
            return {"error": "State file not found"}

        # Monitor state file modifications
        initial_mtime = state_file.stat().st_mtime
        time.sleep(window_minutes * 60)
        final_mtime = state_file.stat().st_mtime

        writes_in_window = 0
        current_mtime = initial_mtime

        # Count discrete write events
        while current_mtime < final_mtime:
            time.sleep(0.1)
            new_mtime = state_file.stat().st_mtime
            if new_mtime != current_mtime:
                writes_in_window += 1
                current_mtime = new_mtime

        writes_per_min = writes_in_window / window_minutes

        baseline = BASELINES["state_writes_per_min"]
        status = "OK" if writes_per_min < baseline["alert_threshold"] else "HIGH"

        return {
            "window_minutes": window_minutes,
            "total_writes": writes_in_window,
            "writes_per_min": round(writes_per_min, 2),
            "status": status,
            "baseline_expected": baseline["expected"],
            "baseline_threshold": baseline["alert_threshold"]
        }

    def get_command_stats(self, since_minutes: int = 60) -> Dict:
        """Get command execution statistics."""
        metrics = self._load_metrics()
        commands = metrics.get("commands", [])

        if not commands:
            return {"error": "No command data available"}

        # Filter to time window
        cutoff = time.time() - (since_minutes * 60)
        recent = [c for c in commands if c["timestamp"] >= cutoff]

        if not recent:
            return {"error": f"No commands in last {since_minutes} minutes"}

        latencies = [c["latency_ms"] for c in recent]
        avg_latency = sum(latencies) / len(latencies)

        baseline = BASELINES["command_response"]
        status = "OK" if avg_latency < baseline["alert_threshold"] else "SLOW"

        return {
            "total_commands": len(recent),
            "avg_latency_ms": round(avg_latency, 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "status": status,
            "baseline_expected_ms": baseline["expected"],
            "baseline_threshold_ms": baseline["alert_threshold"]
        }


def format_stats(title: str, stats: Dict):
    """Pretty print statistics."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)

    if "error" in stats:
        print(f"  ❌ {stats['error']}")
        return

    for key, value in stats.items():
        if key == "status":
            emoji = "✅" if value == "OK" else "⚠️"
            print(f"  {emoji} Status: {value}")
        else:
            # Format key
            display_key = key.replace('_', ' ').title()
            print(f"  {display_key}: {value}")


def watch_mode(interval_sec: int = 30):
    """Live monitoring mode - refresh stats every interval."""
    collector = MetricsCollector()

    try:
        while True:
            os.system('clear')
            print(f"Manny MCP Performance Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Refreshing every {interval_sec}s (Ctrl+C to exit)\n")

            # Show all metrics
            format_stats("Build Performance", collector.get_build_stats())
            format_stats("Cache Performance", collector.get_cache_stats())
            format_stats("Search Engine", collector.get_search_stats())
            format_stats("Command Latency (last 60 min)", collector.get_command_stats())

            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


def main():
    parser = argparse.ArgumentParser(description="Manny MCP Performance Monitor")
    parser.add_argument("--metric", choices=["builds", "cache", "search", "state", "commands", "all"],
                        default="all", help="Metric to display")
    parser.add_argument("--watch", action="store_true", help="Live monitoring mode")
    parser.add_argument("--interval", type=int, default=30, help="Watch mode refresh interval (seconds)")

    args = parser.parse_args()
    collector = MetricsCollector()

    if args.watch:
        watch_mode(args.interval)
        return

    # Single metric display
    if args.metric == "builds" or args.metric == "all":
        format_stats("Build Performance", collector.get_build_stats())

    if args.metric == "cache" or args.metric == "all":
        format_stats("Cache Performance", collector.get_cache_stats())

    if args.metric == "search" or args.metric == "all":
        format_stats("Search Engine", collector.get_search_stats())

    if args.metric == "state" or args.metric == "all":
        print("\n⏳ Monitoring state file writes for 1 minute...")
        format_stats("State File Write Frequency", collector.get_state_write_frequency(window_minutes=1))

    if args.metric == "commands" or args.metric == "all":
        format_stats("Command Latency (last 60 min)", collector.get_command_stats())

    print()


if __name__ == "__main__":
    main()
