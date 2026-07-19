# 2026-07-19 — IP-diversity / proxy wiring plan (dataimpulse + mat)

**Status:** PLAN + verified prerequisites. No client wiring done (live contact is still gated on
humanization). This is the runbook for the live-work phase. Credentials live in
`~/.manny/credentials.yaml` → `proxies.dataimpulse` (600 perms) — never inline them in code/docs.

## The finding that motivates this (important)

`diort`'s direct public egress IP is **96.39.231.108 — identical to the laptop's.** diort sits behind
the **same home NAT**, so the "diort migration for ban-risk isolation" gave **zero IP diversity**:
BOTH behavioral bans (`new` 07-18, `newbakshesh` 07-19) egressed from this one home IP. Changing the
egress IP therefore requires an *explicit* proxy/relay — it is not a property of which local machine
runs the client.

## Verified resources (2026-07-19)

| Resource | Address | Egress IP (measured) | Notes |
|---|---|---|---|
| Home NAT (laptop + diort) | — | `96.39.231.108` | The flagged IP. Both bans came from here. |
| dataimpulse residential proxy | `gw.dataimpulse.com:10000` (also `74.81.81.81:10000`) | `82.0.170.71` (rotating residential) | Serves **both** HTTP and SOCKS5 on :10000. Verified working from **laptop AND diort**. Creds in `proxies.dataimpulse`. |
| mat (VPS) | Tailscale `100.123.10.30` / public `157.254.18.86` | `157.254.18.86` (datacenter) | Own IP, distinct from home. SSH-reachable (`ssh mat`). Datacenter IP is itself ban-risky → only useful as a *host/relay* combined with the residential proxy, not as a bare egress. |

## Two operational cautions before trusting the proxy for a game session

1. **Sticky vs rotating.** Port `:10000` appears to rotate the residential exit per request. A live
   OSRS session needs a **stable IP for its whole duration** (a mid-session IP change looks like
   session hijack / triggers re-auth). dataimpulse supports **sticky sessions** via a session token in
   the username (e.g. `...__cr.us;sessid-<id>` or their documented sticky format) — confirm the exact
   sticky syntax on the dataimpulse dashboard and store a sticky variant before any live login.
2. **The game socket is raw TCP, not HTTP.** RuneLite talks HTTP (OkHttp) for jav_config/world-list
   but the actual game connection is a raw socket to the world server (port 43594). An **HTTP** proxy
   won't carry the game socket — the residential egress must be **SOCKS5** (or a transparent
   TCP-redirect) so the game socket itself is proxied. HTTP-only proxying would leave the game traffic
   on the home IP = pointless.

## Wiring approaches for the Java client (ranked)

`proxychains` is NOT installed on diort and the docs record **proxychains + Java NIO as broken**, so
that path is out. Preferred options:

1. **Local SOCKS relay → JVM socks props (RECOMMENDED).** Run a tiny local forwarder on the run host
   that accepts a no-auth SOCKS5 on `127.0.0.1:<port>` and forwards to dataimpulse (relay handles the
   upstream auth + sticky session). Good candidates: `gost`, `redsocks`, `microsocks`+upstream, or an
   `ssh -D` chain. Then launch the JVM with `-DsocksProxyHost=127.0.0.1 -DsocksProxyPort=<port>` —
   Java routes **all** TCP sockets (including the game socket) through it. This sidesteps Java's finicky
   SOCKS auth and the broken proxychains path entirely. Wire it into `scripts/remote/client_remote.sh`
   as an optional `MANNY_PROXY`/`SOCKS_RELAY` env, mirroring how `NAV_BACKEND` is injected.
2. **JVM SOCKS props + `java.net.Authenticator`.** `-DsocksProxyHost/-DsocksProxyPort` plus a default
   Authenticator supplying the dataimpulse user/pass. Works in principle but Java's SOCKS5
   username/password auth is version-sensitive and awkward; the relay in (1) is more robust.
3. **Run the client on `mat` + option (1).** Uses mat's compute and its distinct routing, but mat's
   bare IP is datacenter — still must egress through the residential relay. Only worth it if diort is
   busy/thermal-constrained; otherwise it adds a host to provision for no IP benefit over (1) on diort.

## Verification gate (before any live account uses the proxy)

- With the relay up, from the run host: `curl -x socks5h://127.0.0.1:<port> https://api.ipify.org`
  returns the residential exit (not `96.39.231.108`), and the SAME IP twice in a row (sticky holds).
- Launch RuneLite with the JVM socks props on a **throwaway/banned alias first** and confirm in the
  client log that the **world/game connection** established through the proxy (not just HTTP) — i.e.
  the account actually reaches the login/lobby, proving the raw game socket is proxied.
- Only then consider a real (humanized) session on `punitpun`.

## Sequence dependency

This whole plan is **downstream of humanization** (the standing prerequisite for sustained live
contact) and the user's account posture. It is prep: resources verified, approach chosen, cautions
documented. Do not launch a live sustained session on `punitpun` through this until humanization is
proven on an expendable account.
