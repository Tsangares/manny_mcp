#!/home/wil/manny-mcp/venv/bin/python3
"""
CLI to run YAML routines.

Usage:
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml --loops 3
    ./run_routine.py routines/skilling/cooking_lumbridge.yaml --start-step 5
"""
import argparse
import asyncio
import json
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


async def run_routine(routine_path: str, max_loops: int = 1, start_step: str = '1', account_id: str = None):
    """Run a YAML routine and return results."""
    from mcptools.tools import routine, commands, monitoring
    from mcptools.config import ServerConfig

    config = ServerConfig.load()

    async def send_cmd(cmd, timeout, account=None):
        with open(config.get_command_file(account), 'w') as f:
            f.write(cmd + '\n')
        await asyncio.sleep(0.1)
        try:
            with open(config.get_response_file(account)) as f:
                return json.load(f)
        except:
            return {"status": "sent"}

    # Initialize dependencies in correct order
    commands.set_dependencies(send_cmd, config)
    monitoring.set_dependencies(None, config)
    routine.set_dependencies(send_cmd, config)

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
    print(f"\nFinal State:")
    print(f"  Plane: {result.get('final_plane')}")
    print(f"  Inventory items: {result.get('final_items')}")

    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Run a YAML routine')
    parser.add_argument('routine', help='Path to routine YAML file')
    parser.add_argument('--loops', type=int, default=1, help='Number of loops (default: 1)')
    parser.add_argument('--start-step', type=str, default='1', help='Starting step ID (default: 1)')
    parser.add_argument('--account', type=str, default=None, help='Account ID (e.g., "main")')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of formatted')

    args = parser.parse_args()

    if not os.path.exists(args.routine):
        print(f"Error: Routine file not found: {args.routine}")
        sys.exit(1)

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
