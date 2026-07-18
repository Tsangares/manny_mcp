# Remote Client Architecture — Machine-Agnostic manny Run Layer

**Date:** 2026-07-18
**Status:** DESIGN + PROTOTYPE. No live testing, no git commit. Existing
`scripts/client.sh`, `run_routine.py`, and `mcptools/` are UNMODIFIED — new files
sit alongside and generalize them.

## Problem

The manny RuneLite client is currently welded to one machine (the laptop `taxi`),
which overheats (90C in ~2min under grind), can crash, and carries a single fixed
egress IP. We want to run the client on **any** host — starting with `diort`, later
others (`mat`, …) — driven **uniformly over SSH**, so no single machine is a point
of failure and we can pick egress IP / thermal headroom per run.

`journals/DIORT_MIGRATION_PLAN.md` already worked out the diort move by hand. This
doc **generalizes those manual steps into a repeatable per-host flow** and ships a
thin prototype.

## The load-bearing constraint (confirmed in code)

The plugin's IPC is **local-file based**. `mcptools/config.py` defines the paths as
`/tmp/manny_<acct>_command.txt`, `_response.json`, `_state.json`,
`_location_history.json` (see `get_command_file` / `get_response_file` /
`get_state_file`, lines 116-143). `mcptools/transport.py` writes the command file
atomically and waits for the plugin to delete it + emit the response file — all
**local filesystem** operations, no network transport (transport.py:195-322).

**Therefore:** the client, `run_routine.py`, and the MCP tooling must all run **on
the same machine** — the target host. The orchestrator (a Claude session on the
laptop) never touches those files directly; it only issues SSH commands. Do **not**
try to share `/tmp/manny_*` over sshfs/NFS — it adds latency and failure modes to a
timing-sensitive control loop (DEFECT-19b timeout tuning). Keep IPC host-local.

This is the whole design in one sentence:

> **Run the client + runner ON the host; drive it purely via SSH from the laptop.**

## Design principle: thin SSH + a YAML, not a framework

The entire remote layer is: a **host registry** (`hosts.yaml`) + one **abstraction
function** (`run_on_host`) that either runs a command locally or wraps it in
`ssh <host>`. Everything else — start/stop/status, running routines, ad-hoc
commands, the viewer — is that one function applied to the existing scripts. Local
and remote are the *same code path* with the ssh wrapper toggled by `local: true`.

---

## 1. Host registry — `scripts/remote/hosts.yaml`

One entry per machine. Schema (full commentary in the file):

| field | meaning |
|---|---|
| `local` | `true` = the orchestrator box itself; run commands directly (no ssh). Exactly one host. |
| `ssh` | ssh destination: alias, `user@host`, or `user@tailscale-ip`. Ignored if local. |
| `jdk` | absolute path to the **Java 21** binary (must run the major-65 shaded jar; JDK17 will not). |
| `display` | Xvfb display, e.g. `:2` (parity with `client.sh`). |
| `staging_dir` | where the `manny_mcp` repo lives on the host. |
| `runelite_libs` | dir containing `*-shaded.jar` on the host. |
| `venv_python` | python inside the host venv (`<staging_dir>/venv/bin/python`). |
| `temp_refuse_c` / `temp_warn_c` | thermal thresholds (per-host — a hot iMac and a cool desktop differ). |
| `egress` | human note on outbound IP identity (ban-risk surface). Documentation, not enforced. |
| `viewer_host` / `viewer_port` | where to reach the mjpeg viewer (LAN/Tailscale IP; `127.0.0.1` for local). |
| `notes` | free-form. |

Concrete entries shipped: **`laptop`** (local, mirrors today's flow) and **`diort`**
(remote, Tailscale/LAN, residential IP, iMac thermal). A commented **`mat`** template
is included for phase 2.

Why per-host `jdk`/`libs`/`display` instead of reading `config.yaml`? Because
`config.yaml` is one file with laptop paths; the jar lives at a *different* path on
diort (`~/Desktop/runelite-client-libs`). The registry captures exactly the handful
of things that vary per machine, and `client_remote.sh` takes them as env overrides.

---

## 2. `provision <host>` — `scripts/remote/provision.sh`

Idempotent, re-runnable staging that codifies DIORT_MIGRATION_PLAN Steps 1-2,4 plus
the perf config. Runs **from** the orchestrator, pushes **to** the host. Steps (each
guarded so a re-run is a cheap no-op):

1. **JDK 21** — skip if `jdk` path already executable; else
   `sudo pacman -S --needed --noconfirm jdk21-openjdk`.
2. **Shaded jar** — `rsync` the local `*-shaded.jar` into the host's `runelite_libs`.
3. **Repo** — `rsync` `manny_mcp/` excluding `venv/ .git/ __pycache__/ logs/ *.log
   .env` (**never** creds).
4. **Venv** — create `venv` if absent, then `pip install -r requirements.txt`
   (idempotent refresh).
5. **RuneLite perf config** — replicate the proven keys into every host
   `~/.runelite/profiles2/*.properties`, backing up once to `.bak-manny-perf`:
   ```
   runelite.gpuplugin=false
   fpscontrol.limitFps=true
   fpscontrol.maxFps=30
   fpscontrol.drawFps=false
   ```
   These take Xvfb software-render CPU from ~374% (llvmpipe) to ~46% — **mandatory
   on every Xvfb host** or it cooks the CPU (source: REFACTOR_CAMPAIGN_HANDOFF +
   wave3_display_isolation journals). If the host has never launched RuneLite yet,
   `profiles2/*.properties` won't exist — provision notes this and you re-run once
   after the first launch.

Deliberately **excludes credentials** — that is a separate user-gated step (§6).

---

## 3. Remote launch/stop — `scripts/remote/client_remote.sh`

A **parameterized port** of `client.sh`. `client.sh` hardcodes `RUNELITE_DIR` /
`JAVA_BIN` / `XVFB_DISPLAY` for the laptop; `client_remote.sh` reads them from env
(`RUNELITE_LIBS`, `JAVA_BIN`, `XVFB_DISPLAY`, `TEMP_REFUSE_C`, `TEMP_WARN_C`,
`REPO_DIR`) with the laptop values as defaults. It preserves every hard-won lesson
from `client.sh` verbatim:

- `pgrep -x java` (exact comm) + `MANNY_ACCOUNT_ID` from `/proc/<pid>/environ` — the
  self-match-safe client detection.
- thermal guard (refuse ≥ refuse_c, warn ≥ warn_c) — reads the **host's own** temp.
- kill-existing-first (duplicate-login JVM kill), SIGTERM→SIGKILL stop.
- creds pulled via the host venv (`mcptools.credentials`), **never echoed**.
- `renice 15` immediately after launch; login-wait loop for `LOGGED_IN`.

One addition over `client.sh`: the temp reader tries `x86_pkg_temp` first (laptop),
then falls back to a coretemp `Package id` hwmon input — diort's iMac reports there,
not via the x86_pkg_temp thermal zone.

`mannyctl` invokes it over SSH with the host's env prefix. **For localhost it
behaves like today** (same logic, no ssh). Subcommands: `status | stop |
start <acct> | restart <acct>`.

> This file does **not** touch `client.sh`. On the laptop you can keep running
> `client.sh` directly. See the phased plan for the eventual convergence.

---

## 4. Remote driving / IPC — the recommended pattern

The orchestrator drives via **`scripts/remote/mannyctl`**, the thin wrapper. Its one
abstraction, `run_on_host`, runs a command string locally (`bash -lc`) for local
hosts or `ssh <host> '<cmd>'` for remote ones. Everything is built on that.

**Recommended IPC pattern = option (a): run the runner ON the host.**

```
mannyctl <host> run routines/combat/chicken_killer_training.yaml --loops 3 --account new
```

`mannyctl` translates this to (for a remote host):

```
ssh <host> 'cd <staging_dir> && <venv_python> run_routine.py routines/... --loops 3 --account new'
```

`run_routine.py` executes on the host, reads/writes the host's local `/tmp/manny_*`
files, talks to the local client — **zero IPC-layer changes**. This is why the
constraint in the intro matters: colocating the runner with the client is what keeps
the whole existing transport working untouched.

**Ad-hoc single command = option (b), cleaned up:** `mannyctl <host> cmd <acct>
<COMMAND...>` runs a one-liner on the host that calls
`transport.send_command_sync(...)` — the **same** rid-correlated path
`run_routine.py` uses — and prints the JSON response. This is better than raw
`printf > /tmp/..._command.txt` + `cat ..._response.json` because it reuses the
atomic-write + request-id correlation + delivery-check logic in `transport.py`
instead of racing the plugin's ~500ms poller by hand.

`mannyctl <host> <cmd>` command surface:

| command | does |
|---|---|
| `list` | print the host registry |
| `provision` | run `provision.sh` for the host |
| `push-creds` | **user-gated** creds copy (§6) |
| `start <acct>` / `stop` / `restart <acct>` / `status` | client lifecycle via `client_remote.sh` |
| `temp` | quick remote package temp |
| `run <routine> [args]` | `run_routine.py` on the host (recommended IPC path) |
| `cmd <acct> <COMMAND...>` | one rid-correlated command + response |
| `logs [acct] [n]` | tail the client log on the host |
| `viewer [port]` | start the mjpeg viewer on the host, print the URL |
| `exec <shell...>` | escape hatch |

---

## 5. Monitoring + viewing

- **Health/thermal:** `mannyctl <host> status` (client pids + host temp/load) and
  `mannyctl <host> temp`. The per-host thresholds live in `hosts.yaml`. Poll from
  the orchestrator on the existing monitor cadence (30-60s).
- **Viewer:** `mannyctl <host> viewer` starts the existing `scripts/mjpeg_viewer.py`
  on the host (detached, `MJPEG_DISPLAY=<host display>`) and prints
  `http://<viewer_host>:<port>/view?display=<display>`. For diort that's the
  Tailscale IP so it works off-LAN. `x11vnc` remains available on hosts that have it
  for hands-on debugging (`ssh -L 5900:localhost:5900 <host>` + `x11vnc -display :2
  -localhost`), but prefer mjpeg for routine monitoring (lighter).

---

## 6. Security note (called out, not solved insecurely)

Credentials (`~/.manny/credentials.yaml`, containing JX character/session tokens)
**must** reach the target host — the client logs in with them (`client_remote.sh`
step 4 reads them via `mcptools.credentials` on the host). The least-bad handling:

- **Explicit, user-gated copy only.** `mannyctl <host> push-creds` prompts for a
  typed `yes` (it is an account-affecting new-device/new-IP login), then `scp`s
  **only** `credentials.yaml` (never `rsync -a ~/.manny/` — that also holds
  `training_data/`), and `chmod 600`s it on the far side under a `chmod 700 ~/.manny`.
- **Never in the repo or jar.** `provision.sh`'s repo rsync excludes `.env`; creds
  are never part of any synced tree.
- **Never logged / printed.** `client_remote.sh` pulls tokens into the JVM's environ
  and immediately `unset`s the shell vars, exactly like `client.sh`; nothing echoes
  them. The orchestrator must not print tokens either — `mannyctl` has no path that
  reads or emits a token.
- **Two-machine hygiene:** treat the laptop copy as authoritative, the host copy as
  a working copy; never run the same account on two hosts at once (Jagex
  duplicate-login kill is self-enforcing but noisy). Residual risk of the migration
  is *credentials on N machines*, not the residential IP (which is the safety win).
- Future hardening (not required now): push creds just-in-time and remove them after
  a run / age-encrypt at rest / add a cgroup+memory cap via `systemd-run` on shared
  hosts like diort.

---

## Local ↔ remote unification: what stays, what generalizes

| Existing (unchanged) | Generalized-alongside (new) |
|---|---|
| `scripts/client.sh` — laptop launcher, hardcoded paths | `scripts/remote/client_remote.sh` — same logic, env-parameterized, any host |
| `run_routine.py` — runs the routine engine locally | invoked **on the host** by `mannyctl run` (no change to the file) |
| `mcptools/transport.py` + `config.py` — local-file IPC | untouched; runner is colocated so paths stay local |
| manual `ssh diort '...'` from DIORT_MIGRATION_PLAN | `mannyctl <host> <cmd>` — one wrapper, registry-driven |
| by-hand diort setup | `scripts/remote/provision.sh` — idempotent |
| `scripts/mjpeg_viewer.py` | `mannyctl <host> viewer` starts it remotely |

Nothing is deleted or rewritten. The laptop's working flow is fully intact; the
remote layer is additive.

---

## Phased implementation plan

**Phase 0 — prototype (this deliverable, done).** `hosts.yaml`, `mannyctl`,
`client_remote.sh`, `provision.sh` written and syntax/parse-checked. `mannyctl list`
and local `temp`/`status` verified without SSH.

**Phase 1 — get diort running via this layer.**
1. `mannyctl diort provision` (installs jdk21, syncs jar+repo, builds venv, sets perf
   config). Re-run after diort's first RuneLite launch so `profiles2` perf keys land.
2. `mannyctl diort push-creds` (user present, types `yes`).
3. `mannyctl diort start new`, watch via `mannyctl diort viewer` +
   `mannyctl diort logs new`.
4. Run the DIORT_MIGRATION_PLAN Step-6 gate through the wrapper:
   `mannyctl diort run routines/combat/chicken_killer_training.yaml --loops 3
   --account new`, monitoring `mannyctl diort temp` throughout — this is the real
   thermal go/no-go.
5. Resolve the live TODOs in the prototype (see below).

**Phase 2 — second host + convergence refactor.**
- Add a real `mat` entry; `mannyctl mat provision` should work with **zero code
  changes** (the proof the abstraction is right).
- **Refactor to converge the two launchers:** make `client.sh` itself read the same
  env overrides `client_remote.sh` uses (defaulting to today's laptop constants), then
  reduce `client_remote.sh` to a thin shim or delete it — one launcher, param-driven.
  This is the only planned change to an existing file, and only after Phase 1 proves
  the parameter set is correct. Until then, keep the two in sync by hand (they share
  identical logic; only path-sourcing differs).
- Optional: teach the MCP server / `MultiRuneLiteManager` a `host` dimension so
  LLM-driven tools can target a remote host directly, rather than only via `mannyctl`
  shell-outs. Bigger change; defer until the shell path is proven.

### Live TODOs left in the prototype (need a real host)
- `mannyctl cmd`: confirm `${var@Q}` bash quoting survives the SSH hop on the target's
  bash version; fall back to a stdin-heredoc form if not.
- `provision.sh`: confirm `config.yaml` (shipped as-is) has no laptop-only absolute
  path that breaks `ServerConfig.load()` on the host; confirm `python3 -m venv` on
  diort's Python 3.14 yields a working `pip` (else `sudo pacman -S python-pip`).
- Verify diort's temp actually reads via the coretemp `Package` hwmon fallback (the
  iMac has no `x86_pkg_temp` zone).

---

## Biggest design risk / tradeoff

**Config duplication between `client.sh` and `client_remote.sh` until the Phase-2
convergence.** The task forbids modifying `client.sh`, so the honest move was to
*copy* its battle-tested logic into a parameterized twin rather than refactor it in
place. That keeps the working local flow untouched today, but means the operational
lessons (thermal guard, `pgrep -x java` detection, duplicate-login kill, renice) now
live in **two** files that can silently drift. The mitigation is explicit: they share
identical logic, only path-sourcing differs, and Phase 2's first job is to collapse
them into one env-driven launcher once the parameter set is proven on diort. The
alternative — editing `client.sh` now — was rejected because it risks the one flow
that currently works, with no live host yet to validate against.
