# Sticky dataimpulse proxy + mat bring-up — Lessons Learned
**Date:** 2026-07-19

## The Problem

Prove a STICKY residential proxy session through dataimpulse, get the OSRS game
socket to traverse it, and stand up the Debian VPS `mat` as a proxy-mandatory
client host. Two prior blockers were open: sticky-session syntax unconfirmed, and
`pproxy` (the relay tool from commit `403e235`) could not carry the dataimpulse
token at all (`journals/2026-07-19_pproxy_incompatible_with_dataimpulse_tokens.md`).

## Root Cause / Key Findings

### 1. pproxy is a dead end for dataimpulse — swapped for a tiny asyncio relay

**What happened:** `pproxy -r` rejects the dataimpulse session/geo token in the
username (`...__cr.us;sessid.<id>`) with `invalid proxies_by_uri value`. Both the
`.` in `__cr.us` and the `;` between params break its URI grammar; percent-encoding
does not help.

**Extra hazard observed:** when pproxy dies on that bad `-r`, its argparse error
message **echoes the full upstream URI — login, token, AND password — into its log
file**, which `proxy_relay.sh` used to `tail` to stderr on failure. That was a live
credential-leak path. The replacement never puts the secret on argv or in a log.

**Solution:** wrote `scripts/remote/socks_relay.py` — a ~200-line, dependency-free
(pure `asyncio`) no-auth SOCKS5 → upstream-SOCKS5 forwarder. It reads the upstream
`user:pass` from the creds file **inside the process** (never argv/stdout/log),
does the username/password handshake with the token passed **verbatim**, and
forwards each CONNECT (preserving `ATYP=domain` so the exit resolves DNS — no
local-DNS leak). `proxy_relay.sh` now launches it instead of pproxy.

Two bugs cost time while writing it (both client-side SOCKS parse):
- `ver, nmethods = readexactly(2)` unpacks to **ints**; an inverted ternary tried
  `nmethods[0]` → `TypeError: 'int' object is not subscriptable`. Silent connection
  close, empty curl.
- The domain label was decoded with `.decode("idna", "replace")`. **The `idna`
  codec does not support the `replace` error handler** → `UnicodeError` on *every*
  hostname CONNECT. The label is log-only; decode `ascii`/`replace` instead.
Lesson: when a SOCKS relay "connects but returns nothing," the handler is dying in
a silently-swallowed `except` — instrument the excepts and run the relay `-u`
(unbuffered) or its stderr never reaches the log file before you read it.

### 2. Sticky: CONFIRMED. Syntax is the username token, not a port trick

Sticky is achieved by `sessid.<caller-id>` in the username, combined with geo
`cr.us`, on a sticky port (`:10000`–`:20000`). The full upstream form (stored in
`~/.manny/proxies.yaml`, **not** in repo, 600):
`socks5h://<login>__cr.us;sessid.<id>:<pass>@gw.dataimpulse.com:10000`
Param grammar: `__` after login, `.` for key/value, `;` between params.

**Proof (laptop → relay → dataimpulse):** 6 curls over ~2.5 min + an earlier
direct probe all egressed **the same IP `158.51.100.187` (US, Maryland,
AS7029 Windstream — residential)**. Then `mannyctl diort proxy status` and
`mannyctl mat proxy status` — from two *different* hosts, minutes later — egressed
**the same `158.51.100.187`**. The sessid pins the exit IP regardless of which
host dials, because the stickiness lives in the token. TTL per docs: ~30 min, no
username param to extend (re-issue a fresh sessid when it lapses). Rotating (no
sticky) uses ports `:823`/`:824` and hands out random-country exits — do NOT use
the bare login (a rotating multi-country login is itself a ban signal).

### 3. RAW GAME SOCKET (TCP 43594) IS BLOCKED AT THE PROVIDER — hard gate

`CONNECT <world>:43594` through dataimpulse returns SOCKS5 `REP=0x02`
("connection not allowed by ruleset"). Characterized against `portquiz.net`:
**80/443/8080 → OK; 22/2000/25565/30000/43594 → BLOCKED.** Hostnames resolve fine,
so it is a **port allowlist on dataimpulse's side, not DNS or relay code.** Their
docs confirm the default open ports (80, 443, 5228, 53, 5060, 8080, 8090, 8443,
853) and that any other port needs a **manual unblock request with target +
use-case (KYC possible)**. So a live *game* login cannot traverse this proxy until
that request is granted. HTTP (jav_config / world list / login screen) traverses
fine on 443.

### 4. RuneLite's OkHttp DOES honor `-DsocksProxyHost` — no HTTP leak

Feared the client's HTTP (OkHttp) might bypass the JVM SOCKS props. Verified with
`ss -tnp` during a cred-less launch on diort: **every** java TCP connection went to
`127.0.0.1:1080` and the relay forwarded to `gw.dataimpulse.com:10000`; **zero**
external connections from the java pid. Relay log recorded the client's targets:
`oldschool.config.runescape.com:443`, `api.runelite.net`, `static.runelite.net`,
`oldschoolNN.runescape.com:443`. So the full HTTP boot path is proxied.
(Note: `ss`/live-socket inspection beats the relay's own log for leak-checking —
appending a "mark" line to a log the relay process holds open via a non-append fd
interleaves by offset, so mark-relative `awk` counts are unreliable.)

### 5. mat is Debian — provision.sh's pacman step is Arch-only

`provision.sh` Step 1 installs JDK via `pacman`. mat is Debian 13 (trixie). The
guard is `test -x <jdk path>`, so the fix is to **pre-install via apt and point
hosts.yaml `jdk:` at the real path** — then Step 1 is a no-op:
`sudo apt-get install -y openjdk-21-jdk xvfb` →
`/usr/lib/jvm/java-21-openjdk-amd64/bin/java` (21.0.11). mat has NOPASSWD sudo,
Xvfb, rsync, python3-venv already. Login shell is fish (like diort/llama) —
mannyctl/provision already wrap remote cmds in bash; keep it that way.

## Fail-closed (leak guard) — verified

mat is `force_proxy: true` in hosts.yaml (new per-host flag): mannyctl forces
`MANNY_PROXY=1` for every launch, and `client_remote.sh` aborts the launch if
`proxy_relay.sh start` fails. Proved the trigger: with no creds resolvable
(HOME override, bogus `MANNY_CREDS`), the relay dies immediately and
`proxy_relay.sh start` returns **rc=1** → "refusing to launch (would leak home
IP)". No relay = no launch. mat's bare IP (157.254.18.86, datacenter) can never
leak. The creds fallback chain (proxies.yaml → credentials.yaml) is robust enough
that a merely-wrong `MANNY_CREDS` path is rescued, which is desirable.

## Anti-Patterns

1. **Don't** feed dataimpulse tokens to pproxy — its URI parser rejects `.`/`;`
   AND leaks the secret in its error log. Use `socks_relay.py`.
2. **Don't** assume the residential proxy carries the game socket — 43594 is
   provider-blocked; only a dataimpulse unblock request opens it.
3. **Don't** use the bare login (no `cr.us`) as a sticky shortcut — it egresses
   random countries.
4. **Don't** trust a relay's own log for leak-checking; use `ss -tnp` on the pid.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `curl -x socks5h://127.0.0.1:PORT https://ipinfo.io/json` | egress IP + country through relay |
| `ss -tnp \| grep pid=<java>` | prove client sockets go only to 127.0.0.1:relay (no leak) |
| direct SOCKS5 `REP` probe to `portquiz.net:<port>` | characterize provider port allowlist |
| `mannyctl <host> proxy start\|status\|stop` | drive the relay on a remote host |

## Files Modified

| File | Change |
|------|--------|
| `scripts/remote/socks_relay.py` | NEW — dependency-free SOCKS5→dataimpulse forwarder (carries the token; replaces pproxy) |
| `scripts/remote/proxy_relay.sh` | launch socks_relay.py; creds reader now defaults to proxies.yaml→credentials.yaml chain; pidfile/log renamed manny_socks_relay_* |
| `scripts/remote/mannyctl` | `push-proxy` (copy only proxies.yaml, non-gated); `push-creds` now also ships proxies.yaml; `force_proxy` host flag forces MANNY_PROXY=1 |
| `scripts/remote/hosts.yaml` | mat entry (Debian, force_proxy, datacenter-IP warning, Debian JDK path) |

## What remains before a live proxied trial

1. **dataimpulse port-unblock for 43594** (support request; use-case + possible
   KYC) — without it the game socket cannot traverse. HARD GATE.
2. `mannyctl mat push-creds` (user-gated) — account tokens not yet on mat.
3. User go-ahead + a throwaway/expendable account (never `main`, never a banned
   alias) for the first proxied game login.
4. sessid TTL is ~30 min — issue a fresh `sessid.<id>` per session before login.
