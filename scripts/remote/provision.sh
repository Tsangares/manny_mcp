#!/usr/bin/env bash
# provision.sh <host> — idempotent staging of a manny client host  [PROTOTYPE]
#
# Codifies the by-hand diort setup (journals/DIORT_MIGRATION_PLAN.md, Steps 1-2,4)
# into ONE re-runnable script. Safe to run repeatedly: every step is guarded so a
# second run is a cheap no-op if nothing changed. Reads host fields from
# scripts/remote/hosts.yaml. Runs FROM the orchestrator and pushes to the host
# over ssh/rsync (or acts locally if the host is local: true).
#
# Does NOT touch credentials — that is a separate, user-gated step
# (`mannyctl <host> push-creds`). See the security note in the arch doc.
#
# Steps (each idempotent):
#   1. Ensure JDK 21 present on the host (pacman -S --needed; skip if already there).
#   2. rsync the shaded jar into the host's runelite_libs dir.
#   3. rsync the manny_mcp repo (EXCLUDING venv/.git/creds/caches/logs).
#   4. Create the host venv + pip install -r requirements.txt (skip if present).
#   5. Replicate the RuneLite perf config (gpuplugin=false + 30fps cap) into the
#      host's ~/.runelite/profiles2/ so software-render CPU stays ~46% not ~374%.
#
# Usage: provision.sh <host>          (normally via: mannyctl <host> provision)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOSTS_YAML="${MANNY_HOSTS_YAML:-$SCRIPT_DIR/hosts.yaml}"

PYBIN="$REPO_DIR/venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="python3"

die() { echo "provision: $*" >&2; exit 1; }

HOST="${1:-}"; [ -n "$HOST" ] || die "usage: provision.sh <host>"

hf() { "$PYBIN" - "$HOSTS_YAML" "$HOST" "$1" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1])) or {}
h = (d.get("hosts") or {}).get(sys.argv[2]) or sys.exit(3)
v = h.get(sys.argv[3], ""); print("" if v is None else v)
PY
}

H_LOCAL="$(hf local)"   || die "unknown host '$HOST'"
H_SSH="$(hf ssh)"
H_JDK="$(hf jdk)"
H_STAGING="$(hf staging_dir)"
H_LIBS="$(hf runelite_libs)"

is_local() { [ "$H_LOCAL" = "True" ] || [ "$H_LOCAL" = "true" ]; }
# Feed the command to the remote bash via stdin (`bash -s`) rather than as an
# ssh argument. This avoids the target LOGIN shell (fish on diort) ever parsing
# it: `printf %q` emits bash `$'...\n...'` ANSI-C quoting for any multi-line or
# special-char command, which fish rejects ("Expected a variable name after $").
# `ssh host bash -s <<<"$1"` hands the script straight to bash's stdin, so it is
# shell-agnostic for both single-line and multi-line commands. Exit code of the
# remote command still propagates through ssh (used by the `test -x` guards).
onhost()   { if is_local; then bash -lc "$1"; else ssh -o BatchMode=yes "$H_SSH" bash -s <<<"$1"; fi; }

echo "=== provisioning host '$HOST' (local=$H_LOCAL ssh=$H_SSH) ==="

if is_local; then
  echo "host is local — nothing to stage (repo/jar/venv already here). Verifying perf config only."
else
  [ -n "$H_SSH" ] && [ "$H_SSH" != "None" ] || die "remote host has no ssh: in hosts.yaml"
  # ---- Step 1: JDK 21 ------------------------------------------------------
  echo "[1/5] ensuring JDK 21 ($H_JDK) ..."
  if onhost "test -x $(printf %q "$H_JDK")"; then
    echo "      JDK 21 already present."
  else
    echo "      installing jdk21-openjdk (pacman) ..."
    # --needed makes this a no-op if a later re-run finds it installed.
    onhost "sudo pacman -S --needed --noconfirm jdk21-openjdk" \
      || die "JDK install failed — install jdk21 manually and re-run"
    onhost "test -x $(printf %q "$H_JDK")" \
      || die "jdk21 installed but $H_JDK still missing — fix hosts.yaml jdk: path"
  fi

  # ---- Step 2: shaded jar --------------------------------------------------
  # JAR PIN GATE (DEFECT attempt #12): before shipping ANY jar, assert the
  # build-path *shaded.jar matches the reviewed sha in scripts/remote/jar_pin.yaml.
  # This runs on EVERY provision path (mannyctl provision AND window Gate 4, both
  # funnel through here), so a surprise rebuild fails LOUD instead of shipping.
  # No override lives here on purpose: to adopt a new jar you go through
  # `mannyctl <host> window … --accept-new-jar <prefix>` (reviewed) or hand-edit
  # the pin — either rewrites the pin, after which this gate passes cleanly.
  local_libs="$REPO_DIR/../runelite/runelite-client/build/libs"
  "$PYBIN" "$SCRIPT_DIR/window_checks.py" jar-pin --libs "$local_libs" --pin "$SCRIPT_DIR/jar_pin.yaml" \
    || die "jar pin gate FAILED — refusing to ship (see the JAR PIN GATE block above)"

  echo "[2/5] syncing shaded jar -> $H_LIBS ..."
  local_jar="$(find "$local_libs" -maxdepth 1 -iname '*shaded.jar' 2>/dev/null | head -1)"
  [ -n "$local_jar" ] || die "no local *shaded.jar to ship (build it first on the orchestrator)"
  onhost "mkdir -p $(printf %q "$H_LIBS")"
  rsync -az --info=progress2 "$local_jar" "$H_SSH:$H_LIBS/" || die "jar rsync failed"

  # ---- Step 3: manny_mcp repo (code only) ----------------------------------
  echo "[3/5] syncing manny_mcp repo -> $H_STAGING (excluding venv/.git/creds) ..."
  onhost "mkdir -p $(printf %q "$H_STAGING")"
  rsync -az --info=stats1 \
    --exclude 'venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' --exclude 'logs/' --exclude '*.log' \
    --exclude '.git/' --exclude '.env' \
    "$REPO_DIR/" "$H_SSH:$H_STAGING/" || die "repo rsync failed"

  # ---- Step 4: venv --------------------------------------------------------
  echo "[4/5] ensuring venv + deps on host ..."
  if onhost "test -x $(printf %q "$H_STAGING/venv/bin/python")"; then
    echo "      venv exists; refreshing requirements (idempotent) ..."
  else
    echo "      creating venv ..."
    onhost "cd $(printf %q "$H_STAGING") && python3 -m venv venv" \
      || die "venv create failed (may need: sudo pacman -S python-pip; see DIORT_MIGRATION_PLAN)"
  fi
  onhost "cd $(printf %q "$H_STAGING") && ./venv/bin/pip install -q -r requirements.txt" \
    || die "pip install failed"

  # ---- Step 4b: render host-correct config.yaml (finding #4) ---------------
  # `mannyctl run` -> run_routine.py -> ServerConfig.load() reads config.yaml,
  # NOT hosts.yaml -- so the laptop java_path/runelite_jar shipped in Step 3
  # would make the FIRST real `run` boot with a missing JDK or a STALE untrusted
  # jar (exactly attempt #1's two dead launches: java_path pointed at a JDK the
  # host lacks, and the fallback runelite_jar was ~/runelite.jar). Rewrite the
  # host-specific fields from hosts.yaml, and stamp the trusted shaded jar's
  # sha256 so the launcher REFUSES any other jar (no silent fallback). Runs the
  # host venv python (has pyyaml). Idempotent (overwrites the same keys). Values
  # are passed as argv to avoid quoting a python literal through ssh.
  echo "[4b] rendering host config.yaml (java_path/runelite_jar/sha256 from hosts.yaml) ..."
  jar_base="$(basename "$local_jar")"
  host_jar="$H_LIBS/$jar_base"
  jar_sha="$(sha256sum "$local_jar" | awk '{print $1}')"
  [ -n "$jar_sha" ] || die "could not compute sha256 of $local_jar"
  # runelite_root -> H_STAGING: its runelite-client/build/libs doesn't exist on a
  # client host, so the gradle auto-detect finds nothing and the launcher uses the
  # stamped runelite_jar. (Avoids a missing-dir _validate() warning too.)
  onhost "cd $(printf %q "$H_STAGING") && $(printf %q "$H_STAGING/venv/bin/python") -c 'import yaml,sys; p=\"config.yaml\"; d=yaml.safe_load(open(p)) or {}; d[\"java_path\"]=sys.argv[1]; d[\"runelite_jar\"]=sys.argv[2]; d[\"runelite_jar_sha256\"]=sys.argv[3]; d[\"runelite_root\"]=sys.argv[4]; yaml.safe_dump(d, open(p,\"w\"), sort_keys=False); print(\"config.yaml rendered for host\")' $(printf %q "$H_JDK") $(printf %q "$host_jar") $(printf %q "$jar_sha") $(printf %q "$H_STAGING")" \
    || die "config.yaml render failed"
  echo "      java_path=$H_JDK runelite_jar=$host_jar sha256=${jar_sha:0:16}..."
fi

# ---- Step 5: RuneLite perf config (both local + remote) --------------------
# Exact keys proven on the laptop (journals/REFACTOR_CAMPAIGN_HANDOFF.md +
# wave3_display_isolation): GPU plugin OFF + 30fps cap => ~46% CPU on Xvfb
# software render, instead of ~374% via llvmpipe. MUST be set on every host that
# renders on Xvfb or it will cook the CPU.
echo "[5/5] replicating RuneLite perf config (gpuplugin=false + 30fps cap) ..."
PERF_KEYS='runelite.gpuplugin=false
fpscontrol.limitFps=true
fpscontrol.maxFps=30
fpscontrol.drawFps=false'

# Applied idempotently: for each existing profiles2/*.properties on the host,
# drop any pre-existing copies of these keys and append the canonical set.
# Backs up once to .bak-manny-perf if no backup exists yet.
onhost "$(cat <<PERF
set -e
mkdir -p ~/.runelite/profiles2
shopt -s nullglob
files=(~/.runelite/profiles2/*.properties)
if [ \${#files[@]} -eq 0 ]; then
  # No profile yet (host never launched RuneLite) — the client writes one on
  # first run. Leave a note; perf keys get applied on the next provision.
  echo "      no profiles2/*.properties yet — will apply after first client launch (re-run provision)"
else
  for f in "\${files[@]}"; do
    case "\$f" in *.bak-*) continue;; esac
    [ -f "\$f.bak-manny-perf" ] || cp "\$f" "\$f.bak-manny-perf"
    grep -vE '^(runelite\.gpuplugin|fpscontrol\.limitFps|fpscontrol\.maxFps|fpscontrol\.drawFps)=' "\$f" > "\$f.tmp" || true
    printf '%s\n' "$PERF_KEYS" >> "\$f.tmp"
    mv "\$f.tmp" "\$f"
    echo "      perf keys applied to \$(basename "\$f")"
  done
fi
PERF
)"

echo "=== provision complete for '$HOST' ==="
echo "Next: 'mannyctl $HOST push-creds' (user-gated), then 'mannyctl $HOST start <account>'."
