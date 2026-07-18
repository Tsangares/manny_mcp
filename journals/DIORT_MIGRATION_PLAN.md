# Diort Migration Plan — Moving the Manny RuneLite Client Off the Laptop

**Date:** 2026-07-18
**Author:** recon + plan by Claude (read-only recon on diort; nothing executed there)
**Status:** PLAN ONLY — no prereqs installed, no files copied, no creds touched, nothing launched on diort.

## Why

This laptop (`taxi`) hits **90C package temp within ~2 minutes** of running the manny
client, every time, across 3 live gates today (see `REFACTOR_CAMPAIGN_HANDOFF.md`,
"THERMAL CEILING CONFIRMED" section, 2026-07-18). `renice 15` helps scheduling, not
heat; `cpulimit` isn't installed. The client pins ~79% of a CPU core continuously
(software rendering on Xvfb) and this machine's cooling cannot sustain that for a full
unattended grind (76-tile GOTO + 200-kill loop = many minutes). Short, careful bursts
work; a real grind does not. `diort` (10.0.0.13, also reachable via Tailscale at
`100.91.42.96`) is the candidate stable host — same LAN, residential IP (no
datacenter-IP ban risk), and per recon below, meaningfully better thermal headroom.

---

## Go/No-Go Verdict: **GO**

diort is a viable host. Evidence:

**Hardware/thermal — GOOD.** diort is a 2011 21.5" iMac (Intel Core i5-2400S @
2.50GHz, 4 cores/4 threads, AMD Radeon HD 6650M-class GPU, Apple SMC fan controller —
confirmed by `applesmc-isa-0300` in `sensors` output and DMI chassis_type=13
"All-in-One"). This is a **desktop-class thermal design** with real active fan
cooling (ODD/HDD/CPU fans, fan curve 1200-4350 RPM), unlike the laptop's cramped
chassis. At idle/light-load (loadavg 0.31/0.33/0.66, 49 days uptime) `coretemp`
reports CPU package **50C** against a **high=80C / crit=86C** threshold, with the CPU
fan barely spun up (1199 RPM vs. 1200 min). That's a large thermal margin compared to
the laptop's 90C-in-2-minutes behavior — diort's cooling has real headroom to work
with. It cannot be *proven* stable under sustained manny-client load without the live
grind test (see verification steps below), but the design and idle numbers strongly
favor it over the laptop.

**Software — GOOD, with one required prereq.** diort is Arch Linux (rolling,
kernel 6.19.11-arch1-1, x86_64), same distro family as the laptop, so the known-good
recipe from `laptop_taxi_environment_revival_2026-07-17.md` transfers directly.
`jdk21-openjdk 21.0.11.u10-1` is available in the official Arch `extra` repo
(confirmed via `pacman -Ss jdk21`) — a single-package install, not a hand-build.
`Xvfb`, `x11vnc`, `vncserver`, `ffmpeg`, `git`, `rsync`, `python3` (3.14.4) are all
already present.

**Network — GOOD.** diort has working internet (ping to 1.1.1.1: 12.3ms, 0% loss)
and is on Tailscale (`100.91.42.96`), giving the orchestrator a stable route that
doesn't depend on LAN topology.

**Access — GOOD.** SSH key-based login works as `wil` (diort is one of the user's own
machines — same account, not a shared/foreign box). Passwordless sudo is available
(`sudo -n true` exits 0), so prereq installs won't need an interactive password.

**Caveats to weigh (not blockers, but worth noting in the verdict):**
- RAM: 15Gi total, only 1.5Gi "free" / 6.5Gi "available", and **5.3Gi of swap already
  in use**. diort is the user's actively-used general desktop (couchdb, containerd/
  docker, bolt/thunderbolt, dbus-broker, and more running — `systemctl status` shows
  385 loaded units, 1 failed, state "degraded"). Client memory footprint on the laptop
  is capped at `-Xmx1536m -XX:MaxMetaspaceSize=192m`, which should fit, but don't
  assume diort has idle headroom the way a dedicated host would — check `free -h`
  again right before the first live launch.
- Disk: root filesystem 439G, 229G free (45% used) — plenty of room for the jar
  (~39MB) + manny_mcp (a few hundred MB with venv). Not a concern.
- This is a shared-use machine, not a dedicated bot box — treat the manny client as a
  guest process (stop it when not actively gating/grinding), same discipline as
  `client.sh`'s existing thermal-guard policy already encodes.

### JDK version verdict (the core technical question)

The laptop's `client.sh` pins `JAVA_BIN="/usr/lib/jvm/java-21-openjdk/bin/java"`
because gradle 8.8 (used to *build* the plugin) breaks on JDK 26, and the shaded jar's
compiled class files are major version 65 (= Java 21 target).

- **JDK 17 present on diort — will NOT run the jar.** A JVM can only run class files
  at or below its own major version. Java 17 = class major 61 < 65 required. Attempting
  this fails hard with `UnsupportedClassVersionError`. Ruled out.
- **JDK 26 present on diort — would plausibly START, but is NOT the recommended
  path.** JVMs are backward-compatible (a JDK 26 runtime *can* execute major-65
  bytecode), so `java-26-openjdk` might well run the jar. But RuneLite/manny rely on
  reflective access into `java.desktop`/AWT/Swing internals that has historically
  needed version-specific `--add-opens`/`--add-exports` handling, and the only
  *known-good* combination (proven today, twice, on this laptop) is JDK 21. Diort's
  JDK 26 is untested territory for this jar — a bad place to debug thermal-load gate
  tests.
- **Recommendation: install `jdk21-openjdk` on diort to match the proven laptop
  environment exactly.** This is a single official-repo package, no build step, no
  system-default change needed (installs alongside 17/26; launch script points at the
  absolute binary path, same pattern as `client.sh`'s existing fallback logic).

**Single most important unknown:** whether diort's cooling *actually* holds under
sustained load — the idle numbers (50C, fans barely spinning) are a strong positive
signal but the only real proof is the live nav-gate + grind test in the verification
steps below. Budget for that as the true go/no-go checkpoint, not this recon.

---

## Recon Summary (read-only, diort)

| Item | Finding |
|---|---|
| OS | Arch Linux (rolling), kernel `6.19.11-arch1-1`, x86_64 |
| CPU | Intel Core i5-2400S @ 2.50GHz, 4 cores (`nproc`=4) |
| Chassis | DMI type 13 = "All-in-One" — 2011 21.5" iMac (AppleSMC fan controller, AMD Radeon HD 6650M-class GPU: `01:00.0 VGA ... AMD/ATI Whistler`) |
| RAM | 15Gi total, 9.1Gi used, 1.5Gi free, 6.5Gi available; swap 19Gi (5.3Gi in use) |
| Disk | `/` 439G, 229G avail (45% used); `/tmp` is tmpfs 7.8G (1.2G used); separate `/mnt` volume 458G/267G avail |
| JDKs present | `java-17-openjdk`, `java-26-openjdk` — **no java-21** |
| JDK21 installable | Yes: `extra/jdk21-openjdk 21.0.11.u10-1` (official repo, `pacman -Ss jdk21` confirmed, NOT installed) |
| Xvfb | Present, `/usr/bin/Xvfb` |
| VNC/viewer | `x11vnc` and `vncserver` both present; `ffmpeg` present (no `mjpg_streamer`, not needed — laptop's mjpeg viewer uses `import`/ImageMagick pattern, not mjpg_streamer) |
| Thermal | `applesmc` + `coretemp` sensors present. Idle: package 50C (high=80C, crit=86C), fans ~1200 RPM (near minimum) |
| Uptime/load | 49 days up, loadavg 0.31/0.33/0.66 — lightly loaded |
| sudo | Passwordless (`sudo -n true` → exit 0) |
| Network | Internet reachable (ping 1.1.1.1, 12.3ms, 0% loss); Tailscale up at `100.91.42.96` |
| SSH user | `wil` (same account as laptop — this is the user's own machine) |
| python3 | `/usr/bin/python3`, 3.14.4; `python-pip`/`python-virtualenv` **not** installed as system packages (stdlib `venv` module should still work; may need `python-pip` for `ensurepip` inside the venv — verify at prereq-install time) |
| git / rsync | Both present |
| Misc | Machine also runs couchdb, docker/containerd, bolt (thunderbolt), 385 systemd units, 1 failed unit (degraded state) — general-purpose desktop, not a dedicated bot host |

---

## Prereqs to Install on diort (PLAN — not executed)

1. **JDK 21**: `sudo pacman -S jdk21-openjdk` (matches laptop exactly; official repo,
   no AUR/build needed).
2. **Python venv tooling** (only if `python -m venv` or the resulting `pip` fails —
   verify first, don't blind-install): `sudo pacman -S python-pip` if `ensurepip`
   inside a fresh venv errors out. `python3.14` stdlib `venv` module itself should
   already be present as part of the base `python` package.
3. Nothing else required — `Xvfb`, `git`, `rsync`, `ffmpeg`, `x11vnc` are already
   present.

No system-wide JDK default change needed — point the launch script at the absolute
`jdk21-openjdk` binary path (same pattern `client.sh` already uses on the laptop).

---

## Exact Migration Steps

### Step 1 — Install prereqs (after user confirms Go)
```
ssh diort 'sudo pacman -S --noconfirm jdk21-openjdk'
ssh diort 'ls /usr/lib/jvm'   # confirm java-21-openjdk now present
```

### Step 2 — Copy the shaded jar + manny_mcp repo (code only, no creds)
```
# Jar (already freshly built on laptop, ~39MB)
rsync -avz --progress \
  /home/wil/Desktop/runelite/runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar \
  diort:/home/wil/Desktop/runelite-client-libs/

# manny_mcp repo — exclude venv, caches, logs, and (critically) never sync .manny/creds
rsync -avz --progress \
  --exclude 'venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' --exclude 'logs/' --exclude '*.log' \
  --exclude '.git/' \
  /home/wil/Desktop/manny_mcp/ diort:/home/wil/Desktop/manny_mcp/

# On diort: set up the venv fresh (don't copy the laptop's venv — rebuild it there)
ssh diort 'cd /home/wil/Desktop/manny_mcp && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt'
```
Note: `manny_mcp`'s `manny`/`manny_src` symlinks point at `/home/wil/Desktop/manny`
(the plugin source repo) — only needed on diort if you intend to *rebuild* the jar
there. For running the pre-built jar, this isn't required; skip it unless/until a
diort-side rebuild is wanted.

Adjust `config.yaml` on diort's copy: `java_path:` →
`/usr/lib/jvm/java-21-openjdk/bin/java`; `display:` → whatever Xvfb display is chosen
(recommend keeping `:2` for parity with the laptop recipe and `client.sh`'s hardcoded
`XVFB_DISPLAY=":2"`).

### Step 3 — [USER-APPROVAL GATE] Copy credentials + first login

**STOP. Do not do this step without the user's explicit go-ahead in that moment.**
This is the one consequential, account-affecting step: it puts live Jagex session
credentials on a second machine and triggers what Jagex sees as a login from a new
IP/device fingerprint (a residential IP, which is the *point* of this migration, but
still a new device — first login on any new host carries a small inherent risk
profile change).

When the user approves:
```
# Copy ONLY ~/.manny/credentials.yaml, via scp (not rsync -a, to avoid accidentally
# pulling in other .manny/ contents like training_data/)
scp /home/wil/.manny/credentials.yaml diort:/home/wil/.manny/credentials.yaml
```
(`~/.manny/` doesn't exist yet on diort — `ssh diort 'mkdir -p ~/.manny'` first, or
let `scp` create the leaf file if the parent exists... confirm parent dir exists
before this copy.)

First login should be done **watched** (via the viewer, see below) on whichever
account is least consequential to verify the client comes up cleanly on diort's
JDK21/Xvfb stack before trusting it with a real grind account.

### Step 4 — Xvfb + launch recipe (adapted for diort)

Port `client.sh` to diort essentially unchanged — it already has the thermal guard
(refuses ≥88C, warns ≥80C), the `pgrep -x java` + environ-based account detection
(not `pgrep -f`, which self-matches), and the renice-to-15 policy. Only path/JDK
constants change:

```bash
RUNELITE_DIR="/home/wil/Desktop/runelite-client-libs"   # or wherever the jar landed
JAVA_BIN="/usr/lib/jvm/java-21-openjdk/bin/java"
XVFB_DISPLAY=":2"
```
Everything else in `client.sh` (thermal guard, stop/start/restart, IPC-safe kill
detection, `renice 15`, login-wait loop) is host-agnostic bash and should work as-is
once copied. Launch env vars unchanged: `DISPLAY=:2`, `_JAVA_OPTIONS="-Xmx1536m
-XX:MaxMetaspaceSize=192m"`, `MANNY_ACCOUNT_ID`, `JX_CHARACTER_ID`,
`JX_SESSION_ID` (the latter two pulled from `credentials.yaml` via
`mcptools/credentials.py`, never echoed — same as today).

```
ssh diort '/home/wil/Desktop/manny_mcp/scripts/client.sh start new'
```

### Step 5 — Verify login
```
ssh diort 'tail -f /tmp/runelite.log'   # watch for "Game state is now LOGGED_IN"
```
or via `client.sh status` for the account/pid/thermal summary.

### Step 6 — Run the DEFECT-19b nav gate + short grind test

This is the actual proof that diort solves the problem, not just recon numbers:

1. **Nav gate**: `GOTO 3235 3295 0` (the Lumbridge chicken coop route, 76 tiles) —
   per `REFACTOR_CAMPAIGN_HANDOFF.md`, this previously walked ~35 tiles before hitting
   DEFECT-19b's 30s absolute NAV-MULTI timeout (fixed but pending a full-length live
   gate). On diort, this must now walk the **FULL 76 tiles** to the coop
   uninterrupted — watch for the "[NAV-API] Pathfinder API unavailable but LINE OF
   SIGHT CLEAR" log line, confirm NO `[Global A*]` churn, confirm arrival.
2. **Short grind test**: chain `combat/chicken_killer_training.yaml` (already fixed:
   correct coords, `await_condition location:3235,3295`, `timeout_ms 120000`) for a
   handful of kills via `run_routine.py`, monitoring thermal (`client.sh status`)
   throughout. This is the test that was blocked on the laptop by the 90C/2min
   ceiling — on diort, watch whether package temp stabilizes well under 88C over
   several minutes of sustained load (the real proof, vs. today's idle-number
   inference).
```
ssh diort 'cd /home/wil/Desktop/manny_mcp && ./run_routine.py routines/combat/chicken_killer_training.yaml --loops 3 --account new'
```
Run this from the laptop over SSH (drives diort remotely) or directly on diort via
another SSH session — either way `run_routine.py` needs to execute ON diort since IPC
is local-file-based (see next section).

---

## How the Orchestrator (this laptop) Drives diort

The manny plugin's IPC is **local-file based**: `/tmp/manny_<acct>_command.txt`,
`_response.json`, `_state.json`, `_location_history.json`, plus
`/tmp/manny_combat_config.json` for kill-loop config (confirmed in
`mcptools/config.py` / `session_manager.py`). There is no network transport in this
loop today — `run_routine.py`, `mcptools/*`, and the RuneLite client all read/write
the same local `/tmp` files.

**Recommended approach: run both the client AND `run_routine.py`/MCP server ON
diort; drive it from the laptop purely via SSH.** This is the cleanest option because
it requires zero IPC-layer changes — the files stay local to whichever machine has
the client, exactly like today.

- Interactive/manual control: `ssh diort '<command>'` wrapping whatever `client.sh` /
  `run_routine.py` / individual mcptools calls are needed.
- If MCP-server-driven control from this laptop's Claude session is wanted (rather
  than raw SSH), two sub-options:
  - (a) **SSH-wrapped MCP tools** — keep the MCP server itself running on the laptop
    but have its tool implementations SSH out to diort for anything that touches the
    IPC files or process lifecycle. More invasive, not recommended as a first cut.
  - (b) **Run the MCP server ON diort too**, and have the laptop's Claude Code
    session connect over SSH (or Tailscale) as if diort were the dev box for this
    project. Simpler, keeps everything colocated the way it works today, just
    physically on diort. This is the recommended long-term shape if orchestration
    needs to stay LLM-driven rather than manual SSH.

Either way, avoid trying to forward/share `/tmp/manny_*` files over the network
(sshfs/NFS) — it adds latency and failure modes to a control loop that's already
timing-sensitive (see DEFECT-19b's timeout tuning). Keep IPC local to diort.

---

## Viewing the Client Remotely

diort already has both pieces the laptop uses conceptually, plus more options since
it has a full VNC stack:

1. **mjpeg viewer (same as laptop today)**: `scripts/mjpeg_viewer.py` uses
   `DISPLAY=<d> import -window root ... jpg:-` (ImageMagick), no GPU/X extensions
   needed — should work identically over Xvfb `:2` on diort.
   ```
   ssh diort 'cd /home/wil/Desktop/manny_mcp && MJPEG_DISPLAY=:2 MJPEG_PORT=8787 MJPEG_FPS=1.5 python3 scripts/mjpeg_viewer.py &'
   ```
   Then browse `http://100.91.42.96:8787/view?display=:2` over Tailscale (works from
   anywhere, not just LAN) or `http://10.0.0.13:8787/view?display=:2` on LAN.
2. **x11vnc (diort has this, laptop setup doc doesn't mention it)**: heavier but gives
   full interactive access if ever needed for manual debugging:
   ```
   ssh diort 'x11vnc -display :2 -localhost -forever &'
   ssh -L 5900:localhost:5900 diort   # tunnel, then point a VNC client at localhost:5900
   ```
   Prefer the mjpeg viewer for routine monitoring (lighter weight); reserve x11vnc for
   hands-on debugging sessions.

---

## Rollback / Risks

- **Ban considerations**: moving to diort's residential IP is the *safety
  improvement*, not a risk — it removes the datacenter-IP correlation entirely. The
  actual residual risk is having live session credentials on **two machines**
  instead of one; treat the laptop's copy as primary/authoritative and diort's as a
  working copy, and don't run the same account simultaneously on both (duplicate
  login already gets JVM-killed by Jagex per `client.sh`'s own comments — this is
  self-enforcing, not just a policy).
- **Fallback**: keep the laptop fully intact as a short-burst/dev-loop environment —
  nothing about this migration requires decommissioning it. Short-range routines
  (already at the resource, no long GOTO) remain fine there per the campaign
  handoff's own conclusion.
- **Rollback if diort underperforms thermally**: if the live grind gate shows temps
  climbing toward the 88C refuse threshold under sustained load (disproving the idle
  read), `client.sh stop` immediately (same thermal-guard script, already ported),
  fall back to laptop short-burst-only operation, and reassess — options at that point
  include a fan-curve/SMC tuning look (Apple SMC fan control on Linux is a known
  quantity, `applesmc` module already loaded) or evaluating a different host.
- **Shared-machine risk**: diort runs other real services (couchdb, docker,
  containerd) — a runaway/leaked manny client process could compete for resources
  with those. `client.sh`'s existing `renice 15` + explicit `stop` discipline
  mitigates this; consider adding a cgroup/systemd-run memory+CPU cap on diort as a
  future hardening step (not required for the initial gate).
- **Credential hygiene**: never `rsync -a` the whole `~/.manny/` directory (it also
  has `training_data/`); copy only `credentials.yaml` explicitly, and only after the
  user's go-ahead at the Step 3 gate.

---

## Open Items / Not Yet Verified

- Whether `python -m venv` on diort's Python 3.14.4 produces a working `pip` without
  installing `python-pip` separately — check at prereq time, not assumed here.
- Whether diort actually holds temperature under a real multi-minute grind (the idle
  50C reading is a strong positive signal, not proof) — this is exactly what Step 6's
  live gate is for.
- Whether AppleSMC fan control is fully functional under Linux on this hardware (fans
  were near-idle at recon time, consistent with light load, but worth watching during
  the live gate that fans actually ramp under load rather than staying pinned low).
