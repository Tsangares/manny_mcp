# Port-per-lane sticky proxy + game-over-443 verdict — Lessons Learned
**Date:** 2026-07-19
**Supersedes** the sessid-token sticky model from `2026-07-19_mat_sticky_proxy_bringup.md`
as the default, and answers the "43594 is provider-blocked, is there another way?" question.

## The Problem

Two open questions from the sticky bringup:
1. Give every concurrent client its OWN stable residential exit IP (isolation) without
   juggling per-session sessid tokens + their ~30-min TTL.
2. The dataimpulse exit BLOCKS the raw OSRS game socket (TCP 43594). Is the game
   reachable over destination port 443 (which DOES traverse the exit) instead?

## Finding 1 — dataimpulse stickiness is PER GATEWAY PORT (proven)

`gw.dataimpulse.com` ports 10000, 10001, 10002, ... are each an **independent sticky
session with its own stable exit IP**. Empirical (4 curls/port over ~2 min, laptop →
relay → exit):

| upstream port | exit IP (stable ×4) | geo / ASN |
|---|---|---|
| 10000 (sessid token) | 73.184.107.212 | Atlanta GA — AS7922 Comcast |
| 10001 (`--no-session`) | 184.58.105.38 | Columbus OH — AS10796 Charter |
| 10002 (`--no-session`) | 82.40.87.121 | Birmingham **GB** — see GEO CAVEAT |
| 10050/51/52 (fresh) | 69.246.27.171 / 82.40.73.28 / 172.56.194.99 | Tupelo MS / NYC / Boston — all US |

Stable within a port, distinct across ports. **The port alone provides stickiness** —
no sessid token needed (10001/10002/1005x ran `--no-session`, keeping only the `cr.us`
geo pin). This is simpler than sessid (no TTL to re-issue) and is now the DEFAULT model
for concurrent lanes.

**GEO CAVEAT (important):** the `cr.us` US pin is honored only on a **fresh** port
session. A sticky port **reuses whatever exit it already holds until its ~30-min TTL
lapses** — so a port previously claimed with a non-US session egresses non-US for a
while (that is why 10002 landed GB while every *fresh* port honored US). Mitigations
shipped: `proxy status` now prints the exit **country** and warns if not US; if a lane
egresses non-US at launch, reassign it to a fresh higher port or wait out the TTL.

**TTL:** within the ~5-min window every port held its IP; docs put sticky TTL ~30 min.
A new session (port first-claim or TTL lapse) re-rolls the IP — so the IP is stable
WITHIN a play session, best-effort across days. Fine for the goal (concurrency
isolation), not a guarantee of a permanent per-account IP (dataimpulse residential is a
rotating pool; true static residential is a different product).

## Finding 2 — GAME OVER 443: VIABLE (transport proven; one live login still needed)

**Verdict: proxied game via 443 = YES (viable), pending one throwaway-login confirmation.**
The 43594 block does NOT have to gate a live proxied session.

Evidence chain:
- **43594 is blocked at the exit, 443 is not.** Through the US relay,
  `CONNECT oldschoolN:443` succeeds (SOCKS REP=0x00); `CONNECT oldschoolN:43594` is
  refused (REP=0x01). (Earlier journal saw 0x02; either way blocked.)
- **The world host serves the SAME TLS game service on BOTH ports.** `openssl s_client`
  to `oldschool1.runescape.com` on **43594 AND 443** both complete a full TLS handshake
  with the identical cert `CN=*.runescape.com` (Amazon-issued), same IP `8.42.17.164`
  (= `osrs-world-1.l3ushe.jagex.com`). Modern OSRS (post-AWS migration, rsprot) is
  TLS-wrapped and the world is fronted on both ports — 443 is the firewall-fallback for
  exactly this scenario.
- **Full TLS to the game host on 443 traverses the dataimpulse exit end-to-end.**
  `curl --socks5-hostname` and a raw Python `ssl.wrap_socket` through the US relay both
  complete TLSv1.2 to `oldschool1:443` (cert `CN=*.runescape.com`). So the transport a
  proxied client needs for game-over-443 is available through the proxy.
- **RuneLite has no port knob and no OSS 443-fallback.** The OSS tree
  (`/home/wil/Desktop/runelite`) only references 43594 in the worldhopper *ping* plugin
  (`.../plugins/worldhopper/ping/Ping.java:53,289`); the real game socket + any fallback
  live in the injected closed-source Jagex gamepack (revision from `Client.getRevision()`
  at `runelite-api/.../Client.java:703`, world host pattern `oldschoolN.runescape.com`
  from `.../rs/WorldSupplier.java:82-85`). We cannot force 443 from the Java side.

### The lever (implemented, opt-in, default OFF): relay-side 43594→443 rewrite

Since the SAME TLS game service listens on 443 and 443 traverses the proxy, the smallest
lever is **on our side, not Java**: `socks_relay.py --game-port-443` rewrites any outbound
`CONNECT :43594` into `:443`. The client (or gamepack) still asks for 43594; the relay
sends it to 443; dataimpulse allows it; the client's own TLS + game protocol flow inside.
**Proven end-to-end:** a client CONNECTing to `oldschool1:43594` through a relay with
`--game-port-443` gets a full TLS session to the game host (`CN=*.runescape.com`, log:
`CONNECT oldschool1.runescape.com:43594->443(game-rewrite) -> upstream OK`). No Java
patch, no client config, ATYP=domain preserved (exit resolves DNS + SNI matches).

**What is NOT yet proven:** an actual sustained in-game session (login → world → gameplay)
riding 443. The transport is proven; the live game protocol behaving identically on 443
is strongly inferred (same cert/IP/backend) but must be observed once on a throwaway
account before any real use. `--game-port-443` stays OFF by default for that reason.

## What shipped (port-per-lane model)

- `socks_relay.py`: `--upstream-port N` (override gateway port), `--session ID` /
  `--no-session` (sessid token control), `--game-port-443` (opt-in 43594→443 rewrite).
  Secret handling unchanged (token/login/pass read in-process, never argv/log).
- `proxy_relay.sh`: `MANNY_UPSTREAM_PORT` → `--upstream-port … --no-session`;
  `MANNY_GAME_443=1` → `--game-port-443`; `status` now prints exit IP **+ country** and
  warns on non-US (geo caveat). Default path (no env) byte-for-byte unchanged.
- `mannyctl`: reads top-level `hosts.yaml proxy_lanes` (account → gateway port); a
  proxied `start`/`run <account>` pins `MANNY_SOCKS_PORT` **and** `MANNY_UPSTREAM_PORT`
  to that account's lane, so concurrent clients get distinct stable exits. Unlisted
  accounts use the shared default lane (local :1080 → upstream :10000) — unchanged.
- `client_remote.sh`: forwards `MANNY_UPSTREAM_PORT` + `MANNY_GAME_443` to the relay.
- `hosts.yaml`: `proxy_lanes:` map (punitpun→10001, blast→10002) + full model/caveat doc.

Local port == upstream port for a lane (1:1, memorable, no 127.0.0.1 collision between
two lanes on one host).

## Anti-Patterns

1. **Don't** assume a sticky port honors the geo pin — a stale (pre-TTL) session on that
   port wins. Check `proxy status` country before a launch; re-roll to a fresh port if
   non-US.
2. **Don't** conclude "43594 blocked ⇒ no proxied game." 443 carries the same TLS game
   service and traverses the exit; rewrite the port at the relay.
3. **Don't** send a raw `opcode 15 + revision` JS5 probe expecting a status byte on
   modern OSRS — the protocol is TLS-wrapped now; the world holds the raw TCP open with
   no reply on BOTH 43594 and 443 (a wrong-handshake artifact, not a dead port). Use
   `openssl s_client` / a TLS wrap to characterize the service instead.

## Debugging Commands

| Command | Purpose |
|---|---|
| `socks_relay.py --upstream-port N --no-session` | one port-lane relay (stable per-port US exit) |
| `curl -x socks5h://127.0.0.1:PORT https://ipinfo.io/json` | egress IP **+ country** per lane |
| `openssl s_client -connect oldschool1.runescape.com:443` | prove the world serves TLS on 443 |
| Python `ssl.wrap_socket` over a SOCKS5 CONNECT to :443 | prove game-host TLS traverses the proxy |
| `socks_relay.py --game-port-443` then CONNECT :43594 | prove the 43594→443 rewrite works |

## What remains before a live proxied trial

1. **One throwaway-account login over 443** (relay with `--game-port-443` on a lane port)
   to confirm a sustained in-game session actually rides 443 — the only unproven link.
2. User go-ahead + an expendable account (never `main`, never a banned alias).
3. Per-lane geo check at launch (now surfaced by `proxy status`) — ensure US before login.
4. The dataimpulse 43594 unblock request becomes OPTIONAL if the 443 path is confirmed.
