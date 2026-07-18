#!/home/wil/Desktop/manny_mcp/venv/bin/python3
"""
CLI to run YAML routines.

Usage:
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml --loops 3
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml --start-step 5
"""
import argparse
import asyncio
import glob
import json
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


# Files that are references/reference-docs or the chain master itself -- never
# run them as sections when globbing a directory.
_CHAIN_SKIP_BASENAMES = {"widget_reference.yaml"}


def resolve_chain(path: str):
    """Resolve a routine argument into an ordered list of routine entries.

    Returns (entries, base_dir) where each entry is a dict with at least a
    resolved absolute ``routine`` path, plus any pass-through metadata
    (e.g. ``progress_hint``, ``description``).

    Three input shapes are supported, consistent with the existing loader:
    - A directory                -> every ``*.yaml`` in sorted (numeric-prefix)
                                    order, skipping reference docs and any
                                    ``00_*`` master file.
    - A chain YAML               -> a file with ``type: chain`` or a top-level
                                    ``chain:`` list of section routines in order.
    - A single routine YAML      -> a one-entry list (the pre-existing behavior).
    """
    import yaml

    # Directory: sorted *.yaml, skipping the master + reference docs.
    if os.path.isdir(path):
        base_dir = os.path.abspath(path)
        entries = []
        for f in sorted(glob.glob(os.path.join(base_dir, "*.yaml"))):
            base = os.path.basename(f)
            if base in _CHAIN_SKIP_BASENAMES or base.startswith("00_"):
                continue
            entries.append({"routine": f})
        return entries, base_dir

    # Chain YAML: type == chain, or a top-level `chain:` list.
    try:
        with open(path) as fh:
            doc = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        doc = None

    if isinstance(doc, dict) and (doc.get("type") == "chain" or "chain" in doc):
        base_dir = os.path.dirname(os.path.abspath(path))
        entries = []
        for item in doc.get("chain", []) or []:
            if isinstance(item, str):
                entry = {"routine": item}
            elif isinstance(item, dict):
                entry = dict(item)
            else:
                continue
            rel = entry.get("routine")
            if not rel:
                continue
            # Resolve relative to the chain file's directory (unless absolute).
            entry["routine"] = rel if os.path.isabs(rel) else os.path.join(base_dir, rel)
            entries.append(entry)
        return entries, base_dir

    # Single routine (unchanged behavior).
    return [{"routine": path}], os.path.dirname(os.path.abspath(path))


def is_chain(path: str) -> bool:
    """True if `path` should be executed as a multi-routine chain."""
    if os.path.isdir(path):
        return True
    try:
        import yaml
        with open(path) as fh:
            doc = yaml.safe_load(fh)
        return isinstance(doc, dict) and (doc.get("type") == "chain" or "chain" in doc)
    except Exception:
        return False


async def run_routine(routine_path: str, max_loops: int = 1, start_step: str = '1', account_id: str = None):
    """Run a YAML routine and return results."""
    from mcptools import transport
    from mcptools.config import ServerConfig
    from mcptools.runelite_manager import MultiRuneLiteManager
    from mcptools.tools import commands, monitoring, routine

    config = ServerConfig.load()
    transport.set_config(config)

    # Same MultiRuneLiteManager instance server.py wires in (server.py:89-95) --
    # without this, routine.py's crash-restart path (_auto_restart_client) and
    # the disconnect-relogin escalation path have no way to stop/start the
    # client and silently no-op ("No runelite_manager available, cannot
    # restart"). See journals/ENGINE_DISCONNECT_RECOVERY_SPEC.md section (a).
    manager = MultiRuneLiteManager(config)

    async def send_cmd(cmd, timeout=10000, account=None):
        """Canonical command transport (rid-correlated, atomic write).

        Replaces the old sleep-0.1s-then-read shim which returned STALE
        responses: the plugin only polls the command file every ~500ms, so a
        0.1s wait read the PREVIOUS response. transport.send_command waits for a
        request-id-matched response instead.
        """
        return await transport.send_command(
            cmd,
            account_id=account,
            await_response=True,
            timeout=timeout / 1000.0,
        )

    # Initialize dependencies in correct order (mirrors server.py:92-96 --
    # manager must be passed to both monitoring and routine so the
    # crash-restart / disconnect-relogin paths are reachable from the CLI,
    # not just from the MCP server entrypoint).
    commands.set_dependencies(send_cmd, config)
    monitoring.set_dependencies(manager, config)
    routine.set_dependencies(send_cmd, config, manager)

    # Get initial state for XP tracking
    initial_xp = {}
    try:
        with open(config.get_state_file(account_id)) as f:
            state = json.load(f)
        for skill, data in state.get('player', {}).get('skills', {}).items():
            initial_xp[skill] = data.get('xp', 0)
    except:
        pass

    # Run the routine
    result = await routine.handle_execute_routine({
        'routine_path': routine_path,
        'max_loops': max_loops,
        'start_step': start_step,
        'account_id': account_id
    })

    # Get final state
    final_xp = {}
    final_items = 0
    final_plane = None
    try:
        with open(config.get_state_file(account_id)) as f:
            state = json.load(f)
        for skill, data in state.get('player', {}).get('skills', {}).items():
            final_xp[skill] = data.get('xp', 0)
        final_items = len(state.get('player', {}).get('inventory', {}).get('items', []))
        final_plane = state.get('player', {}).get('location', {}).get('plane')
    except:
        pass

    # Calculate XP gains
    xp_gains = {}
    for skill in final_xp:
        gain = final_xp[skill] - initial_xp.get(skill, 0)
        if gain > 0:
            xp_gains[skill] = gain

    return {
        **result,
        'xp_gains': xp_gains,
        'final_items': final_items,
        'final_plane': final_plane
    }


async def run_chain(chain_path: str, max_loops: int = 1, account_id: str = None,
                    continue_on_error: bool = False):
    """Run an ordered chain of routines (chain YAML or directory).

    Each section is executed in order via ``run_routine``. By default the chain
    stops at the first failed section (later tutorial sections assume the prior
    one left the player in the right place); pass ``continue_on_error`` to run
    every section regardless.

    NOTE ON GATING: chain entries may carry a ``progress_hint`` (e.g. the
    tutorial-progress widget stage). It is currently metadata only -- logged,
    not enforced -- because active stage-gating (skip a section already
    completed) is part of the still-pending condition-dialect design. This keeps
    the chain purely sequential today while leaving the hint in the schema.
    """
    entries, _base = resolve_chain(chain_path)

    if not entries:
        return {"success": False, "error": f"No runnable routines found in chain: {chain_path}",
                "sections": []}

    sections = []
    overall_success = True
    for i, entry in enumerate(entries, start=1):
        routine_path = entry["routine"]
        hint = entry.get("progress_hint")
        label = entry.get("description") or os.path.basename(routine_path)
        print(f"\n[chain {i}/{len(entries)}] {label}"
              + (f"  (progress_hint: {hint})" if hint else ""))

        if not os.path.exists(routine_path):
            section = {"routine": routine_path, "success": False,
                       "error": f"Routine file not found: {routine_path}"}
            sections.append(section)
            overall_success = False
            if not continue_on_error:
                print(f"  ! missing routine, stopping chain: {routine_path}")
                break
            continue

        result = await run_routine(routine_path, max_loops, '1', account_id)
        section = {"routine": routine_path, **result}
        sections.append(section)

        if not result.get("success"):
            overall_success = False
            if not continue_on_error:
                print(f"  ! section failed, stopping chain: {label}")
                break

    return {
        "success": overall_success,
        "chain": chain_path,
        "sections_run": len(sections),
        "sections_total": len(entries),
        "sections": sections,
    }


def print_chain_results(result: dict):
    """Pretty print chain results."""
    print("\n" + "=" * 50)
    print("CHAIN RESULTS")
    print("=" * 50)
    print(f"\nStatus: {'SUCCESS' if result.get('success') else 'FAILED'}")
    print(f"Chain: {result.get('chain')}")
    print(f"Sections run: {result.get('sections_run')}/{result.get('sections_total')}")
    for i, section in enumerate(result.get("sections", []), start=1):
        ok = 'OK ' if section.get('success') else 'FAIL'
        name = section.get('routine_name') or os.path.basename(section.get('routine', '?'))
        line = f"  [{ok}] {i}. {name}"
        if section.get('error'):
            line += f"  - {section['error']}"
        errors = section.get('errors') or []
        if errors and not section.get('error'):
            line += f"  - {len(errors)} step error(s)"
        print(line)
    print("\n" + "=" * 50)


def print_results(result: dict):
    """Pretty print routine results."""
    print("\n" + "=" * 50)
    print("ROUTINE RESULTS")
    print("=" * 50)

    print(f"\nStatus: {'SUCCESS' if result.get('success') else 'FAILED'}")
    print(f"Routine: {result.get('routine_name', 'Unknown')}")
    print(f"Loops completed: {result.get('loops_completed', 0)}")

    if result.get('stop_reason'):
        print(f"Stop reason: {result['stop_reason']}")

    # Errors
    errors = result.get('errors', [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nErrors: None")

    # XP gains
    xp_gains = result.get('xp_gains', {})
    if xp_gains:
        print("\nXP Gained:")
        for skill, xp in xp_gains.items():
            print(f"  {skill}: +{xp}")

    # Final state
    print("\nFinal State:")
    print(f"  Plane: {result.get('final_plane')}")
    print(f"  Inventory items: {result.get('final_items')}")

    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Run a YAML routine')
    parser.add_argument('routine', help='Path to a routine YAML, a chain YAML, or a directory of routines')
    parser.add_argument('--loops', type=int, default=1, help='Number of loops (default: 1)')
    parser.add_argument('--start-step', type=str, default='1', help='Starting step ID (default: 1)')
    parser.add_argument('--account', type=str, default=None, help='Account ID (e.g., "main")')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of formatted')
    parser.add_argument('--continue-on-error', action='store_true',
                        help='For chains/directories: keep running later sections after a failure')

    args = parser.parse_args()

    if not os.path.exists(args.routine):
        print(f"Error: Routine file not found: {args.routine}")
        sys.exit(1)

    # Chain / directory mode: run an ordered sequence of routines.
    if is_chain(args.routine):
        print(f"Running chain: {args.routine}")
        print(f"Loops/section: {args.loops}, Account: {args.account or 'default'}, "
              f"continue_on_error: {args.continue_on_error}")
        result = asyncio.run(run_chain(args.routine, args.loops, args.account,
                                       args.continue_on_error))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_chain_results(result)
        sys.exit(0 if result.get('success') else 1)

    print(f"Running: {args.routine}")
    print(f"Loops: {args.loops}, Start step: {args.start_step}, Account: {args.account or 'default'}")

    result = asyncio.run(run_routine(args.routine, args.loops, args.start_step, args.account))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_results(result)

    # Exit with error code if routine failed
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
