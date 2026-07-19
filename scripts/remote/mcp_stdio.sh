#!/usr/bin/env bash
# mcp_stdio.sh — launch the manny_mcp stdio MCP server on THIS host for an
# LLM session reaching in over `ssh -T <host> /abs/path/mcp_stdio.sh`.
#
# WHY a wrapper (Track A / remote MCP parity):
#   The MCP transport is pure stdio (server.py). Over bare ssh the remote login
#   shell on diort is FISH and the working dir is $HOME, so two things must be
#   pinned deterministically before exec'ing python:
#     1. cwd -> the repo, so relative imports / session files resolve.
#     2. RUNELITE_MCP_CONFIG -> an absolute config path, because ServerConfig.load()
#        defaults to `Path.cwd()/config.yaml` and would FileNotFoundError otherwise
#        (config.py). We point it at config.diort.yaml (display :2, host paths).
#   Invoked as a single absolute-path argv it is immune to fish quoting: ssh runs
#   `/home/wil/Desktop/manny_mcp/scripts/remote/mcp_stdio.sh` directly, no shell
#   parsing of a multi-line command.
#
# stdout MUST stay protocol-clean (JSON-RPC frames only). This script prints
# nothing to stdout; `exec` replaces the shell so python owns the fds. Any
# diagnostics from python go to stderr, which ssh keeps separate.
set -euo pipefail

cd /home/wil/Desktop/manny_mcp
export RUNELITE_MCP_CONFIG="$PWD/config.diort.yaml"
exec venv/bin/python server.py
