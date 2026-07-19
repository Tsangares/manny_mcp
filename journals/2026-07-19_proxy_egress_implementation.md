# 2026-07-19 — Proxy egress implementation report (dataimpulse residential SOCKS5)

**Status:** BUILT + committed (`403e235`). Verified offline. **NOT deployed to any host, no client
launched.** This report documents what was implemented, how, what was verified, and the exact gated
steps + open risks that remain before a live account may use it.

Supersedes the "no client wiring done" status of
[`2026-07-19_proxy_ip_wiring_plan.md`](2026-07-19_proxy_ip_wiring_plan.md) — that file is the *plan
and rationale*; this one is the *implementation*. Credentials remain only in
`~/.manny/credentials.yaml` → `proxies.dataimpulse` (600 perms); nothing secret is in the repo.

## Why this exists (one paragraph)

`diort`'s public egress IP is `96.39.231.108` — **identical to the laptop's**, because both sit
behind the same home NAT. The "diort migration for ban isolation" gave **zero IP diversity**; both
behavioral bans (`new` 07-18, `newbakshesh` 07-19) left from this one IP. Changing the egress IP
requires an *explicit* proxy — it is not a property of which machine runs the client. This work wires
the verified dataimpulse residential exit (`82.0.170.71`) into the client launch as an **opt-in,
default-OFF** flag.

## Architecture — why a local no-auth relay, not proxychains or Java's SOCKS auth

The raw OSRS game connection is a **raw TCP socket** to the world server (port 43594), not HTTP — so
an HTTP proxy can't carry it; the egress must be SOCKS5 end-to-end. Two candidate paths were
rejected:

- **proxychains + Java NIO** — documented broken, and proxychains isn't installed on diort.
- **JVM `-DsocksProxyHost/Port` speaking auth directly to dataimpulse** — Java's SOCKS5
  username/password auth is version-sensitive and awkward.

Chosen shape: a tiny **loopback no-auth SOCKS5 relay** (`pproxy`) runs *on the client host*. It
accepts plain SOCKS5 on `127.0.0.1:<port>` and forwards to dataimpulse, owning the upstream
credentials (and, in future, the sticky session). The JVM then just speaks plain SOCKS5 to
`127.0.0.1` via `-DsocksProxyHost=127.0.0.1 -DsocksProxyPort=<port>`, which routes **all** its TCP
sockets — including the game socket — through the relay. This sidesteps both broken paths.

```
JVM (RuneLite)                 host loopback              upstream
  -DsocksProxyHost=127.0.0.1  ──►  pproxy relay  ──►  dataimpulse residential
  -DsocksProxyPort=<port>          (no-auth in,        gw.dataimpulse.com:10000
  (all TCP incl. 43594)            authed out)         exit ~82.0.170.71
```

## What was built (commit `403e235`, author `Tsangares`)

| File | Change |
|---|---|
| `scripts/remote/proxy_relay.sh` | **new (+202).** `start\|stop\|status` a pproxy SOCKS5 relay on `127.0.0.1:${MANNY_SOCKS_PORT:-1080}`. Reads `proxies.dataimpulse.socks5` from `~/.manny/credentials.yaml` at runtime via repo-venv python+pyyaml, converts `socks5h://user:pass@host:port` → pproxy's `socks5://host:port#user:pass`, launches `setsid`-detached (survives ssh disconnect), pidfile+log in `/tmp`. Idempotent. `status` runs a `curl -x socks5h://127.0.0.1:<port>` egress check and prints the exit IP, warning loudly if it equals the home IP. Secret never echoed. |
| `scripts/remote/client_remote.sh` | **(+35).** Opt-in: when `MANNY_SOCKS_PORT` is set **or** `MANNY_PROXY=1`, ensure the relay is up *before* launch and append the two socks `-D` props to the java command (threaded next to `-Dmanny.navBackend`). **Default OFF = byte-for-byte identical launch.** On relay failure it **aborts the launch** rather than falling back to direct egress — a proxied launch must never silently leak the home IP. |
| `scripts/remote/mannyctl` | **(+73).** `mannyctl <host> proxy <start\|stop\|status>` to manage the relay directly, plus a `--proxy` flag on `start`/`run` that threads `MANNY_PROXY=1` (and optional `MANNY_SOCKS_PORT` override) into the host launch env. `status`/`stop`/`temp` never set the flag, so they're untouched. |
| `requirements.txt` | **(+4).** `pproxy>=2.7.0`. |

## Tools / versions

- **pproxy 2.7.9** — pure-Python async SOCKS5/HTTP proxy + relay (`pip install pproxy`). Chosen over
  `gost`/`redsocks`/`microsocks` because it needs no system package on diort — it installs into the
  existing repo venv, so `provision`'s `pip install -r requirements.txt` ships it with everything
  else.
- **PyYAML** (already a repo dep) — parses the credentials file host-side.
- **Python 3.14.5** on the laptop (verification host). diort's Python version is unconfirmed; the
  relay's launcher is written to work on **3.10–3.14** (see gotcha below).

## Verification done offline (laptop, no client, torn down after)

1. **Parser round-trips** the spec sample `socks5h://u:p@h:1` → `socks5://h:1#u:p`, and correctly
   handles passwords containing `:` and `@` (`rpartition('@')` isolates the last `@`; `partition(':')`
   splits on the first `:`).
2. **Live relay smoke test** (nonstandard port, torn down): `start` → `status` egress =
   **`82.0.170.71`** (dataimpulse residential exit, **NOT** the home IP `96.39.231.108`) →
   idempotent re-`start` no-ops → `stop` → `DOWN`. Secret never printed to stdout or log.
3. **OFF-path and PROXY-path** java command-string generation both inspected — OFF path is unchanged.

## Issues hit and how they were resolved

- **pproxy 2.7.9 crashes on Python 3.14.** `asyncio.get_event_loop()` now *raises* in the main thread
  (the implicit-loop-creation behavior was removed) instead of auto-creating a loop, so a bare
  `python -m pproxy` dies at startup. **Fix:** the relay launches pproxy through a small event-loop
  shim (`python -c` that `try/except`-creates a loop before calling `pproxy.server.main()`), which
  covers 3.10 through 3.14. Verified working on 3.14.5.
- **ssh disconnect could SIGHUP the relay.** **Fix:** `setsid … </dev/null >log 2>&1 & disown`
  severs the controlling tty, matching how `client_remote.sh` already detaches the java client.
- **A bad bind/upstream makes pproxy exit silently.** **Fix:** `start` polls the loopback port for a
  real TCP accept (up to ~10s) and fails loudly with the last log lines if the process dies first,
  so `--proxy` launches can't proceed against a dead relay.
- **Secret hygiene.** The upstream is parsed into a shell local, `unset` immediately after launch,
  and never echoed. (One residual: the secret is visible in the pproxy **process argv** on the host
  — unavoidable with pproxy's CLI; not logged, not committed.)

## Deploy runbook (all steps GATED — none run yet)

```
# 1. Ship creds incl. the proxies section (USER-GATED; also fixes diort's stale banned default:new)
mannyctl diort push-creds

# 2. Ship the new scripts + install pproxy on diort
mannyctl diort provision

# 3. Bring the relay up and CONFIRM the residential exit (expect 82.x/74.x, NOT 96.39.231.108)
mannyctl diort proxy start
mannyctl diort proxy status

# 4. Launch through the proxy (default display from hosts.yaml account_displays)
mannyctl diort start <account> --proxy
```

## Open items before a LIVE account may use this (ranked)

1. **Sticky session — UNCONFIRMED (needs the dataimpulse dashboard).** Port `:10000` appears to
   **rotate the residential exit per request**. A live OSRS session needs **one stable IP for its
   whole duration** — a mid-session IP change reads as session-hijack / forces re-auth and is *worse*
   than no proxy. dataimpulse supports sticky sessions via a token in the username; the exact syntax
   is account-specific and must be confirmed, then stored as a sticky `socks5` variant in
   `credentials.yaml`, **before any sustained login.**
2. **Game-socket traversal — UNPROVEN.** The JVM socks props *should* carry the raw game socket
   (43594), but this could not be verified without a client. **Confirm on a throwaway/banned alias**
   (e.g. `new` on `:4`) that the client log shows the **world/game** connection (not just HTTP)
   established through the proxy, before any real session. Good first use of the proxy.
3. **pproxy on diort.** The 3.14 shim covers 3.10–3.14, but pproxy's clean import on diort
   specifically is unverified — `mannyctl diort proxy start` surfaces it immediately.
4. **Display mapping.** Map `punitpun → :5` in `hosts.yaml` `account_displays` before launching it,
   so it can't collide with the `:2` `newbakshesh` ban-evidence client (unmapped accounts fall to
   the host default `:2`).
5. **Standing gate unchanged.** This is downstream of **humanization** — a naked ~1h scripted
   session on a fresh residential IP is the exact profile that burned `new`/`newbakshesh`. The proxy
   changes the IP; it does not change the behavior. Humanization (esp. of the tutorial phase) remains
   the prerequisite for a real `punitpun` run.

## Provenance

- Code: subagent build, scoped commit `403e235` (author `Tsangares <Tsangares@gmail.com>`, no
  co-author). Parked humanization files (`mcptools/tools/routine.py` seed hunk, `mcptools/humanize.py`,
  `tests/test_humanize.py`) left untouched/unstaged.
- Sanitized snapshot of the relay: [`code/proxy_relay.sh`](code/proxy_relay.sh) (reads secrets from
  file at runtime — nothing sensitive inlined).
